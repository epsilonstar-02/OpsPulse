"""
Log and Alert Routes for Dashboard Data Access.

Provides endpoints for:
- Recent logs retrieval
- Alert management
- Remediation history
- Log/Alert search and filtering
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Body
import httpx

from ..models.logs import (
    LogEntry, LogBatch, Alert, Remediation, AlertWithRemediation,
    RecentActivity, LogQuery, AlertQuery, LogLevel, AnomalyType
)
from ..services.data_aggregator import aggregator
from ..config import get_settings

router = APIRouter(prefix="/api", tags=["Logs & Alerts"])


# ============== Logs ==============

@router.get("/logs/recent", response_model=List[Dict[str, Any]])
async def get_recent_logs(
    limit: int = Query(default=100, ge=1, le=1000, description="Number of logs to return"),
    service: Optional[str] = Query(default=None, description="Filter by service name"),
    level: Optional[LogLevel] = Query(default=None, description="Filter by log level"),
    anomaly_only: bool = Query(default=False, description="Only return anomaly logs")
):
    """
    Get most recent log entries.
    
    Returns:
        List of recent log entries with optional filtering
    """
    logs = aggregator.get_recent_logs(limit * 2)  # Get extra for filtering
    
    # Apply filters
    if service:
        logs = [l for l in logs if l.get("service") == service]
    if level:
        logs = [l for l in logs if l.get("level") == level.value]
    if anomaly_only:
        logs = [l for l in logs if l.get("_labels", {}).get("is_anomaly")]
    
    return logs[:limit]


@router.get("/logs/stream")
async def get_log_stream_info():
    """
    Get information about the log stream.
    
    Returns:
        Stream statistics and connection info
    """
    overview = aggregator.get_dashboard_overview()
    
    return {
        "stream_active": overview.pipeline_status == "running",
        "kafka_connected": overview.kafka_connected,
        "logs_per_minute": overview.logs_per_minute,
        "total_logs": overview.total_logs,
        "last_log_timestamp": overview.last_log_timestamp.isoformat() if overview.last_log_timestamp else None,
        "websocket_url": "/ws/logs"
    }


@router.post("/logs/generate")
async def trigger_log_generation(
    count: int = Query(default=100, ge=1, le=10000),
    anomaly_rate: float = Query(default=0.05, ge=0.0, le=1.0)
):
    """
    Trigger log generation from the log generator.
    
    Args:
        count: Number of logs to generate
        anomaly_rate: Probability of anomalies
        
    Returns:
        Generated logs summary
    """
    settings = get_settings()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.LOG_GENERATOR_URL}/api/generate",
                json={
                    "count": count,
                    "anomaly_rate": anomaly_rate,
                    "include_labels": True,
                    "format": "json"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Record logs in aggregator
            for log in data.get("logs", []):
                aggregator.record_log(log)
            
            return {
                "success": True,
                "count": data.get("count", 0),
                "anomaly_count": data.get("anomaly_count", 0),
                "message": f"Generated {data.get('count', 0)} logs"
            }
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Log generator service unavailable"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Alerts ==============

@router.get("/alerts/recent", response_model=List[Dict[str, Any]])
async def get_recent_alerts(
    limit: int = Query(default=50, ge=1, le=500, description="Number of alerts to return"),
    service: Optional[str] = Query(default=None, description="Filter by service name"),
    severity: Optional[str] = Query(default=None, description="Filter by severity")
):
    """
    Get most recent alerts.
    
    Returns:
        List of recent alerts with optional filtering
    """
    alerts = aggregator.get_recent_alerts(limit * 2)
    
    if service:
        alerts = [a for a in alerts if a.get("service") == service]
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    
    return alerts[:limit]


@router.get("/alerts/{alert_id}")
async def get_alert_by_id(alert_id: str):
    """
    Get a specific alert by ID.
    
    Args:
        alert_id: Alert identifier
        
    Returns:
        Alert details with remediation if available
    """
    alerts = aggregator.get_recent_alerts(500)
    
    for alert in alerts:
        if alert.get("id") == alert_id:
            # Look for remediation
            remediations = aggregator.get_recent_remediations(100)
            remediation = next(
                (r for r in remediations if r.get("alert_id") == alert_id),
                None
            )
            return {
                "alert": alert,
                "remediation": remediation
            }
    
    raise HTTPException(status_code=404, detail="Alert not found")


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """
    Acknowledge an alert.
    
    Args:
        alert_id: Alert identifier
        
    Returns:
        Acknowledgement confirmation
    """
    # In a real implementation, this would update the alert in a database
    return {
        "alert_id": alert_id,
        "acknowledged": True,
        "acknowledged_at": datetime.now().isoformat()
    }


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, notes: str = Body(default="")):
    """
    Mark an alert as resolved.
    
    Args:
        alert_id: Alert identifier
        notes: Resolution notes
        
    Returns:
        Resolution confirmation
    """
    return {
        "alert_id": alert_id,
        "resolved": True,
        "resolved_at": datetime.now().isoformat(),
        "notes": notes
    }


# ============== Remediations ==============

@router.get("/remediations/recent", response_model=List[Dict[str, Any]])
async def get_recent_remediations(
    limit: int = Query(default=50, ge=1, le=200, description="Number of remediations to return")
):
    """
    Get most recent remediation suggestions.
    
    Returns:
        List of recent remediations from RAG
    """
    return aggregator.get_recent_remediations(limit)


@router.post("/remediations/query")
async def query_remediation(
    query: str = Body(..., embed=True),
    service: Optional[str] = Body(default=None)
):
    """
    Query the RAG system for remediation suggestions.
    
    Args:
        query: Natural language query
        service: Optional service context
        
    Returns:
        Remediation suggestions from RAG
    """
    settings = get_settings()
    
    full_query = query
    if service:
        full_query = f"For {service} service: {query}"
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.RAG_SERVER_URL}/query",
                json={"query": full_query}
            )
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="RAG server unavailable"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Activity Feed ==============

@router.get("/activity/recent")
async def get_recent_activity(
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    Get recent activity feed combining logs, alerts, and remediations.
    
    Returns:
        Combined activity feed sorted by time
    """
    activities = []
    
    # Add recent logs (sample)
    for log in aggregator.get_recent_logs(20):
        labels = log.get("_labels", {})
        if labels.get("is_anomaly"):
            activities.append({
                "id": log.get("request_id", ""),
                "timestamp": log.get("timestamp"),
                "type": "anomaly",
                "title": f"Anomaly in {log.get('service')}",
                "description": log.get("message", "")[:200],
                "service": log.get("service"),
                "severity": "warning" if log.get("level") in ("ERROR", "CRITICAL") else "info"
            })
    
    # Add recent alerts
    for alert in aggregator.get_recent_alerts(20):
        activities.append({
            "id": alert.get("id", ""),
            "timestamp": alert.get("timestamp"),
            "type": "alert",
            "title": f"Alert: {alert.get('alert_type', 'unknown')}",
            "description": f"{alert.get('anomaly_count', 0)} anomalies detected in {alert.get('service')}",
            "service": alert.get("service"),
            "severity": "critical" if alert.get("is_spike") else "warning"
        })
    
    # Add recent remediations
    for rem in aggregator.get_recent_remediations(10):
        activities.append({
            "id": rem.get("id", ""),
            "timestamp": rem.get("received_at"),
            "type": "remediation",
            "title": "Remediation Generated",
            "description": rem.get("remediation_text", "")[:200] if rem.get("remediation_text") else "Remediation available",
            "service": rem.get("service"),
            "severity": "info"
        })
    
    # Sort by timestamp
    activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return activities[:limit]


# ============== Stats ==============

@router.get("/stats/summary")
async def get_stats_summary():
    """
    Get a quick stats summary.
    
    Returns:
        Key statistics at a glance
    """
    overview = aggregator.get_dashboard_overview()
    level_breakdown = aggregator.get_log_level_breakdown()
    
    return {
        "totals": {
            "logs": overview.total_logs,
            "anomalies": overview.total_anomalies,
            "alerts": overview.total_alerts,
            "remediations": overview.total_remediations
        },
        "rates": {
            "logs_per_minute": overview.logs_per_minute,
            "anomaly_rate": overview.anomaly_rate,
            "error_rate": overview.error_rate
        },
        "log_levels": {
            "debug": level_breakdown.debug,
            "info": level_breakdown.info,
            "warning": level_breakdown.warning,
            "error": level_breakdown.error,
            "critical": level_breakdown.critical
        },
        "services": {
            "total": overview.services_count,
            "healthy": overview.services_healthy,
            "degraded": overview.services_degraded,
            "critical": overview.services_critical
        },
        "pipeline": {
            "status": overview.pipeline_status,
            "kafka_connected": overview.kafka_connected,
            "rag_connected": overview.rag_connected
        },
        "updated_at": overview.updated_at.isoformat()
    }
