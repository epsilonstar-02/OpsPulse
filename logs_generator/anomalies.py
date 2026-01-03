"""
Anomaly Generator - Creates various anomaly patterns in logs
"""
import random
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .models import LogEntry, LogLevel, AnomalyType
from .templates import MessageTemplates


@dataclass
class AnomalyState:
    """Tracks the current state of an ongoing anomaly"""
    anomaly_type: AnomalyType
    remaining_logs: int
    severity: float  # 0.0 to 1.0
    context: Dict[str, Any]


class AnomalyGenerator:
    """Generates various types of anomalies in log streams"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("anomalies", {})
        self.probability = self.config.get("probability", 0.05)
        self.types_config = self.config.get("types", {})
        self.current_anomaly: Optional[AnomalyState] = None
        
    def should_start_anomaly(self) -> bool:
        """Determine if a new anomaly should start"""
        if self.current_anomaly is not None:
            return False
        return random.random() < self.probability
    
    def select_anomaly_type(self) -> AnomalyType:
        """Select which type of anomaly to generate based on weights"""
        enabled_types = []
        weights = []
        
        type_mapping = {
            "error_spike": AnomalyType.ERROR_SPIKE,
            "latency_degradation": AnomalyType.LATENCY_DEGRADATION,
            "security_threat": AnomalyType.SECURITY_THREAT,
            "resource_exhaustion": AnomalyType.RESOURCE_EXHAUSTION,
            "service_outage": AnomalyType.SERVICE_OUTAGE,
            "data_anomaly": AnomalyType.DATA_ANOMALY,
        }
        
        for type_name, anomaly_type in type_mapping.items():
            type_config = self.types_config.get(type_name, {})
            if type_config.get("enabled", False):
                enabled_types.append(anomaly_type)
                weights.append(type_config.get("weight", 0.1))
        
        if not enabled_types:
            return AnomalyType.ERROR_SPIKE
        
        return random.choices(enabled_types, weights=weights, k=1)[0]
    
    def start_anomaly(self, anomaly_type: Optional[AnomalyType] = None) -> AnomalyState:
        """Start a new anomaly sequence"""
        if anomaly_type is None:
            anomaly_type = self.select_anomaly_type()
        
        type_key = anomaly_type.value
        type_config = self.types_config.get(type_key, {})
        
        duration = type_config.get("duration_logs", 20)
        
        context = self._build_anomaly_context(anomaly_type, type_config)
        
        self.current_anomaly = AnomalyState(
            anomaly_type=anomaly_type,
            remaining_logs=duration,
            severity=random.uniform(0.6, 1.0),
            context=context
        )
        
        return self.current_anomaly
    
    def _build_anomaly_context(self, anomaly_type: AnomalyType, config: Dict) -> Dict[str, Any]:
        """Build context data for the anomaly"""
        context = {
            "start_time": datetime.now(),
            "affected_service": random.choice([
                "auth-service", "payment-service", "user-service",
                "order-service", "inventory-service"
            ]),
        }
        
        if anomaly_type == AnomalyType.LATENCY_DEGRADATION:
            context["multiplier"] = config.get("multiplier", 5.0)
            context["base_latency"] = random.randint(100, 300)
            
        elif anomaly_type == AnomalyType.SECURITY_THREAT:
            threat_types = config.get("types", ["brute_force"])
            context["threat_type"] = random.choice(threat_types)
            context["source_ip"] = f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
            
        elif anomaly_type == AnomalyType.RESOURCE_EXHAUSTION:
            resources = config.get("resources", ["memory"])
            context["resource_type"] = random.choice(resources)
            context["usage_start"] = random.randint(70, 85)
            
        elif anomaly_type == AnomalyType.ERROR_SPIKE:
            context["error_rate"] = config.get("error_rate", 0.8)
            
        elif anomaly_type == AnomalyType.SERVICE_OUTAGE:
            context["outage_type"] = random.choice(["complete", "intermittent"])
            
        elif anomaly_type == AnomalyType.DATA_ANOMALY:
            data_types = config.get("types", ["null_values"])
            context["data_issue"] = random.choice(data_types)
        
        return context
    
    def generate_anomalous_log(
        self,
        timestamp: datetime,
        source: str,
        service: str
    ) -> LogEntry:
        """Generate a log entry that is part of the current anomaly"""
        if self.current_anomaly is None:
            # If no anomaly is active, start one
            self.start_anomaly()
        
        anomaly = self.current_anomaly
        anomaly.remaining_logs -= 1
        
        # Calculate progress through anomaly (0 = start, 1 = end)
        duration = self.types_config.get(anomaly.anomaly_type.value, {}).get("duration_logs", 20)
        progress = 1 - (anomaly.remaining_logs / max(duration, 1))  # Avoid division by zero
        
        log_entry = self._create_anomalous_entry(
            anomaly, timestamp, source, service, progress
        )
        
        # Check if anomaly should end
        if anomaly.remaining_logs <= 0:
            self.current_anomaly = None
        
        return log_entry
    
    def _create_anomalous_entry(
        self,
        anomaly: AnomalyState,
        timestamp: datetime,
        source: str,
        service: str,
        progress: float
    ) -> LogEntry:
        """Create a log entry for the specific anomaly type"""
        
        if anomaly.anomaly_type == AnomalyType.ERROR_SPIKE:
            return self._create_error_spike_log(anomaly, timestamp, source, service)
        
        elif anomaly.anomaly_type == AnomalyType.LATENCY_DEGRADATION:
            return self._create_latency_log(anomaly, timestamp, source, service, progress)
        
        elif anomaly.anomaly_type == AnomalyType.SECURITY_THREAT:
            return self._create_security_log(anomaly, timestamp, source, service)
        
        elif anomaly.anomaly_type == AnomalyType.RESOURCE_EXHAUSTION:
            return self._create_resource_log(anomaly, timestamp, source, service, progress)
        
        elif anomaly.anomaly_type == AnomalyType.SERVICE_OUTAGE:
            return self._create_outage_log(anomaly, timestamp, source, service)
        
        elif anomaly.anomaly_type == AnomalyType.DATA_ANOMALY:
            return self._create_data_anomaly_log(anomaly, timestamp, source, service)
        
        # Fallback
        return self._create_error_spike_log(anomaly, timestamp, source, service)
    
    def _create_error_spike_log(
        self,
        anomaly: AnomalyState,
        timestamp: datetime,
        source: str,
        service: str
    ) -> LogEntry:
        """Create error spike anomaly log"""
        error_rate = anomaly.context.get("error_rate", 0.8)
        
        if random.random() < error_rate:
            level = random.choices(
                [LogLevel.ERROR, LogLevel.CRITICAL],
                weights=[0.8, 0.2]
            )[0]
            message, context = MessageTemplates.get_message(source, level.value)
            status_code = MessageTemplates.get_status_code("server_error")
        else:
            level = LogLevel.WARNING
            message, context = MessageTemplates.get_message(source, "WARNING")
            status_code = MessageTemplates.get_status_code("client_error")
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            source=source,
            service=service,
            message=message,
            request_id=context.get("request_id"),
            ip_address=context.get("ip"),
            response_time_ms=random.uniform(1000, 5000),
            status_code=status_code,
            endpoint=MessageTemplates.get_endpoint(),
            method=MessageTemplates.get_method(),
            error_code=MessageTemplates.get_error_code() if level in [LogLevel.ERROR, LogLevel.CRITICAL] else None,
            is_anomaly=True,
            anomaly_type=AnomalyType.ERROR_SPIKE,
            anomaly_score=anomaly.severity
        )
    
    def _create_latency_log(
        self,
        anomaly: AnomalyState,
        timestamp: datetime,
        source: str,
        service: str,
        progress: float
    ) -> LogEntry:
        """Create latency degradation anomaly log"""
        multiplier = anomaly.context.get("multiplier", 5.0)
        base_latency = anomaly.context.get("base_latency", 150)
        
        # Latency increases with progress
        current_multiplier = 1 + (multiplier - 1) * progress
        response_time = base_latency * current_multiplier * random.uniform(0.8, 1.2)
        
        if response_time > 2000:
            level = LogLevel.ERROR
            message = f"Request timeout after {response_time:.0f}ms"
        elif response_time > 1000:
            level = LogLevel.WARNING
            message = f"Slow response detected: {response_time:.0f}ms"
        else:
            level = LogLevel.INFO
            message, _ = MessageTemplates.get_message(source, "INFO")
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            source=source,
            service=service,
            message=message,
            request_id=str(random.randint(100000, 999999)),
            response_time_ms=response_time,
            status_code=200 if level == LogLevel.INFO else 504,
            endpoint=MessageTemplates.get_endpoint(),
            method=MessageTemplates.get_method(),
            is_anomaly=True,
            anomaly_type=AnomalyType.LATENCY_DEGRADATION,
            anomaly_score=min(1.0, progress * anomaly.severity)
        )
    
    def _create_security_log(
        self,
        anomaly: AnomalyState,
        timestamp: datetime,
        source: str,
        service: str
    ) -> LogEntry:
        """Create security threat anomaly log"""
        threat_type = anomaly.context.get("threat_type", "brute_force")
        source_ip = anomaly.context.get("source_ip")
        
        message, context = MessageTemplates.get_security_message(threat_type)
        
        level = random.choices(
            [LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL],
            weights=[0.3, 0.5, 0.2]
        )[0]
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            source=source,
            service=service,
            message=message,
            request_id=context.get("request_id"),
            user_id=context.get("user_id"),
            ip_address=source_ip,
            endpoint=MessageTemplates.get_endpoint(),
            method=MessageTemplates.get_method(),
            status_code=random.choice([401, 403, 429]),
            metadata={"threat_type": threat_type},
            is_anomaly=True,
            anomaly_type=AnomalyType.SECURITY_THREAT,
            anomaly_score=anomaly.severity
        )
    
    def _create_resource_log(
        self,
        anomaly: AnomalyState,
        timestamp: datetime,
        source: str,
        service: str,
        progress: float
    ) -> LogEntry:
        """Create resource exhaustion anomaly log"""
        resource_type = anomaly.context.get("resource_type", "memory")
        usage_start = anomaly.context.get("usage_start", 75)
        
        # Usage increases with progress
        current_usage = min(99, usage_start + (99 - usage_start) * progress)
        
        message, context = MessageTemplates.get_resource_message(resource_type)
        
        if current_usage > 95:
            level = LogLevel.CRITICAL
        elif current_usage > 90:
            level = LogLevel.ERROR
        else:
            level = LogLevel.WARNING
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            source="infrastructure",
            service=service,
            message=message,
            metadata={
                "resource_type": resource_type,
                "usage_percent": current_usage
            },
            is_anomaly=True,
            anomaly_type=AnomalyType.RESOURCE_EXHAUSTION,
            anomaly_score=current_usage / 100
        )
    
    def _create_outage_log(
        self,
        anomaly: AnomalyState,
        timestamp: datetime,
        source: str,
        service: str
    ) -> LogEntry:
        """Create service outage anomaly log"""
        outage_type = anomaly.context.get("outage_type", "complete")
        affected_service = anomaly.context.get("affected_service")
        
        if outage_type == "complete":
            level = LogLevel.CRITICAL
            messages = [
                f"Service {affected_service} is not responding",
                f"Connection refused to {affected_service}",
                f"Health check failed for {affected_service}",
                f"Circuit breaker opened for {affected_service}",
            ]
        else:
            level = random.choice([LogLevel.ERROR, LogLevel.WARNING])
            messages = [
                f"Intermittent failures connecting to {affected_service}",
                f"Retry attempt for {affected_service}",
                f"Partial response from {affected_service}",
            ]
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            source=source,
            service=service,
            message=random.choice(messages),
            status_code=503,
            error_code="ERR_SERVICE_UNAVAILABLE",
            metadata={"affected_service": affected_service, "outage_type": outage_type},
            is_anomaly=True,
            anomaly_type=AnomalyType.SERVICE_OUTAGE,
            anomaly_score=anomaly.severity
        )
    
    def _create_data_anomaly_log(
        self,
        anomaly: AnomalyState,
        timestamp: datetime,
        source: str,
        service: str
    ) -> LogEntry:
        """Create data anomaly log"""
        data_issue = anomaly.context.get("data_issue", "null_values")
        
        messages = {
            "null_values": [
                "Unexpected null value in field: user_id",
                "Required field missing: transaction_id",
                "Null reference encountered in order processing",
            ],
            "out_of_range": [
                "Value out of expected range: amount=-500.00",
                "Invalid timestamp: date in future",
                "Quantity exceeds maximum: 999999",
            ],
            "format_error": [
                "Invalid date format in field: created_at",
                "Malformed JSON in request body",
                "Invalid email format: user@",
            ],
        }
        
        message = random.choice(messages.get(data_issue, messages["null_values"]))
        
        return LogEntry(
            timestamp=timestamp,
            level=LogLevel.ERROR,
            source=source,
            service=service,
            message=message,
            error_code="ERR_VALIDATION",
            metadata={"data_issue": data_issue},
            is_anomaly=True,
            anomaly_type=AnomalyType.DATA_ANOMALY,
            anomaly_score=anomaly.severity
        )
    
    @property
    def is_active(self) -> bool:
        """Check if there's an active anomaly"""
        return self.current_anomaly is not None
