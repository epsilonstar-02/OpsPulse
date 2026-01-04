"""
Data Aggregation Service for Dashboard Analytics.

Collects and aggregates data from all OpsPulse components:
- Log Generator (via HTTP API)
- Kafka/Redpanda (message queue stats)
- Pathway Consumer (pipeline metrics)
- RAG Server (remediation stats)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import logging
import httpx
import json
import uuid

from ..config import get_settings, get_kafka_config
from ..models.analytics import (
    DashboardOverview, LogLevelBreakdown, ServiceStats, AnomalyMetrics,
    AnomalyTypeStats, PipelineMetrics, RealTimeStats, TimeSeriesDataPoint,
    TimeSeriesData, TimeRange, AnalyticsSummary
)
from ..models.logs import LogEntry, Alert, Remediation, AlertWithRemediation, LogLevel, AnomalyType

logger = logging.getLogger(__name__)


class MetricsStore:
    """In-memory store for time-series metrics."""
    
    def __init__(self, max_history_minutes: int = 60):
        self.max_history = max_history_minutes
        self._log_counts: deque = deque(maxlen=max_history_minutes * 60)  # per-second
        self._error_counts: deque = deque(maxlen=max_history_minutes * 60)
        self._anomaly_counts: deque = deque(maxlen=max_history_minutes * 60)
        self._response_times: deque = deque(maxlen=max_history_minutes * 60)
        self._service_stats: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
    def add_log_count(self, count: int, timestamp: datetime):
        self._log_counts.append({"ts": timestamp, "value": count})
    
    def add_error_count(self, count: int, timestamp: datetime):
        self._error_counts.append({"ts": timestamp, "value": count})
    
    def add_anomaly_count(self, count: int, timestamp: datetime):
        self._anomaly_counts.append({"ts": timestamp, "value": count})
    
    def add_response_time(self, time_ms: float, timestamp: datetime):
        self._response_times.append({"ts": timestamp, "value": time_ms})
    
    def get_recent_sum(self, metric_deque: deque, minutes: int = 5) -> int:
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return sum(d["value"] for d in metric_deque if d["ts"] >= cutoff)
    
    def get_time_series(self, metric_deque: deque, minutes: int = 60) -> List[TimeSeriesDataPoint]:
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [
            TimeSeriesDataPoint(timestamp=d["ts"], value=d["value"])
            for d in metric_deque if d["ts"] >= cutoff
        ]


class DataAggregator:
    """
    Aggregates data from all OpsPulse components for dashboard display.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.metrics = MetricsStore(self.settings.METRICS_HISTORY_MINUTES)
        
        # Counters
        self._total_logs = 0
        self._total_anomalies = 0
        self._total_alerts = 0
        self._total_remediations = 0
        
        # Recent data storage
        self._recent_logs: deque = deque(maxlen=self.settings.MAX_RECENT_LOGS)
        self._recent_alerts: deque = deque(maxlen=self.settings.MAX_RECENT_ALERTS)
        self._recent_remediations: deque = deque(maxlen=100)
        
        # Service statistics
        self._service_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_logs": 0,
            "error_count": 0,
            "warning_count": 0,
            "anomaly_count": 0,
            "response_times": deque(maxlen=1000),
            "last_seen": None
        })
        
        # Anomaly type counts
        self._anomaly_type_counts: Dict[str, int] = defaultdict(int)
        self._anomaly_type_scores: Dict[str, List[float]] = defaultdict(list)
        self._anomaly_type_last_seen: Dict[str, datetime] = {}
        
        # Log level counts
        self._log_level_counts: Dict[str, int] = defaultdict(int)
        
        # Pipeline state
        self._pipeline_status = "stopped"
        self._windows_processed = 0
        self._pipeline_start_time: Optional[datetime] = None
        
        # Component status
        self._kafka_connected = False
        self._rag_connected = False
        
        # Timestamps
        self._last_log_timestamp: Optional[datetime] = None
        self._last_anomaly_timestamp: Optional[datetime] = None
        self._last_alert_timestamp: Optional[datetime] = None
        self._start_time = datetime.now()
    
    def record_log(self, log_data: Dict[str, Any]):
        """Record a log entry for analytics."""
        self._total_logs += 1
        now = datetime.now()
        self._last_log_timestamp = now
        
        # Store recent log
        self._recent_logs.append(log_data)
        
        # Update service stats
        service = log_data.get("service", "unknown")
        self._service_stats[service]["total_logs"] += 1
        self._service_stats[service]["last_seen"] = now
        
        # Log level
        level = log_data.get("level", "INFO").upper()
        self._log_level_counts[level] += 1
        if level == "ERROR":
            self._service_stats[service]["error_count"] += 1
        elif level == "WARNING":
            self._service_stats[service]["warning_count"] += 1
        
        # Response time
        response_time = log_data.get("response_time_ms")
        if response_time:
            self._service_stats[service]["response_times"].append(response_time)
            self.metrics.add_response_time(response_time, now)
        
        # Anomaly info
        labels = log_data.get("_labels", {})
        if labels.get("is_anomaly"):
            self._total_anomalies += 1
            self._last_anomaly_timestamp = now
            self._service_stats[service]["anomaly_count"] += 1
            
            anomaly_type = labels.get("anomaly_type", "none")
            self._anomaly_type_counts[anomaly_type] += 1
            self._anomaly_type_last_seen[anomaly_type] = now
            
            score = labels.get("anomaly_score", 0.0)
            self._anomaly_type_scores[anomaly_type].append(score)
            
            self.metrics.add_anomaly_count(1, now)
        
        self.metrics.add_log_count(1, now)
        if level in ("ERROR", "CRITICAL"):
            self.metrics.add_error_count(1, now)
    
    def record_alert(self, alert_data: Dict[str, Any]) -> str:
        """Record an alert and return its ID."""
        self._total_alerts += 1
        alert_id = str(uuid.uuid4())[:8]
        
        alert_with_id = {**alert_data, "id": alert_id, "received_at": datetime.now().isoformat()}
        self._recent_alerts.append(alert_with_id)
        self._last_alert_timestamp = datetime.now()
        
        return alert_id
    
    def record_remediation(self, remediation_data: Dict[str, Any]):
        """Record a remediation response."""
        self._total_remediations += 1
        self._recent_remediations.append({
            **remediation_data,
            "received_at": datetime.now().isoformat()
        })
    
    def update_pipeline_status(self, status: str, windows: int = 0):
        """Update pipeline status."""
        self._pipeline_status = status
        self._windows_processed = windows
        if status == "running" and not self._pipeline_start_time:
            self._pipeline_start_time = datetime.now()
    
    def update_component_status(self, kafka: bool = None, rag: bool = None):
        """Update component connection status."""
        if kafka is not None:
            self._kafka_connected = kafka
        if rag is not None:
            self._rag_connected = rag
    
    def get_dashboard_overview(self) -> DashboardOverview:
        """Get main dashboard overview data."""
        now = datetime.now()
        uptime = (now - self._start_time).total_seconds()
        
        # Calculate rates (per minute, last 5 minutes)
        logs_last_5min = self.metrics.get_recent_sum(self.metrics._log_counts, 5)
        errors_last_5min = self.metrics.get_recent_sum(self.metrics._error_counts, 5)
        anomalies_last_5min = self.metrics.get_recent_sum(self.metrics._anomaly_counts, 5)
        
        logs_per_minute = logs_last_5min / 5 if logs_last_5min else 0
        error_rate = errors_last_5min / logs_last_5min if logs_last_5min else 0
        anomaly_rate = anomalies_last_5min / logs_last_5min if logs_last_5min else 0
        
        # Service health
        services = list(self._service_stats.keys())
        services_healthy = sum(1 for s in services if self._get_service_status(s) == "healthy")
        services_degraded = sum(1 for s in services if self._get_service_status(s) == "degraded")
        services_critical = sum(1 for s in services if self._get_service_status(s) == "critical")
        
        return DashboardOverview(
            total_logs=self._total_logs,
            total_anomalies=self._total_anomalies,
            total_alerts=self._total_alerts,
            total_remediations=self._total_remediations,
            logs_per_minute=round(logs_per_minute, 2),
            anomaly_rate=round(anomaly_rate, 4),
            error_rate=round(error_rate, 4),
            pipeline_status=self._pipeline_status,
            kafka_connected=self._kafka_connected,
            rag_connected=self._rag_connected,
            services_count=len(services),
            services_healthy=services_healthy,
            services_degraded=services_degraded,
            services_critical=services_critical,
            last_log_timestamp=self._last_log_timestamp,
            last_anomaly_timestamp=self._last_anomaly_timestamp,
            last_alert_timestamp=self._last_alert_timestamp,
            updated_at=now
        )
    
    def get_log_level_breakdown(self) -> LogLevelBreakdown:
        """Get log level breakdown."""
        return LogLevelBreakdown(
            debug=self._log_level_counts.get("DEBUG", 0),
            info=self._log_level_counts.get("INFO", 0),
            warning=self._log_level_counts.get("WARNING", 0),
            error=self._log_level_counts.get("ERROR", 0),
            critical=self._log_level_counts.get("CRITICAL", 0),
            total=self._total_logs
        )
    
    def _get_service_status(self, service: str) -> str:
        """Determine service health status."""
        stats = self._service_stats.get(service)
        if not stats:
            return "unknown"
        
        total = stats["total_logs"]
        if total == 0:
            return "healthy"
        
        error_rate = stats["error_count"] / total
        anomaly_rate = stats["anomaly_count"] / total
        
        if error_rate > 0.2 or anomaly_rate > 0.3:
            return "critical"
        elif error_rate > 0.1 or anomaly_rate > 0.1:
            return "degraded"
        return "healthy"
    
    def get_service_stats(self) -> List[ServiceStats]:
        """Get statistics for all services."""
        result = []
        for service, stats in self._service_stats.items():
            response_times = list(stats["response_times"])
            avg_response = sum(response_times) / len(response_times) if response_times else 0
            max_response = max(response_times) if response_times else 0
            
            total = stats["total_logs"]
            error_rate = stats["error_count"] / total if total else 0
            
            result.append(ServiceStats(
                name=service,
                total_logs=stats["total_logs"],
                error_count=stats["error_count"],
                warning_count=stats["warning_count"],
                anomaly_count=stats["anomaly_count"],
                error_rate=round(error_rate, 4),
                avg_response_time_ms=round(avg_response, 2),
                max_response_time_ms=round(max_response, 2),
                status=self._get_service_status(service)
            ))
        
        return sorted(result, key=lambda x: x.anomaly_count, reverse=True)
    
    def get_anomaly_metrics(self) -> AnomalyMetrics:
        """Get anomaly detection metrics."""
        anomaly_types = []
        for atype, count in self._anomaly_type_counts.items():
            scores = self._anomaly_type_scores.get(atype, [])
            avg_score = sum(scores) / len(scores) if scores else 0
            
            anomaly_types.append(AnomalyTypeStats(
                type=atype,
                count=count,
                percentage=count / self._total_anomalies if self._total_anomalies else 0,
                avg_score=round(avg_score, 3),
                last_seen=self._anomaly_type_last_seen.get(atype)
            ))
        
        anomaly_types.sort(key=lambda x: x.count, reverse=True)
        
        return AnomalyMetrics(
            total_anomalies=self._total_anomalies,
            anomalies_last_hour=self.metrics.get_recent_sum(self.metrics._anomaly_counts, 60),
            anomaly_rate=self._total_anomalies / self._total_logs if self._total_logs else 0,
            anomaly_types=anomaly_types,
            top_affected_services=self.get_service_stats()[:5],
            remediation_generated=self._total_remediations,
            avg_remediation_time_ms=0  # TODO: track this
        )
    
    def get_pipeline_metrics(self) -> PipelineMetrics:
        """Get streaming pipeline metrics."""
        uptime = 0
        if self._pipeline_start_time:
            uptime = (datetime.now() - self._pipeline_start_time).total_seconds()
        
        logs_last_min = self.metrics.get_recent_sum(self.metrics._log_counts, 1)
        logs_per_second = logs_last_min / 60 if logs_last_min else 0
        
        return PipelineMetrics(
            logs_per_second=round(logs_per_second, 2),
            total_logs_processed=self._total_logs,
            windows_processed=self._windows_processed,
            alerts_generated=self._total_alerts,
            avg_processing_latency_ms=50,  # TODO: track actual latency
            kafka_lag=0,  # TODO: get from Kafka
            uptime_seconds=uptime
        )
    
    def get_real_time_stats(self, window_seconds: int = 15) -> RealTimeStats:
        """Get real-time statistics for live updates."""
        window_minutes = window_seconds / 60
        
        return RealTimeStats(
            timestamp=datetime.now(),
            logs_in_window=self.metrics.get_recent_sum(self.metrics._log_counts, window_minutes),
            errors_in_window=self.metrics.get_recent_sum(self.metrics._error_counts, window_minutes),
            anomalies_in_window=self.metrics.get_recent_sum(self.metrics._anomaly_counts, window_minutes),
            avg_response_time=0,  # TODO: calculate
            active_services=len(self._service_stats),
            window_duration_seconds=window_seconds
        )
    
    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get most recent logs."""
        return list(self._recent_logs)[-limit:]
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent alerts."""
        return list(self._recent_alerts)[-limit:]
    
    def get_recent_remediations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent remediations."""
        return list(self._recent_remediations)[-limit:]
    
    def get_time_series(self, metric: str, time_range: TimeRange) -> TimeSeriesData:
        """Get time series data for a metric."""
        minutes_map = {
            TimeRange.LAST_5_MINUTES: 5,
            TimeRange.LAST_15_MINUTES: 15,
            TimeRange.LAST_30_MINUTES: 30,
            TimeRange.LAST_HOUR: 60,
            TimeRange.LAST_6_HOURS: 360,
            TimeRange.LAST_24_HOURS: 1440
        }
        minutes = minutes_map.get(time_range, 60)
        
        metric_deque_map = {
            "logs": self.metrics._log_counts,
            "errors": self.metrics._error_counts,
            "anomalies": self.metrics._anomaly_counts,
            "response_time": self.metrics._response_times
        }
        
        deque_data = metric_deque_map.get(metric, self.metrics._log_counts)
        data_points = self.metrics.get_time_series(deque_data, minutes)
        
        return TimeSeriesData(
            metric_name=metric,
            data_points=data_points,
            unit="count" if metric != "response_time" else "ms"
        )
    
    def get_analytics_summary(self, time_range: TimeRange = TimeRange.LAST_HOUR) -> AnalyticsSummary:
        """Get complete analytics summary."""
        return AnalyticsSummary(
            overview=self.get_dashboard_overview(),
            log_level_breakdown=self.get_log_level_breakdown(),
            service_stats=self.get_service_stats(),
            anomaly_metrics=self.get_anomaly_metrics(),
            pipeline_metrics=self.get_pipeline_metrics(),
            time_range=time_range,
            generated_at=datetime.now()
        )


# Global aggregator instance
aggregator = DataAggregator()
