"""
System Health and Management Routes.

Provides endpoints for:
- System health checks
- Component status
- System information
- Component management actions
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..models.system import (
    ComponentHealth, ComponentStatus, ComponentType, SystemHealth,
    SystemInfo, ComponentAction, ComponentActionResult
)
from ..services.health_checker import health_checker

router = APIRouter(prefix="/api/system", tags=["System"])


@router.get("/health", response_model=SystemHealth)
async def get_system_health():
    """
    Get comprehensive system health status.
    
    Checks all components and returns aggregated health information.
    
    Returns:
        Complete system health including all components
    """
    return await health_checker.get_system_health()


@router.get("/health/simple")
async def get_simple_health():
    """
    Simple health check endpoint for load balancers.
    
    Returns:
        Simple OK status if API is running
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "opspulse-dashboard-api"
    }


@router.get("/info", response_model=SystemInfo)
async def get_system_info():
    """
    Get system information.
    
    Returns:
        System info including version, environment, and uptime
    """
    return health_checker.get_system_info()


@router.get("/components", response_model=List[ComponentHealth])
async def get_all_components():
    """
    Get health status of all components.
    
    Returns:
        List of component health statuses
    """
    return await health_checker.check_all_components()


@router.get("/components/{component_type}", response_model=ComponentHealth)
async def get_component_health(component_type: str):
    """
    Get health status of a specific component.
    
    Args:
        component_type: Type of component to check
        
    Returns:
        Component health status
    """
    try:
        comp_type = ComponentType(component_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid component type. Valid types: {[t.value for t in ComponentType]}"
        )
    
    # Check the specific component
    if comp_type == ComponentType.LOG_GENERATOR:
        return await health_checker.check_log_generator()
    elif comp_type == ComponentType.RAG_SERVER:
        return await health_checker.check_rag_server()
    elif comp_type == ComponentType.DEEPSEEK_LLM:
        return await health_checker.check_deepseek()
    elif comp_type in (ComponentType.KAFKA_PRODUCER, ComponentType.PATHWAY_CONSUMER):
        return await health_checker.check_kafka()
    else:
        raise HTTPException(status_code=400, detail="Component check not implemented")


@router.post("/components/{component_type}/check", response_model=ComponentHealth)
async def check_component(component_type: str):
    """
    Force a health check on a specific component.
    
    Args:
        component_type: Type of component to check
        
    Returns:
        Updated component health status
    """
    return await get_component_health(component_type)


@router.get("/status")
async def get_quick_status():
    """
    Get a quick status overview for monitoring.
    
    Returns:
        Quick status with essential metrics
    """
    health = await health_checker.get_system_health()
    
    return {
        "status": health.status.value,
        "uptime_seconds": health.uptime_seconds,
        "components": {
            c.name: c.status.value for c in health.components
        },
        "last_updated": health.last_updated.isoformat()
    }


@router.get("/config")
async def get_system_config():
    """
    Get current system configuration (non-sensitive).
    
    Returns:
        System configuration details
    """
    from ..config import get_settings
    settings = get_settings()
    
    return {
        "api": {
            "title": settings.API_TITLE,
            "version": settings.API_VERSION,
            "host": settings.HOST,
            "port": settings.PORT,
            "debug": settings.DEBUG
        },
        "components": {
            "log_generator_url": settings.LOG_GENERATOR_URL,
            "rag_server_url": settings.RAG_SERVER_URL,
            "deepseek_url": settings.DEEPSEEK_URL,
            "kafka_servers": settings.KAFKA_BOOTSTRAP_SERVERS
        },
        "kafka_topics": {
            "raw_logs": settings.KAFKA_RAW_LOGS_TOPIC,
            "alerts": settings.KAFKA_ALERTS_TOPIC,
            "remediation": settings.KAFKA_REMEDIATION_TOPIC
        },
        "websocket": {
            "heartbeat_interval": settings.WS_HEARTBEAT_INTERVAL,
            "max_connections": settings.WS_MAX_CONNECTIONS
        },
        "data_retention": {
            "metrics_history_minutes": settings.METRICS_HISTORY_MINUTES,
            "max_recent_logs": settings.MAX_RECENT_LOGS,
            "max_recent_alerts": settings.MAX_RECENT_ALERTS
        }
    }


@router.get("/metrics")
async def get_prometheus_metrics():
    """
    Get metrics in Prometheus format for monitoring.
    
    Returns:
        Prometheus-compatible metrics
    """
    from ..services.data_aggregator import aggregator
    
    overview = aggregator.get_dashboard_overview()
    pipeline = aggregator.get_pipeline_metrics()
    
    # Format as Prometheus metrics
    lines = [
        "# HELP opspulse_total_logs Total logs processed",
        "# TYPE opspulse_total_logs counter",
        f"opspulse_total_logs {overview.total_logs}",
        "",
        "# HELP opspulse_total_anomalies Total anomalies detected",
        "# TYPE opspulse_total_anomalies counter",
        f"opspulse_total_anomalies {overview.total_anomalies}",
        "",
        "# HELP opspulse_total_alerts Total alerts generated",
        "# TYPE opspulse_total_alerts counter",
        f"opspulse_total_alerts {overview.total_alerts}",
        "",
        "# HELP opspulse_logs_per_minute Current log ingestion rate",
        "# TYPE opspulse_logs_per_minute gauge",
        f"opspulse_logs_per_minute {overview.logs_per_minute}",
        "",
        "# HELP opspulse_anomaly_rate Current anomaly rate",
        "# TYPE opspulse_anomaly_rate gauge",
        f"opspulse_anomaly_rate {overview.anomaly_rate}",
        "",
        "# HELP opspulse_error_rate Current error rate",
        "# TYPE opspulse_error_rate gauge",
        f"opspulse_error_rate {overview.error_rate}",
        "",
        "# HELP opspulse_services_total Total services monitored",
        "# TYPE opspulse_services_total gauge",
        f"opspulse_services_total {overview.services_count}",
        "",
        "# HELP opspulse_services_healthy Healthy services count",
        "# TYPE opspulse_services_healthy gauge",
        f"opspulse_services_healthy {overview.services_healthy}",
        "",
        "# HELP opspulse_pipeline_logs_per_second Pipeline throughput",
        "# TYPE opspulse_pipeline_logs_per_second gauge",
        f"opspulse_pipeline_logs_per_second {pipeline.logs_per_second}",
        "",
        "# HELP opspulse_pipeline_uptime_seconds Pipeline uptime",
        "# TYPE opspulse_pipeline_uptime_seconds gauge",
        f"opspulse_pipeline_uptime_seconds {pipeline.uptime_seconds}",
    ]
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines), media_type="text/plain")
