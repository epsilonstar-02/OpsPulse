"""
System health and component status models.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ComponentStatus(str, Enum):
    """Status of a system component."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """Type of system component."""
    LOG_GENERATOR = "log_generator"
    KAFKA_PRODUCER = "kafka_producer"
    PATHWAY_CONSUMER = "pathway_consumer"
    RAG_SERVER = "rag_server"
    DEEPSEEK_LLM = "deepseek_llm"
    CHROMADB = "chromadb"


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    name: str
    type: ComponentType
    status: ComponentStatus
    url: Optional[str] = None
    last_check: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KafkaTopicStats(BaseModel):
    """Statistics for a Kafka topic."""
    topic_name: str
    partition_count: int
    message_count: int
    consumer_lag: int
    messages_per_second: float
    last_message_timestamp: Optional[datetime] = None


class KafkaHealth(BaseModel):
    """Kafka/Redpanda cluster health."""
    connected: bool
    broker_count: int
    topics: List[KafkaTopicStats]
    total_lag: int
    error_message: Optional[str] = None


class RAGHealth(BaseModel):
    """RAG server health and statistics."""
    status: ComponentStatus
    document_count: int
    chunk_count: int
    embedding_model: str
    llm_model: str
    llm_connected: bool
    queries_processed: int
    avg_query_time_ms: float
    last_query_timestamp: Optional[datetime] = None


class LogGeneratorHealth(BaseModel):
    """Log generator health and statistics."""
    status: ComponentStatus
    is_streaming: bool
    logs_generated: int
    anomalies_generated: int
    anomaly_rate: float
    start_time: Optional[datetime] = None
    current_anomaly_active: bool = False


class PathwayHealth(BaseModel):
    """Pathway consumer health."""
    status: ComponentStatus
    is_running: bool
    windows_processed: int
    alerts_generated: int
    logs_seen: int
    avg_processing_time_ms: float
    last_window_timestamp: Optional[datetime] = None


class SystemHealth(BaseModel):
    """Overall system health summary."""
    status: ComponentStatus
    components: List[ComponentHealth]
    kafka: Optional[KafkaHealth] = None
    rag: Optional[RAGHealth] = None
    log_generator: Optional[LogGeneratorHealth] = None
    pathway: Optional[PathwayHealth] = None
    uptime_seconds: float
    last_updated: datetime = Field(default_factory=datetime.now)


class SystemInfo(BaseModel):
    """System information."""
    version: str
    environment: str
    python_version: str
    host: str
    port: int
    start_time: datetime
    uptime_seconds: float


class ComponentAction(BaseModel):
    """Action to perform on a component."""
    component: ComponentType
    action: str  # start, stop, restart, health_check
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ComponentActionResult(BaseModel):
    """Result of a component action."""
    component: ComponentType
    action: str
    success: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
