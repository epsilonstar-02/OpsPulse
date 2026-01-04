"""
Analytics Routes for Dashboard Metrics and Statistics.

Provides endpoints for:
- Dashboard overview
- Service statistics
- Anomaly metrics
- Pipeline performance
- Time series data for charts
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException

from ..models.analytics import (
    DashboardOverview, LogLevelBreakdown, ServiceStats, AnomalyMetrics,
    PipelineMetrics, RealTimeStats, TimeSeriesData, TimeRange,
    AnalyticsSummary, ChartData
)
from ..services.data_aggregator import aggregator

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview():
    """
    Get main dashboard overview with key metrics.
    
    Returns:
        Dashboard overview including totals, rates, and service health
    """
    return aggregator.get_dashboard_overview()


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    time_range: TimeRange = Query(default=TimeRange.LAST_HOUR, description="Time range for analytics")
):
    """
    Get complete analytics summary for the dashboard.
    
    Returns:
        Full analytics summary including all metrics and statistics
    """
    return aggregator.get_analytics_summary(time_range)


@router.get("/log-levels", response_model=LogLevelBreakdown)
async def get_log_level_breakdown():
    """
    Get breakdown of logs by severity level.
    
    Returns:
        Count of logs at each severity level
    """
    return aggregator.get_log_level_breakdown()


@router.get("/services", response_model=List[ServiceStats])
async def get_service_statistics(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum services to return"),
    sort_by: str = Query(default="anomaly_count", description="Sort by: anomaly_count, error_count, total_logs")
):
    """
    Get statistics for all monitored services.
    
    Returns:
        List of service statistics sorted by specified criteria
    """
    stats = aggregator.get_service_stats()
    
    # Sort by requested field
    sort_fields = {
        "anomaly_count": lambda x: x.anomaly_count,
        "error_count": lambda x: x.error_count,
        "total_logs": lambda x: x.total_logs,
        "error_rate": lambda x: x.error_rate,
        "response_time": lambda x: x.avg_response_time_ms
    }
    
    sort_fn = sort_fields.get(sort_by, sort_fields["anomaly_count"])
    stats = sorted(stats, key=sort_fn, reverse=True)
    
    return stats[:limit]


@router.get("/services/{service_name}", response_model=ServiceStats)
async def get_service_details(service_name: str):
    """
    Get detailed statistics for a specific service.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Service statistics
    """
    stats = aggregator.get_service_stats()
    for stat in stats:
        if stat.name == service_name:
            return stat
    
    raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")


@router.get("/anomalies", response_model=AnomalyMetrics)
async def get_anomaly_metrics():
    """
    Get anomaly detection metrics and statistics.
    
    Returns:
        Comprehensive anomaly metrics including types and affected services
    """
    return aggregator.get_anomaly_metrics()


@router.get("/pipeline", response_model=PipelineMetrics)
async def get_pipeline_metrics():
    """
    Get streaming pipeline performance metrics.
    
    Returns:
        Pipeline metrics including throughput, latency, and processing stats
    """
    return aggregator.get_pipeline_metrics()


@router.get("/realtime", response_model=RealTimeStats)
async def get_realtime_stats(
    window_seconds: int = Query(default=15, ge=5, le=300, description="Window size in seconds")
):
    """
    Get real-time statistics for live dashboard updates.
    
    Args:
        window_seconds: Size of the time window in seconds
        
    Returns:
        Statistics for the specified time window
    """
    return aggregator.get_real_time_stats(window_seconds)


@router.get("/timeseries/{metric}", response_model=TimeSeriesData)
async def get_time_series(
    metric: str,
    time_range: TimeRange = Query(default=TimeRange.LAST_HOUR, description="Time range for data")
):
    """
    Get time series data for a specific metric.
    
    Args:
        metric: Metric name (logs, errors, anomalies, response_time)
        time_range: Time range for the data
        
    Returns:
        Time series data points for charting
    """
    valid_metrics = ["logs", "errors", "anomalies", "response_time"]
    if metric not in valid_metrics:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid metric. Valid options: {valid_metrics}"
        )
    
    return aggregator.get_time_series(metric, time_range)


@router.get("/charts/log-rate", response_model=ChartData)
async def get_log_rate_chart(
    time_range: TimeRange = Query(default=TimeRange.LAST_HOUR)
):
    """
    Get log rate data formatted for charts.
    
    Returns:
        Chart data with log counts over time
    """
    logs_ts = aggregator.get_time_series("logs", time_range)
    errors_ts = aggregator.get_time_series("errors", time_range)
    
    return ChartData(
        chart_type="area",
        title="Log Volume Over Time",
        series=[logs_ts, errors_ts],
        x_axis_label="Time",
        y_axis_label="Log Count",
        time_range=time_range
    )


@router.get("/charts/anomaly-distribution")
async def get_anomaly_distribution_chart():
    """
    Get anomaly type distribution for pie/donut charts.
    
    Returns:
        Anomaly counts by type
    """
    metrics = aggregator.get_anomaly_metrics()
    
    return {
        "chart_type": "pie",
        "title": "Anomaly Distribution by Type",
        "data": [
            {"name": at.type, "value": at.count}
            for at in metrics.anomaly_types
        ]
    }


@router.get("/charts/service-health")
async def get_service_health_chart():
    """
    Get service health distribution for charts.
    
    Returns:
        Service count by health status
    """
    overview = aggregator.get_dashboard_overview()
    
    return {
        "chart_type": "donut",
        "title": "Service Health Overview",
        "data": [
            {"name": "Healthy", "value": overview.services_healthy, "color": "#22c55e"},
            {"name": "Degraded", "value": overview.services_degraded, "color": "#f59e0b"},
            {"name": "Critical", "value": overview.services_critical, "color": "#ef4444"}
        ]
    }


@router.get("/charts/error-rate", response_model=ChartData)
async def get_error_rate_chart(
    time_range: TimeRange = Query(default=TimeRange.LAST_HOUR)
):
    """
    Get error rate data formatted for line charts.
    
    Returns:
        Chart data with error rates over time
    """
    errors_ts = aggregator.get_time_series("errors", time_range)
    anomalies_ts = aggregator.get_time_series("anomalies", time_range)
    
    return ChartData(
        chart_type="line",
        title="Error & Anomaly Rate",
        series=[errors_ts, anomalies_ts],
        x_axis_label="Time",
        y_axis_label="Count",
        time_range=time_range
    )
