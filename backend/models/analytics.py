"""
Analytics models for dashboard metrics and statistics.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TimeRange(str, Enum):
    """Time range options for analytics queries."""
    LAST_5_MINUTES = "5m"
    LAST_15_MINUTES = "15m"
    LAST_30_MINUTES = "30m"
    LAST_HOUR = "1h"
    LAST_6_HOURS = "6h"
    LAST_24_HOURS = "24h"


class AnomalyTypeStats(BaseModel):
    """Statistics for a specific anomaly type."""
    type: str
    count: int
    percentage: float
    avg_score: float
    last_seen: Optional[datetime] = None


class ServiceStats(BaseModel):
    """Statistics for a specific service."""
    name: str
    total_logs: int
    error_count: int
    warning_count: int
    anomaly_count: int
    error_rate: float = Field(ge=0, le=1)
    avg_response_time_ms: float
    max_response_time_ms: float
    status: str = "healthy"  # healthy, degraded, critical


class LogLevelBreakdown(BaseModel):
    """Breakdown of log levels."""
    debug: int = 0
    info: int = 0
    warning: int = 0
    error: int = 0
    critical: int = 0
    total: int = 0


class TimeSeriesDataPoint(BaseModel):
    """Single data point in a time series."""
    timestamp: datetime
    value: float
    label: Optional[str] = None


class TimeSeriesData(BaseModel):
    """Time series data for charts."""
    metric_name: str
    data_points: List[TimeSeriesDataPoint]
    unit: Optional[str] = None


class PipelineMetrics(BaseModel):
    """Metrics for the streaming pipeline."""
    logs_per_second: float
    total_logs_processed: int
    windows_processed: int
    alerts_generated: int
    avg_processing_latency_ms: float
    kafka_lag: int
    uptime_seconds: float


class AnomalyMetrics(BaseModel):
    """Overall anomaly detection metrics."""
    total_anomalies: int
    anomalies_last_hour: int
    anomaly_rate: float = Field(ge=0, le=1, description="Anomalies per log")
    anomaly_types: List[AnomalyTypeStats]
    top_affected_services: List[ServiceStats]
    remediation_generated: int
    avg_remediation_time_ms: float


class DashboardOverview(BaseModel):
    """Main dashboard overview data."""
    # Totals
    total_logs: int
    total_anomalies: int
    total_alerts: int
    total_remediations: int
    
    # Rates
    logs_per_minute: float
    anomaly_rate: float
    error_rate: float
    
    # Pipeline Health
    pipeline_status: str  # running, stopped, error
    kafka_connected: bool
    rag_connected: bool
    
    # Services
    services_count: int
    services_healthy: int
    services_degraded: int
    services_critical: int
    
    # Recent Activity
    last_log_timestamp: Optional[datetime] = None
    last_anomaly_timestamp: Optional[datetime] = None
    last_alert_timestamp: Optional[datetime] = None
    
    # Updated
    updated_at: datetime = Field(default_factory=datetime.now)


class RealTimeStats(BaseModel):
    """Real-time statistics for live updates."""
    timestamp: datetime
    logs_in_window: int
    errors_in_window: int
    anomalies_in_window: int
    avg_response_time: float
    active_services: int
    window_duration_seconds: int = 15


class AnalyticsSummary(BaseModel):
    """Complete analytics summary for the dashboard."""
    overview: DashboardOverview
    log_level_breakdown: LogLevelBreakdown
    service_stats: List[ServiceStats]
    anomaly_metrics: AnomalyMetrics
    pipeline_metrics: PipelineMetrics
    time_range: TimeRange
    generated_at: datetime = Field(default_factory=datetime.now)


class ChartData(BaseModel):
    """Data formatted for dashboard charts."""
    chart_type: str  # line, bar, pie, area
    title: str
    series: List[TimeSeriesData]
    x_axis_label: str
    y_axis_label: str
    time_range: TimeRange
