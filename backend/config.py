"""
Configuration settings for the Dashboard Backend API.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Settings
    API_TITLE: str = "OpsPulse AI Dashboard API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Real-time analytics and monitoring API for OpsPulse AI"
    DEBUG: bool = False
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # Component URLs
    LOG_GENERATOR_URL: str = os.getenv("LOG_GENERATOR_URL", "http://localhost:8000")
    RAG_SERVER_URL: str = os.getenv("RAG_SERVER_URL", "http://localhost:5000")
    DEEPSEEK_URL: str = os.getenv("DEEPSEEK_URL", "http://localhost:8080")
    
    # Kafka/Redpanda Settings
    KAFKA_BOOTSTRAP_SERVERS: str = "d5c2s6rrcoacstisf5a0.any.ap-south-1.mpx.prd.cloud.redpanda.com:9092"
    KAFKA_SECURITY_PROTOCOL: str = "SASL_SSL"
    KAFKA_SASL_MECHANISM: str = "SCRAM-SHA-256"
    KAFKA_USERNAME: str = os.getenv("KAFKA_USERNAME", "ashutosh")
    KAFKA_PASSWORD: str = os.getenv("KAFKA_PASSWORD", "768581")
    
    # Kafka Topics
    KAFKA_RAW_LOGS_TOPIC: str = "raw_logs"
    KAFKA_ALERTS_TOPIC: str = "processed_alerts"
    KAFKA_REMEDIATION_TOPIC: str = "remediation_alerts"
    
    # WebSocket Settings
    WS_HEARTBEAT_INTERVAL: int = 30  # seconds
    WS_MAX_CONNECTIONS: int = 100
    
    # Data Retention
    METRICS_HISTORY_MINUTES: int = 60
    MAX_RECENT_LOGS: int = 1000
    MAX_RECENT_ALERTS: int = 500
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Kafka configuration dict for confluent-kafka
def get_kafka_config() -> dict:
    """Get Kafka configuration dictionary."""
    settings = get_settings()
    return {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "security.protocol": settings.KAFKA_SECURITY_PROTOCOL,
        "sasl.mechanisms": settings.KAFKA_SASL_MECHANISM,
        "sasl.username": settings.KAFKA_USERNAME,
        "sasl.password": settings.KAFKA_PASSWORD,
        "group.id": "opspulse-dashboard-consumer",
        "auto.offset.reset": "latest",
    }
