"""
FastAPI Web Server for Synthetic Logs Generator

Provides REST API and WebSocket endpoints for generating logs.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import yaml

from .generator import LogGenerator, create_generator
from .models import LogEntry, AnomalyType
from .output import create_output_handler


# ============== Pydantic Models ==============

class GeneratorConfig(BaseModel):
    """Configuration for log generation"""
    batch_size: int = Field(default=100, ge=1, le=10000)
    total_logs: int = Field(default=1000, ge=0)
    interval: float = Field(default=1.0, ge=0.01, le=60.0)


class AnomalyConfig(BaseModel):
    """Anomaly configuration"""
    probability: float = Field(default=0.05, ge=0.0, le=1.0)
    error_spike_enabled: bool = True
    latency_degradation_enabled: bool = True
    security_threat_enabled: bool = True
    resource_exhaustion_enabled: bool = True
    service_outage_enabled: bool = True
    data_anomaly_enabled: bool = True


class GenerateRequest(BaseModel):
    """Request model for generating logs"""
    count: int = Field(default=100, ge=1, le=10000, description="Number of logs to generate")
    anomaly_rate: float = Field(default=0.05, ge=0.0, le=1.0, description="Probability of anomalies")
    include_labels: bool = Field(default=True, description="Include anomaly labels in output")
    format: str = Field(default="json", pattern="^(json|text)$")


class StreamConfig(BaseModel):
    """Configuration for streaming logs"""
    batch_size: int = Field(default=10, ge=1, le=1000)
    interval: float = Field(default=1.0, ge=0.1, le=60.0)
    anomaly_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    include_labels: bool = True


class GeneratorStatus(BaseModel):
    """Status of the generator"""
    is_running: bool
    logs_generated: int
    anomalies_generated: int
    start_time: Optional[datetime]
    current_anomaly_active: bool


class InjectAnomalyRequest(BaseModel):
    """Request to inject a specific anomaly"""
    anomaly_type: str = Field(
        ..., 
        description="Type of anomaly to inject",
        pattern="^(error_spike|latency_degradation|security_threat|resource_exhaustion|service_outage|data_anomaly)$"
    )
    duration_logs: int = Field(default=20, ge=5, le=100)


# ============== Application State ==============

class AppState:
    """Application state manager"""
    def __init__(self):
        self.config = self._load_default_config()
        self.generator: Optional[LogGenerator] = None
        self.is_streaming = False
        self.logs_generated = 0
        self.anomalies_generated = 0
        self.start_time: Optional[datetime] = None
        self.active_websockets: List[WebSocket] = []
        self._init_generator()
    
    def _load_default_config(self) -> dict:
        """Load default configuration"""
        try:
            from pathlib import Path
            config_path = Path(__file__).parent / "config.yaml"
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception:
            return {
                "generator": {"batch_size": 100, "total_logs": 1000, "interval": 1.0},
                "sources": [
                    {"name": "web-server", "weight": 0.4, "services": ["nginx", "apache"]},
                    {"name": "application", "weight": 0.3, "services": ["auth-service", "user-service"]},
                    {"name": "database", "weight": 0.15, "services": ["postgresql", "redis"]},
                    {"name": "infrastructure", "weight": 0.15, "services": ["kubernetes", "docker"]},
                ],
                "normal_logs": {
                    "log_levels": {"INFO": 0.7, "DEBUG": 0.15, "WARNING": 0.1, "ERROR": 0.04, "CRITICAL": 0.01},
                    "response_time": {"min": 10, "max": 500, "mean": 150, "std": 50}
                },
                "anomalies": {"probability": 0.05, "types": {
                    "error_spike": {"enabled": True, "weight": 0.25, "duration_logs": 20},
                    "latency_degradation": {"enabled": True, "weight": 0.2, "duration_logs": 50},
                    "security_threat": {"enabled": True, "weight": 0.15},
                    "resource_exhaustion": {"enabled": True, "weight": 0.15},
                    "service_outage": {"enabled": True, "weight": 0.15},
                    "data_anomaly": {"enabled": True, "weight": 0.1},
                }},
                "timestamps": {"start": "now", "increment": {"min": 0.001, "max": 2.0}},
            }
    
    def _init_generator(self):
        """Initialize the log generator"""
        self.generator = create_generator(self.config)
    
    def update_config(self, updates: dict):
        """Update configuration and reinitialize generator"""
        def deep_update(base: dict, updates: dict):
            for key, value in updates.items():
                if isinstance(value, dict) and key in base:
                    deep_update(base[key], value)
                else:
                    base[key] = value
        
        deep_update(self.config, updates)
        self._init_generator()
    
    def reset_stats(self):
        """Reset statistics"""
        self.logs_generated = 0
        self.anomalies_generated = 0
        self.start_time = datetime.now()


# Global state
state = AppState()


# ============== Lifespan ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    state.reset_stats()
    yield
    state.is_streaming = False


# ============== FastAPI App ==============

app = FastAPI(
    title="Synthetic Logs Generator API",
    description="REST API and WebSocket endpoints for generating synthetic logs with anomaly patterns",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== REST Endpoints ==============

@app.get("/", tags=["Info"])
async def root():
    """API information"""
    return {
        "name": "Synthetic Logs Generator API",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/api/generate",
            "stream": "/api/stream",
            "websocket": "/ws/logs",
            "config": "/api/config",
            "status": "/api/status",
        }
    }


@app.get("/api/status", response_model=GeneratorStatus, tags=["Status"])
async def get_status():
    """Get generator status"""
    return GeneratorStatus(
        is_running=state.is_streaming,
        logs_generated=state.logs_generated,
        anomalies_generated=state.anomalies_generated,
        start_time=state.start_time,
        current_anomaly_active=state.generator.anomaly_generator.is_active if state.generator else False
    )


@app.get("/api/config", tags=["Configuration"])
async def get_config():
    """Get current configuration"""
    return state.config


@app.put("/api/config/generator", tags=["Configuration"])
async def update_generator_config(config: GeneratorConfig):
    """Update generator configuration"""
    state.update_config({
        "generator": {
            "batch_size": config.batch_size,
            "total_logs": config.total_logs,
            "interval": config.interval,
        }
    })
    return {"message": "Generator configuration updated", "config": config}


@app.put("/api/config/anomalies", tags=["Configuration"])
async def update_anomaly_config(config: AnomalyConfig):
    """Update anomaly configuration"""
    state.update_config({
        "anomalies": {
            "probability": config.probability,
            "types": {
                "error_spike": {"enabled": config.error_spike_enabled},
                "latency_degradation": {"enabled": config.latency_degradation_enabled},
                "security_threat": {"enabled": config.security_threat_enabled},
                "resource_exhaustion": {"enabled": config.resource_exhaustion_enabled},
                "service_outage": {"enabled": config.service_outage_enabled},
                "data_anomaly": {"enabled": config.data_anomaly_enabled},
            }
        }
    })
    return {"message": "Anomaly configuration updated", "config": config}


@app.post("/api/generate", tags=["Generation"])
async def generate_logs(request: GenerateRequest):
    """Generate a batch of logs"""
    # Temporarily update anomaly rate
    original_prob = state.config.get("anomalies", {}).get("probability", 0.05)
    state.config.setdefault("anomalies", {})["probability"] = request.anomaly_rate
    state._init_generator()
    
    try:
        logs = state.generator.generate_batch(request.count)
        state.logs_generated += len(logs)
        anomaly_count = sum(1 for log in logs if log.is_anomaly)
        state.anomalies_generated += anomaly_count
        
        if request.format == "json":
            output = [log.to_dict(request.include_labels) for log in logs]
        else:
            output = [log.to_text(request.include_labels) for log in logs]
        
        return {
            "count": len(logs),
            "anomaly_count": anomaly_count,
            "logs": output
        }
    finally:
        # Restore original probability
        state.config["anomalies"]["probability"] = original_prob
        state._init_generator()


@app.post("/api/generate/single", tags=["Generation"])
async def generate_single_log(
    include_labels: bool = True,
    force_anomaly: bool = False
):
    """Generate a single log entry"""
    if force_anomaly and not state.generator.anomaly_generator.is_active:
        state.generator.anomaly_generator.start_anomaly()
    
    log = state.generator.generate_log()
    state.logs_generated += 1
    if log.is_anomaly:
        state.anomalies_generated += 1
    
    return log.to_dict(include_labels)


@app.post("/api/inject-anomaly", tags=["Generation"])
async def inject_anomaly(request: InjectAnomalyRequest):
    """Inject a specific type of anomaly"""
    anomaly_type_map = {
        "error_spike": AnomalyType.ERROR_SPIKE,
        "latency_degradation": AnomalyType.LATENCY_DEGRADATION,
        "security_threat": AnomalyType.SECURITY_THREAT,
        "resource_exhaustion": AnomalyType.RESOURCE_EXHAUSTION,
        "service_outage": AnomalyType.SERVICE_OUTAGE,
        "data_anomaly": AnomalyType.DATA_ANOMALY,
    }
    
    anomaly_type = anomaly_type_map.get(request.anomaly_type)
    if not anomaly_type:
        raise HTTPException(status_code=400, detail=f"Invalid anomaly type: {request.anomaly_type}")
    
    # Update duration and start anomaly
    state.config.setdefault("anomalies", {}).setdefault("types", {}).setdefault(
        request.anomaly_type, {}
    )["duration_logs"] = request.duration_logs
    state._init_generator()
    
    state.generator.anomaly_generator.start_anomaly(anomaly_type)
    
    return {
        "message": f"Anomaly '{request.anomaly_type}' injected",
        "duration_logs": request.duration_logs
    }


@app.get("/api/stream", tags=["Streaming"])
async def stream_logs(
    batch_size: int = Query(default=10, ge=1, le=100),
    interval: float = Query(default=1.0, ge=0.1, le=60.0),
    anomaly_rate: float = Query(default=0.05, ge=0.0, le=1.0),
    include_labels: bool = Query(default=True),
    max_batches: Optional[int] = Query(default=None, ge=1, le=100000, description="Max batches (None = unlimited)")
):
    """Stream logs continuously as Server-Sent Events (SSE)"""
    import json
    
    state.config.setdefault("anomalies", {})["probability"] = anomaly_rate
    state._init_generator()
    
    async def generate():
        batch_count = 0
        while max_batches is None or batch_count < max_batches:
            logs = state.generator.generate_batch(batch_size)
            state.logs_generated += len(logs)
            anomaly_count = sum(1 for log in logs if log.is_anomaly)
            state.anomalies_generated += anomaly_count
            
            data = {
                "batch": batch_count + 1,
                "count": len(logs),
                "anomaly_count": anomaly_count,
                "logs": [log.to_dict(include_labels) for log in logs]
            }
            
            yield f"data: {json.dumps(data)}\n\n"
            batch_count += 1
            await asyncio.sleep(interval)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/stream/ndjson", tags=["Streaming"])
async def stream_logs_ndjson(
    batch_size: int = Query(default=1, ge=1, le=100),
    interval: float = Query(default=0.5, ge=0.01, le=60.0),
    anomaly_rate: float = Query(default=0.05, ge=0.0, le=1.0),
    include_labels: bool = Query(default=True),
):
    """Stream logs continuously as newline-delimited JSON (NDJSON)"""
    import json
    
    state.config.setdefault("anomalies", {})["probability"] = anomaly_rate
    state._init_generator()
    
    async def generate():
        while True:
            logs = state.generator.generate_batch(batch_size)
            state.logs_generated += len(logs)
            
            for log in logs:
                if log.is_anomaly:
                    state.anomalies_generated += 1
                yield json.dumps(log.to_dict(include_labels)) + "\n"
            
            await asyncio.sleep(interval)
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/reset", tags=["Status"])
async def reset_stats():
    """Reset generator statistics"""
    state.reset_stats()
    state._init_generator()
    return {"message": "Statistics reset", "timestamp": state.start_time}


# ============== WebSocket Endpoint ==============

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for real-time log streaming"""
    await websocket.accept()
    state.active_websockets.append(websocket)
    
    # Default streaming config
    config = StreamConfig()
    
    try:
        while True:
            try:
                # Check for incoming messages (config updates)
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=config.interval
                )
                
                # Handle control messages
                if message.get("action") == "configure":
                    config = StreamConfig(**message.get("config", {}))
                    await websocket.send_json({
                        "type": "config_updated",
                        "config": config.model_dump()
                    })
                elif message.get("action") == "inject_anomaly":
                    anomaly_type = message.get("anomaly_type", "error_spike")
                    anomaly_type_map = {
                        "error_spike": AnomalyType.ERROR_SPIKE,
                        "latency_degradation": AnomalyType.LATENCY_DEGRADATION,
                        "security_threat": AnomalyType.SECURITY_THREAT,
                        "resource_exhaustion": AnomalyType.RESOURCE_EXHAUSTION,
                        "service_outage": AnomalyType.SERVICE_OUTAGE,
                        "data_anomaly": AnomalyType.DATA_ANOMALY,
                    }
                    if anomaly_type in anomaly_type_map:
                        state.generator.anomaly_generator.start_anomaly(anomaly_type_map[anomaly_type])
                        await websocket.send_json({
                            "type": "anomaly_injected",
                            "anomaly_type": anomaly_type
                        })
                    
            except asyncio.TimeoutError:
                # Generate and send logs
                state.config.setdefault("anomalies", {})["probability"] = config.anomaly_rate
                
                logs = state.generator.generate_batch(config.batch_size)
                state.logs_generated += len(logs)
                anomaly_count = sum(1 for log in logs if log.is_anomaly)
                state.anomalies_generated += anomaly_count
                
                await websocket.send_json({
                    "type": "logs",
                    "count": len(logs),
                    "anomaly_count": anomaly_count,
                    "logs": [log.to_dict(config.include_labels) for log in logs]
                })
                
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in state.active_websockets:
            state.active_websockets.remove(websocket)


# ============== Health Check ==============

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "generator_ready": state.generator is not None
    }


# ============== Main ==============

def main():
    """Run the server"""
    import uvicorn
    uvicorn.run(
        "logs_generator.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
