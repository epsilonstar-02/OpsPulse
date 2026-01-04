"""
WebSocket Routes for Real-Time Dashboard Updates.

Provides:
- WebSocket endpoint for real-time data streaming
- Connection statistics endpoint
- WebSocket documentation
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import asyncio
import logging

from ..services.websocket_manager import ws_manager
from ..services.data_aggregator import aggregator
from ..models.websocket import WSChannel, WSConnectionStats

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time dashboard updates.
    
    Connection Protocol:
    1. Connect to /ws/live
    2. Send subscribe message with channels
    3. Receive real-time updates
    
    Message Types (Client → Server):
    - subscribe: {"type": "subscribe", "channels": ["logs", "alerts", "stats"]}
    - unsubscribe: {"type": "unsubscribe", "channels": ["logs"]}
    - ping: {"type": "ping"}
    
    Message Types (Server → Client):
    - log: New log entry
    - alert: New alert generated
    - remediation: New remediation from RAG
    - stats: Real-time statistics update
    - health: Component health update
    - pong: Response to ping
    - error: Error message
    - subscribed: Subscription confirmation
    - unsubscribed: Unsubscription confirmation
    
    Available Channels:
    - logs: Real-time log entries
    - alerts: Alert notifications
    - remediations: Remediation suggestions
    - stats: Statistics updates (every 5s)
    - health: Health status changes
    - pipeline: Pipeline events
    - all: All channels
    """
    client_id = None
    
    try:
        client_id = await ws_manager.connect(websocket)
        logger.info(f"WebSocket client connected: {client_id}")
        
        # Send welcome message
        await ws_manager.send_to_client(client_id, {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat(),
            "message": "Connected to OpsPulse real-time feed",
            "available_channels": [ch.value for ch in WSChannel]
        })
        
        # Start stats broadcast task for this client
        stats_task = asyncio.create_task(
            broadcast_stats_to_client(client_id)
        )
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                await ws_manager.handle_client_message(client_id, data)
        except WebSocketDisconnect:
            pass
        finally:
            stats_task.cancel()
    
    except ConnectionError as e:
        logger.warning(f"Connection rejected: {e}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if client_id:
            await ws_manager.disconnect(client_id)


async def broadcast_stats_to_client(client_id: str):
    """Periodically send stats to subscribed clients."""
    try:
        while True:
            await asyncio.sleep(5)  # Every 5 seconds
            
            # Check if client is subscribed to stats
            client_info = ws_manager.get_client_info(client_id)
            if not client_info:
                break
            
            if WSChannel.STATS in client_info.subscribed_channels:
                stats = aggregator.get_real_time_stats()
                overview = aggregator.get_dashboard_overview()
                
                await ws_manager.send_to_client(client_id, {
                    "type": "stats",
                    "timestamp": datetime.now().isoformat(),
                    "logs_per_second": overview.logs_per_minute / 60,
                    "errors_per_second": overview.error_rate * overview.logs_per_minute / 60,
                    "anomalies_per_second": overview.anomaly_rate * overview.logs_per_minute / 60,
                    "active_services": overview.services_count,
                    "pipeline_status": overview.pipeline_status,
                    "data": {
                        "total_logs": overview.total_logs,
                        "total_anomalies": overview.total_anomalies,
                        "total_alerts": overview.total_alerts,
                        "services_healthy": overview.services_healthy,
                        "services_degraded": overview.services_degraded,
                        "services_critical": overview.services_critical
                    }
                })
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Stats broadcast error: {e}")


@router.get("/ws/stats", response_model=WSConnectionStats)
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Returns:
        Connection counts and channel subscriptions
    """
    return ws_manager.get_connection_stats()


@router.get("/ws/info")
async def get_websocket_info():
    """
    Get WebSocket endpoint documentation.
    
    Returns:
        WebSocket usage information
    """
    return {
        "endpoint": "/ws/live",
        "protocol": "WebSocket",
        "description": "Real-time data feed for OpsPulse dashboard",
        "channels": {
            "logs": "Real-time log entries as they arrive",
            "alerts": "Alert notifications when anomalies are detected",
            "remediations": "Remediation suggestions from RAG system",
            "stats": "Statistics updates every 5 seconds",
            "health": "Component health status changes",
            "pipeline": "Pipeline processing events",
            "all": "Subscribe to all channels"
        },
        "client_messages": {
            "subscribe": {
                "description": "Subscribe to channels",
                "example": {"type": "subscribe", "channels": ["logs", "alerts", "stats"]}
            },
            "unsubscribe": {
                "description": "Unsubscribe from channels",
                "example": {"type": "unsubscribe", "channels": ["logs"]}
            },
            "ping": {
                "description": "Keep-alive ping",
                "example": {"type": "ping"}
            }
        },
        "server_messages": {
            "connected": "Connection established with client_id",
            "subscribed": "Subscription confirmation",
            "unsubscribed": "Unsubscription confirmation",
            "log": "New log entry",
            "alert": "New alert notification",
            "remediation": "Remediation suggestion",
            "stats": "Statistics update",
            "health": "Health status change",
            "pong": "Response to ping",
            "error": "Error message"
        },
        "connection_stats": ws_manager.get_connection_stats().model_dump()
    }
