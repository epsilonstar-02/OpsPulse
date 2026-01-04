"""
Health Checker Service for OpsPulse Components.

Performs health checks on all system components:
- Log Generator API
- RAG Server
- DeepSeek LLM
- Kafka/Redpanda
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import httpx

from ..config import get_settings, get_kafka_config
from ..models.system import (
    ComponentHealth, ComponentStatus, ComponentType, SystemHealth,
    KafkaHealth, KafkaTopicStats, RAGHealth, LogGeneratorHealth,
    PathwayHealth, SystemInfo
)

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Performs health checks on all OpsPulse components.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._start_time = datetime.now()
        self._last_check: Dict[str, datetime] = {}
        self._component_status: Dict[str, ComponentHealth] = {}
    
    async def check_http_endpoint(
        self, 
        url: str, 
        timeout: float = 5.0,
        expected_status: int = 200
    ) -> tuple[ComponentStatus, Optional[float], Optional[str]]:
        """
        Check an HTTP endpoint health.
        
        Returns:
            (status, response_time_ms, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                start = datetime.now()
                response = await client.get(url)
                elapsed = (datetime.now() - start).total_seconds() * 1000
                
                if response.status_code == expected_status:
                    return ComponentStatus.HEALTHY, elapsed, None
                else:
                    return ComponentStatus.DEGRADED, elapsed, f"Status {response.status_code}"
        except httpx.TimeoutException:
            return ComponentStatus.UNHEALTHY, None, "Timeout"
        except httpx.ConnectError:
            return ComponentStatus.UNHEALTHY, None, "Connection refused"
        except Exception as e:
            return ComponentStatus.UNHEALTHY, None, str(e)
    
    async def check_log_generator(self) -> ComponentHealth:
        """Check log generator health."""
        url = f"{self.settings.LOG_GENERATOR_URL}/api/status"
        status, response_time, error = await self.check_http_endpoint(url)
        
        metadata = {}
        if status == ComponentStatus.HEALTHY:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url)
                    data = response.json()
                    metadata = {
                        "is_running": data.get("is_running", False),
                        "logs_generated": data.get("logs_generated", 0),
                        "anomalies_generated": data.get("anomalies_generated", 0)
                    }
            except:
                pass
        
        health = ComponentHealth(
            name="Log Generator",
            type=ComponentType.LOG_GENERATOR,
            status=status,
            url=self.settings.LOG_GENERATOR_URL,
            last_check=datetime.now(),
            response_time_ms=response_time,
            error_message=error,
            metadata=metadata
        )
        
        self._component_status[ComponentType.LOG_GENERATOR.value] = health
        return health
    
    async def check_rag_server(self) -> ComponentHealth:
        """Check RAG server health."""
        url = f"{self.settings.RAG_SERVER_URL}/health"
        status, response_time, error = await self.check_http_endpoint(url)
        
        metadata = {}
        if status == ComponentStatus.HEALTHY:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    stats_response = await client.get(f"{self.settings.RAG_SERVER_URL}/stats")
                    if stats_response.status_code == 200:
                        metadata = stats_response.json()
            except:
                pass
        
        health = ComponentHealth(
            name="RAG Server",
            type=ComponentType.RAG_SERVER,
            status=status,
            url=self.settings.RAG_SERVER_URL,
            last_check=datetime.now(),
            response_time_ms=response_time,
            error_message=error,
            metadata=metadata
        )
        
        self._component_status[ComponentType.RAG_SERVER.value] = health
        return health
    
    async def check_deepseek(self) -> ComponentHealth:
        """Check DeepSeek LLM health."""
        url = f"{self.settings.DEEPSEEK_URL}/health"
        status, response_time, error = await self.check_http_endpoint(url)
        
        # If /health fails, try /v1/models as backup
        if status != ComponentStatus.HEALTHY:
            url = f"{self.settings.DEEPSEEK_URL}/v1/models"
            status, response_time, error = await self.check_http_endpoint(url)
        
        health = ComponentHealth(
            name="DeepSeek LLM",
            type=ComponentType.DEEPSEEK_LLM,
            status=status,
            url=self.settings.DEEPSEEK_URL,
            last_check=datetime.now(),
            response_time_ms=response_time,
            error_message=error,
            metadata={}
        )
        
        self._component_status[ComponentType.DEEPSEEK_LLM.value] = health
        return health
    
    async def check_kafka(self) -> ComponentHealth:
        """Check Kafka/Redpanda connectivity."""
        # For now, return a basic check
        # In production, would use confluent-kafka AdminClient
        status = ComponentStatus.UNKNOWN
        error = None
        
        try:
            from confluent_kafka import Consumer
            config = get_kafka_config()
            config['socket.timeout.ms'] = 5000
            
            consumer = Consumer(config)
            # Try to list topics
            metadata = consumer.list_topics(timeout=5)
            consumer.close()
            
            if metadata:
                status = ComponentStatus.HEALTHY
            else:
                status = ComponentStatus.DEGRADED
                error = "No topics found"
        except ImportError:
            status = ComponentStatus.UNKNOWN
            error = "confluent-kafka not installed"
        except Exception as e:
            status = ComponentStatus.UNHEALTHY
            error = str(e)
        
        health = ComponentHealth(
            name="Kafka/Redpanda",
            type=ComponentType.KAFKA_PRODUCER,
            status=status,
            url=self.settings.KAFKA_BOOTSTRAP_SERVERS,
            last_check=datetime.now(),
            response_time_ms=None,
            error_message=error,
            metadata={}
        )
        
        self._component_status[ComponentType.KAFKA_PRODUCER.value] = health
        return health
    
    async def check_all_components(self) -> list[ComponentHealth]:
        """Check all components concurrently."""
        results = await asyncio.gather(
            self.check_log_generator(),
            self.check_rag_server(),
            self.check_deepseek(),
            self.check_kafka(),
            return_exceptions=True
        )
        
        health_results = []
        for result in results:
            if isinstance(result, ComponentHealth):
                health_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Health check failed: {result}")
        
        return health_results
    
    async def get_system_health(self) -> SystemHealth:
        """Get overall system health."""
        components = await self.check_all_components()
        
        # Determine overall status
        statuses = [c.status for c in components]
        if all(s == ComponentStatus.HEALTHY for s in statuses):
            overall_status = ComponentStatus.HEALTHY
        elif any(s == ComponentStatus.UNHEALTHY for s in statuses):
            overall_status = ComponentStatus.UNHEALTHY
        elif any(s == ComponentStatus.DEGRADED for s in statuses):
            overall_status = ComponentStatus.DEGRADED
        else:
            overall_status = ComponentStatus.UNKNOWN
        
        # Build specific health objects
        log_gen_health = None
        rag_health = None
        
        for comp in components:
            if comp.type == ComponentType.LOG_GENERATOR:
                log_gen_health = LogGeneratorHealth(
                    status=comp.status,
                    is_streaming=comp.metadata.get("is_running", False),
                    logs_generated=comp.metadata.get("logs_generated", 0),
                    anomalies_generated=comp.metadata.get("anomalies_generated", 0),
                    anomaly_rate=0.05,
                    start_time=None,
                    current_anomaly_active=False
                )
            elif comp.type == ComponentType.RAG_SERVER:
                rag_health = RAGHealth(
                    status=comp.status,
                    document_count=comp.metadata.get("document_count", 0),
                    chunk_count=comp.metadata.get("chunk_count", 0),
                    embedding_model=comp.metadata.get("embedding_model", "unknown"),
                    llm_model=comp.metadata.get("llm_model", "deepseek/deepseek-r1"),
                    llm_connected=comp.status == ComponentStatus.HEALTHY,
                    queries_processed=comp.metadata.get("queries_processed", 0),
                    avg_query_time_ms=comp.metadata.get("avg_query_time_ms", 0),
                    last_query_timestamp=None
                )
        
        uptime = (datetime.now() - self._start_time).total_seconds()
        
        return SystemHealth(
            status=overall_status,
            components=components,
            kafka=None,  # TODO: build KafkaHealth
            rag=rag_health,
            log_generator=log_gen_health,
            pathway=None,  # TODO: build PathwayHealth
            uptime_seconds=uptime,
            last_updated=datetime.now()
        )
    
    def get_system_info(self) -> SystemInfo:
        """Get system information."""
        import sys
        import socket
        
        return SystemInfo(
            version=self.settings.API_VERSION,
            environment="development" if self.settings.DEBUG else "production",
            python_version=sys.version.split()[0],
            host=socket.gethostname(),
            port=self.settings.PORT,
            start_time=self._start_time,
            uptime_seconds=(datetime.now() - self._start_time).total_seconds()
        )
    
    def get_component_status(self, component_type: ComponentType) -> Optional[ComponentHealth]:
        """Get cached status for a component."""
        return self._component_status.get(component_type.value)


# Global health checker instance
health_checker = HealthChecker()
