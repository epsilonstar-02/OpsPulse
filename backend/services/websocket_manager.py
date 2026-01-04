"""
WebSocket Connection Manager for Real-Time Dashboard Updates.

Manages WebSocket connections, subscriptions, and message broadcasting
for the OpsPulse AI dashboard.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict
import uuid
import logging

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..models.websocket import (
    WSMessageType, WSChannel, WSClientInfo, WSConnectionStats,
    WSErrorMessage, WSPongMessage, WSStatsMessage, WSLogMessage,
    WSAlertMessage, WSRemediationMessage, WSHealthMessage
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time dashboard updates.
    
    Features:
    - Multiple channel subscriptions per client
    - Message filtering based on subscription
    - Heartbeat/ping-pong for connection health
    - Graceful disconnection handling
    - Connection statistics
    """
    
    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self._connections: Dict[str, WebSocket] = {}
        self._client_info: Dict[str, WSClientInfo] = {}
        self._channel_subscribers: Dict[WSChannel, Set[str]] = defaultdict(set)
        self._total_messages_sent: int = 0
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept a new WebSocket connection.
        
        Returns:
            client_id: Unique identifier for this connection
        """
        async with self._lock:
            if len(self._connections) >= self.max_connections:
                await websocket.close(code=1008, reason="Max connections reached")
                raise ConnectionError("Maximum connections reached")
            
            await websocket.accept()
            client_id = str(uuid.uuid4())[:8]
            
            self._connections[client_id] = websocket
            self._client_info[client_id] = WSClientInfo(
                client_id=client_id,
                connected_at=datetime.now(),
                subscribed_channels=[],
                filters={},
                messages_sent=0,
                last_activity=datetime.now()
            )
            
            logger.info(f"WebSocket client connected: {client_id}")
            return client_id
    
    async def disconnect(self, client_id: str):
        """Remove a client connection."""
        async with self._lock:
            if client_id in self._connections:
                # Unsubscribe from all channels
                for channel in list(self._channel_subscribers.keys()):
                    self._channel_subscribers[channel].discard(client_id)
                
                del self._connections[client_id]
                del self._client_info[client_id]
                logger.info(f"WebSocket client disconnected: {client_id}")
    
    async def subscribe(
        self, 
        client_id: str, 
        channels: List[WSChannel],
        filters: Optional[Dict[str, Any]] = None
    ):
        """Subscribe a client to channels."""
        if client_id not in self._client_info:
            return
        
        async with self._lock:
            for channel in channels:
                if channel == WSChannel.ALL:
                    # Subscribe to all channels
                    for ch in WSChannel:
                        if ch != WSChannel.ALL:
                            self._channel_subscribers[ch].add(client_id)
                            if ch not in self._client_info[client_id].subscribed_channels:
                                self._client_info[client_id].subscribed_channels.append(ch)
                else:
                    self._channel_subscribers[channel].add(client_id)
                    if channel not in self._client_info[client_id].subscribed_channels:
                        self._client_info[client_id].subscribed_channels.append(channel)
            
            if filters:
                self._client_info[client_id].filters.update(filters)
        
        # Send confirmation
        await self.send_to_client(client_id, {
            "type": WSMessageType.SUBSCRIBED.value,
            "channels": [ch.value for ch in channels],
            "timestamp": datetime.now().isoformat()
        })
    
    async def unsubscribe(self, client_id: str, channels: List[WSChannel]):
        """Unsubscribe a client from channels."""
        if client_id not in self._client_info:
            return
        
        async with self._lock:
            for channel in channels:
                if channel == WSChannel.ALL:
                    for ch in WSChannel:
                        self._channel_subscribers[ch].discard(client_id)
                    self._client_info[client_id].subscribed_channels.clear()
                else:
                    self._channel_subscribers[channel].discard(client_id)
                    if channel in self._client_info[client_id].subscribed_channels:
                        self._client_info[client_id].subscribed_channels.remove(channel)
        
        # Send confirmation
        await self.send_to_client(client_id, {
            "type": WSMessageType.UNSUBSCRIBED.value,
            "channels": [ch.value for ch in channels],
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send a message to a specific client."""
        if client_id not in self._connections:
            return
        
        try:
            websocket = self._connections[client_id]
            await websocket.send_json(message)
            
            async with self._lock:
                self._client_info[client_id].messages_sent += 1
                self._client_info[client_id].last_activity = datetime.now()
                self._total_messages_sent += 1
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
            await self.disconnect(client_id)
    
    async def broadcast_to_channel(
        self, 
        channel: WSChannel, 
        message: Dict[str, Any],
        filter_fn: Optional[callable] = None
    ):
        """Broadcast a message to all subscribers of a channel."""
        subscribers = self._channel_subscribers.get(channel, set()).copy()
        
        for client_id in subscribers:
            # Apply optional filter
            if filter_fn:
                client_info = self._client_info.get(client_id)
                if client_info and not filter_fn(client_info.filters, message):
                    continue
            
            await self.send_to_client(client_id, message)
    
    async def broadcast_log(self, log_data: Dict[str, Any]):
        """Broadcast a log entry to log subscribers."""
        message = {
            "type": WSMessageType.LOG.value,
            "timestamp": datetime.now().isoformat(),
            "data": log_data
        }
        await self.broadcast_to_channel(WSChannel.LOGS, message)
    
    async def broadcast_alert(
        self, 
        alert_id: str, 
        service: str, 
        alert_type: str, 
        severity: str,
        data: Dict[str, Any]
    ):
        """Broadcast an alert to alert subscribers."""
        message = {
            "type": WSMessageType.ALERT.value,
            "timestamp": datetime.now().isoformat(),
            "alert_id": alert_id,
            "service": service,
            "alert_type": alert_type,
            "severity": severity,
            "data": data
        }
        await self.broadcast_to_channel(WSChannel.ALERTS, message)
    
    async def broadcast_remediation(
        self, 
        alert_id: str, 
        remediation_preview: str,
        data: Dict[str, Any]
    ):
        """Broadcast a remediation to remediation subscribers."""
        message = {
            "type": WSMessageType.REMEDIATION.value,
            "timestamp": datetime.now().isoformat(),
            "alert_id": alert_id,
            "remediation_preview": remediation_preview[:500],
            "data": data
        }
        await self.broadcast_to_channel(WSChannel.REMEDIATIONS, message)
    
    async def broadcast_stats(self, stats: Dict[str, Any]):
        """Broadcast real-time statistics."""
        message = {
            "type": WSMessageType.STATS.value,
            "timestamp": datetime.now().isoformat(),
            **stats
        }
        await self.broadcast_to_channel(WSChannel.STATS, message)
    
    async def broadcast_health(
        self, 
        component: str, 
        status: str, 
        message_text: Optional[str] = None
    ):
        """Broadcast a health update."""
        message = {
            "type": WSMessageType.HEALTH.value,
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "status": status,
            "message": message_text
        }
        await self.broadcast_to_channel(WSChannel.HEALTH, message)
    
    async def handle_client_message(self, client_id: str, data: str):
        """Handle an incoming message from a client."""
        try:
            message = json.loads(data)
            msg_type = message.get("type", "").lower()
            
            if msg_type == "subscribe":
                channels = [WSChannel(ch) for ch in message.get("channels", [])]
                filters = message.get("filters")
                await self.subscribe(client_id, channels, filters)
            
            elif msg_type == "unsubscribe":
                channels = [WSChannel(ch) for ch in message.get("channels", [])]
                await self.unsubscribe(client_id, channels)
            
            elif msg_type == "ping":
                await self.send_to_client(client_id, {
                    "type": WSMessageType.PONG.value,
                    "timestamp": datetime.now().isoformat(),
                    "server_time": datetime.now().isoformat()
                })
            
            else:
                await self.send_to_client(client_id, {
                    "type": WSMessageType.ERROR.value,
                    "timestamp": datetime.now().isoformat(),
                    "code": "UNKNOWN_MESSAGE_TYPE",
                    "message": f"Unknown message type: {msg_type}"
                })
        
        except json.JSONDecodeError:
            await self.send_to_client(client_id, {
                "type": WSMessageType.ERROR.value,
                "timestamp": datetime.now().isoformat(),
                "code": "INVALID_JSON",
                "message": "Invalid JSON message"
            })
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
            await self.send_to_client(client_id, {
                "type": WSMessageType.ERROR.value,
                "timestamp": datetime.now().isoformat(),
                "code": "INTERNAL_ERROR",
                "message": str(e)
            })
    
    def get_connection_stats(self) -> WSConnectionStats:
        """Get connection statistics."""
        channel_counts = {
            ch.value: len(subscribers) 
            for ch, subscribers in self._channel_subscribers.items()
        }
        
        return WSConnectionStats(
            total_connections=len(self._connections),
            active_connections=len(self._connections),
            total_messages_sent=self._total_messages_sent,
            channels=channel_counts
        )
    
    def get_client_info(self, client_id: str) -> Optional[WSClientInfo]:
        """Get information about a specific client."""
        return self._client_info.get(client_id)
    
    @property
    def connection_count(self) -> int:
        """Get current connection count."""
        return len(self._connections)


# Global connection manager instance
ws_manager = ConnectionManager()
