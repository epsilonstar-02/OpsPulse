"""
OpsPulse AI - Dashboard Backend API

Main FastAPI application entry point that combines all routers,
middleware, and provides the unified backend for the dashboard.

Run with:
    python -m backend.main
    # or
    uvicorn backend.main:app --reload --port 8001
"""

import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .config import get_settings
from .routes import analytics_router, system_router, logs_router, websocket_router
from .services.data_aggregator import aggregator
from .services.websocket_manager import ws_manager
from .services.health_checker import health_checker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Settings
settings = get_settings()

# Background tasks
_background_tasks = []
_kafka_consumer_task: Optional[asyncio.Task] = None


async def kafka_consumer_loop():
    """
    Background task to consume messages from Kafka topics.
    Updates the aggregator with incoming data.
    """
    try:
        from confluent_kafka import Consumer
        from .config import get_kafka_config
        
        config = get_kafka_config()
        consumer = Consumer(config)
        
        topics = [
            settings.KAFKA_RAW_LOGS_TOPIC,
            settings.KAFKA_ALERTS_TOPIC,
            settings.KAFKA_REMEDIATION_TOPIC
        ]
        consumer.subscribe(topics)
        
        logger.info(f"Kafka consumer started, subscribed to: {topics}")
        aggregator.update_component_status(kafka=True)
        aggregator.update_pipeline_status("running")
        
        while True:
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                await asyncio.sleep(0.1)
                continue
            
            if msg.error():
                logger.error(f"Kafka error: {msg.error()}")
                continue
            
            try:
                import json
                topic = msg.topic()
                value = json.loads(msg.value().decode('utf-8'))
                
                if topic == settings.KAFKA_RAW_LOGS_TOPIC:
                    # Record log
                    aggregator.record_log(value)
                    # Broadcast to WebSocket subscribers
                    await ws_manager.broadcast_log(value)
                
                elif topic == settings.KAFKA_ALERTS_TOPIC:
                    # Record alert
                    alert_id = aggregator.record_alert(value)
                    # Broadcast to WebSocket subscribers
                    await ws_manager.broadcast_alert(
                        alert_id=alert_id,
                        service=value.get("service", "unknown"),
                        alert_type=value.get("alert_type", "unknown"),
                        severity="critical" if value.get("is_spike") else "warning",
                        data=value
                    )
                
                elif topic == settings.KAFKA_REMEDIATION_TOPIC:
                    # Record remediation
                    aggregator.record_remediation(value)
                    # Broadcast to WebSocket subscribers
                    await ws_manager.broadcast_remediation(
                        alert_id=value.get("alert_id", ""),
                        remediation_preview=value.get("remediation", "")[:200],
                        data=value
                    )
            
            except Exception as e:
                logger.error(f"Error processing Kafka message: {e}")
    
    except ImportError:
        logger.warning("confluent-kafka not installed, Kafka consumer disabled")
        aggregator.update_component_status(kafka=False)
    except Exception as e:
        logger.error(f"Kafka consumer error: {e}")
        aggregator.update_component_status(kafka=False)
        aggregator.update_pipeline_status("error")


async def health_check_loop():
    """Periodically check component health."""
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            health = await health_checker.get_system_health()
            
            # Update aggregator with component status
            for comp in health.components:
                if comp.name == "RAG Server":
                    aggregator.update_component_status(
                        rag=comp.status.value == "healthy"
                    )
            
            # Broadcast health update
            await ws_manager.broadcast_health(
                component="system",
                status=health.status.value,
                message_text=f"{health.status.value} - {len(health.components)} components checked"
            )
        except Exception as e:
            logger.error(f"Health check error: {e}")


async def stats_broadcast_loop():
    """Periodically broadcast stats to all subscribers."""
    while True:
        try:
            await asyncio.sleep(5)
            stats = aggregator.get_real_time_stats()
            overview = aggregator.get_dashboard_overview()
            
            await ws_manager.broadcast_stats({
                "logs_per_second": overview.logs_per_minute / 60,
                "errors_per_second": overview.error_rate * overview.logs_per_minute / 60,
                "anomalies_per_second": overview.anomaly_rate * overview.logs_per_minute / 60,
                "active_services": overview.services_count,
                "pipeline_status": overview.pipeline_status,
                "data": {
                    "total_logs": overview.total_logs,
                    "total_anomalies": overview.total_anomalies,
                    "total_alerts": overview.total_alerts
                }
            })
        except Exception as e:
            logger.error(f"Stats broadcast error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting OpsPulse Dashboard API...")
    
    # Start background tasks
    tasks = [
        asyncio.create_task(kafka_consumer_loop()),
        asyncio.create_task(health_check_loop()),
        asyncio.create_task(stats_broadcast_loop()),
    ]
    _background_tasks.extend(tasks)
    
    logger.info(f"📊 Dashboard API running on http://{settings.HOST}:{settings.PORT}")
    logger.info(f"📖 API Docs: http://localhost:{settings.PORT}/docs")
    logger.info(f"🔌 WebSocket: ws://localhost:{settings.PORT}/ws/live")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down Dashboard API...")
    for task in _background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds() * 1000
    
    if not request.url.path.startswith("/ws"):
        logger.debug(
            f"{request.method} {request.url.path} "
            f"- {response.status_code} ({duration:.2f}ms)"
        )
    
    return response


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred"
        }
    )


# Include routers
app.include_router(analytics_router)
app.include_router(system_router)
app.include_router(logs_router)
app.include_router(websocket_router)


# Root endpoint
@app.get("/", tags=["Info"])
async def root():
    """
    API root endpoint with service information.
    """
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "description": "Real-time analytics and monitoring API for OpsPulse AI",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "endpoints": {
            "analytics": "/api/analytics",
            "logs": "/api/logs",
            "alerts": "/api/alerts",
            "remediations": "/api/remediations",
            "system": "/api/system",
            "websocket": "/ws/live"
        },
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", tags=["Info"])
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "opspulse-dashboard-api"
    }


def main():
    """Run the application."""
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()
