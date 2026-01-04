"""
Log and alert models for the dashboard.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class LogLevel(str, Enum):
    """Log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AnomalyType(str, Enum):
    """Types of anomalies that can be detected."""
    NONE = "none"
    ERROR_SPIKE = "error_spike"
    LATENCY_DEGRADATION = "latency_degradation"
    SECURITY_THREAT = "security_threat"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SERVICE_OUTAGE = "service_outage"
    DATA_ANOMALY = "data_anomaly"


class LogLabels(BaseModel):
    """ML labels attached to log entries."""
    is_anomaly: bool = False
    anomaly_type: AnomalyType = AnomalyType.NONE
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)


class LogEntry(BaseModel):
    """A single log entry."""
    timestamp: datetime
    level: LogLevel
    source: str
    service: str
    message: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    response_time_ms: Optional[float] = None
    status_code: Optional[int] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    labels: Optional[LogLabels] = None


class LogBatch(BaseModel):
    """Batch of log entries."""
    logs: List[LogEntry]
    count: int
    anomaly_count: int
    start_time: datetime
    end_time: datetime


class Alert(BaseModel):
    """An anomaly alert from the pipeline."""
    id: str = Field(description="Unique alert identifier")
    timestamp: datetime
    service: str
    log_level: LogLevel
    total_logs: int
    anomaly_count: int
    avg_response_time_ms: float
    is_spike: bool
    alert_type: str
    severity: str = "warning"  # info, warning, critical
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class Remediation(BaseModel):
    """A remediation suggestion from RAG."""
    id: str
    alert_id: str
    timestamp: datetime
    service: str
    query_used: str
    remediation_text: str
    sources: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    applied: bool = False


class AlertWithRemediation(BaseModel):
    """Alert combined with its remediation suggestion."""
    alert: Alert
    remediation: Optional[Remediation] = None


class RecentActivity(BaseModel):
    """Recent activity feed item."""
    id: str
    timestamp: datetime
    type: str  # log, alert, remediation, system
    title: str
    description: str
    service: Optional[str] = None
    severity: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LogQuery(BaseModel):
    """Query parameters for log search."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    services: Optional[List[str]] = None
    levels: Optional[List[LogLevel]] = None
    anomaly_types: Optional[List[AnomalyType]] = None
    search_text: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class AlertQuery(BaseModel):
    """Query parameters for alert search."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    services: Optional[List[str]] = None
    alert_types: Optional[List[str]] = None
    severity: Optional[List[str]] = None
    acknowledged: Optional[bool] = None
    resolved: Optional[bool] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
