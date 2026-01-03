"""
Log Models - Data classes for log entries
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import json


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AnomalyType(Enum):
    NONE = "none"
    ERROR_SPIKE = "error_spike"
    LATENCY_DEGRADATION = "latency_degradation"
    SECURITY_THREAT = "security_threat"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SERVICE_OUTAGE = "service_outage"
    DATA_ANOMALY = "data_anomaly"


@dataclass
class LogEntry:
    """Represents a single log entry"""
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
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Labels for ML training
    is_anomaly: bool = False
    anomaly_type: AnomalyType = AnomalyType.NONE
    anomaly_score: float = 0.0
    
    def to_dict(self, include_labels: bool = True) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "source": self.source,
            "service": self.service,
            "message": self.message,
        }
        
        # Add optional fields if present
        optional_fields = [
            "request_id", "user_id", "ip_address", "response_time_ms",
            "status_code", "endpoint", "method", "error_code", "stack_trace"
        ]
        for field_name in optional_fields:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        
        if self.metadata:
            result["metadata"] = self.metadata
        
        if include_labels:
            result["_labels"] = {
                "is_anomaly": self.is_anomaly,
                "anomaly_type": self.anomaly_type.value,
                "anomaly_score": self.anomaly_score
            }
        
        return result
    
    def to_json(self, include_labels: bool = True) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(include_labels))
    
    def to_text(self, include_labels: bool = True) -> str:
        """Convert to human-readable text format"""
        parts = [
            f"[{self.timestamp.isoformat()}]",
            f"[{self.level.value:8}]",
            f"[{self.source}/{self.service}]",
        ]
        
        if self.request_id:
            parts.append(f"[{self.request_id[:8]}]")
        
        parts.append(self.message)
        
        if self.response_time_ms:
            parts.append(f"({self.response_time_ms:.2f}ms)")
        
        if self.status_code:
            parts.append(f"[{self.status_code}]")
        
        text = " ".join(parts)
        
        if include_labels and self.is_anomaly:
            text += f" [ANOMALY:{self.anomaly_type.value}:{self.anomaly_score:.2f}]"
        
        return text
