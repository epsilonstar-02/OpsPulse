"""
WebSocket models for real-time communication.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


class WSMessageType(str, Enum):
    """WebSocket message types."""
    # Client -> Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    
    # Server -> Client
    LOG = "log"
    ALERT = "alert"
    REMEDIATION = "remediation"
    STATS = "stats"
    HEALTH = "health"
    PONG = "pong"
    ERROR = "error"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"


class WSChannel(str, Enum):
    """Available WebSocket subscription channels."""
    LOGS = "logs"
    ALERTS = "alerts"
    REMEDIATIONS = "remediations"
    STATS = "stats"
    HEALTH = "health"
    PIPELINE = "pipeline"
    ALL = "all"


class WSSubscribeMessage(BaseModel):
    """Message to subscribe to channels."""
    type: WSMessageType = WSMessageType.SUBSCRIBE
    channels: List[WSChannel]
    filters: Optional[Dict[str, Any]] = None


class WSUnsubscribeMessage(BaseModel):
    """Message to unsubscribe from channels."""
    type: WSMessageType = WSMessageType.UNSUBSCRIBE
    channels: List[WSChannel]


class WSLogMessage(BaseModel):
    """Log message sent via WebSocket."""
    type: WSMessageType = WSMessageType.LOG
    timestamp: datetime
    data: Dict[str, Any]


class WSAlertMessage(BaseModel):
    """Alert message sent via WebSocket."""
    type: WSMessageType = WSMessageType.ALERT
    timestamp: datetime
    alert_id: str
    service: str
    alert_type: str
    severity: str
    data: Dict[str, Any]


class WSRemediationMessage(BaseModel):
    """Remediation message sent via WebSocket."""
    type: WSMessageType = WSMessageType.REMEDIATION
    timestamp: datetime
    alert_id: str
    remediation_preview: str
    data: Dict[str, Any]


class WSStatsMessage(BaseModel):
    """Real-time statistics message."""
    type: WSMessageType = WSMessageType.STATS
    timestamp: datetime
    logs_per_second: float
    errors_per_second: float
    anomalies_per_second: float
    active_services: int
    pipeline_status: str
    data: Dict[str, Any] = Field(default_factory=dict)


class WSHealthMessage(BaseModel):
    """Health update message."""
    type: WSMessageType = WSMessageType.HEALTH
    timestamp: datetime
    component: str
    status: str
    message: Optional[str] = None


class WSErrorMessage(BaseModel):
    """Error message from server."""
    type: WSMessageType = WSMessageType.ERROR
    timestamp: datetime = Field(default_factory=datetime.now)
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class WSPongMessage(BaseModel):
    """Pong response to ping."""
    type: WSMessageType = WSMessageType.PONG
    timestamp: datetime = Field(default_factory=datetime.now)
    server_time: datetime = Field(default_factory=datetime.now)


class WSClientInfo(BaseModel):
    """Information about a connected WebSocket client."""
    client_id: str
    connected_at: datetime
    subscribed_channels: List[WSChannel]
    filters: Dict[str, Any] = Field(default_factory=dict)
    messages_sent: int = 0
    last_activity: datetime


class WSConnectionStats(BaseModel):
    """WebSocket connection statistics."""
    total_connections: int
    active_connections: int
    total_messages_sent: int
    channels: Dict[str, int]  # channel -> subscriber count
