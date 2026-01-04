"""
Kafka Data Bridge - Connects OpsPulse Kafka streams to Dashboard API.

This service subscribes to Kafka topics and forwards data to the
dashboard backend for real-time visualization.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class KafkaDataBridge:
    """
    Bridge between Kafka/Redpanda and the Dashboard API.
    
    Consumes from:
    - raw_logs: Log entries from the generator
    - processed_alerts: Alerts from Pathway consumer
    - remediation_alerts: Remediations from RAG
    
    Forwards data to the aggregator and WebSocket manager.
    """
    
    def __init__(
        self,
        bootstrap_servers: str,
        username: str,
        password: str,
        topics: list[str] = None
    ):
        self.bootstrap_servers = bootstrap_servers
        self.username = username
        self.password = password
        self.topics = topics or ["raw_logs", "processed_alerts", "remediation_alerts"]
        
        self._running = False
        self._consumer = None
        self._message_queue: Queue = Queue(maxsize=10000)
        self._consumer_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "errors": 0,
            "last_message_time": None,
            "topic_counts": {t: 0 for t in self.topics}
        }
    
    def _get_kafka_config(self) -> dict:
        """Get Kafka consumer configuration."""
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "SCRAM-SHA-256",
            "sasl.username": self.username,
            "sasl.password": self.password,
            "group.id": "opspulse-dashboard-bridge",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 1000,
        }
    
    def _consumer_loop(self):
        """Background thread for Kafka consumption."""
        try:
            from confluent_kafka import Consumer, KafkaError
            
            self._consumer = Consumer(self._get_kafka_config())
            self._consumer.subscribe(self.topics)
            
            logger.info(f"Kafka bridge started, subscribed to: {self.topics}")
            
            while self._running:
                msg = self._consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error(f"Kafka error: {msg.error()}")
                    self.stats["errors"] += 1
                    continue
                
                try:
                    topic = msg.topic()
                    value = json.loads(msg.value().decode('utf-8'))
                    
                    self._message_queue.put({
                        "topic": topic,
                        "data": value,
                        "timestamp": datetime.now().isoformat(),
                        "partition": msg.partition(),
                        "offset": msg.offset()
                    })
                    
                    self.stats["messages_received"] += 1
                    self.stats["topic_counts"][topic] = self.stats["topic_counts"].get(topic, 0) + 1
                    self.stats["last_message_time"] = datetime.now().isoformat()
                
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    self.stats["errors"] += 1
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.stats["errors"] += 1
        
        except ImportError:
            logger.error("confluent-kafka not installed")
        except Exception as e:
            logger.error(f"Consumer loop error: {e}")
        finally:
            if self._consumer:
                self._consumer.close()
    
    def start(self):
        """Start the Kafka consumer in a background thread."""
        if self._running:
            return
        
        self._running = True
        self._consumer_thread = threading.Thread(target=self._consumer_loop, daemon=True)
        self._consumer_thread.start()
        logger.info("Kafka data bridge started")
    
    def stop(self):
        """Stop the Kafka consumer."""
        self._running = False
        if self._consumer_thread:
            self._consumer_thread.join(timeout=5)
        logger.info("Kafka data bridge stopped")
    
    async def get_messages(self, timeout: float = 0.1) -> list[Dict[str, Any]]:
        """
        Get pending messages from the queue.
        
        Args:
            timeout: How long to wait for messages
            
        Returns:
            List of messages with topic and data
        """
        messages = []
        
        while True:
            try:
                msg = self._message_queue.get_nowait()
                messages.append(msg)
                self.stats["messages_processed"] += 1
            except Empty:
                break
        
        return messages
    
    def get_stats(self) -> dict:
        """Get bridge statistics."""
        return {
            **self.stats,
            "queue_size": self._message_queue.qsize(),
            "is_running": self._running
        }


async def process_kafka_messages(bridge: KafkaDataBridge):
    """
    Async task to process Kafka messages and forward to dashboard.
    """
    from .data_aggregator import aggregator
    from .websocket_manager import ws_manager
    
    while True:
        try:
            messages = await bridge.get_messages()
            
            for msg in messages:
                topic = msg["topic"]
                data = msg["data"]
                
                if topic == "raw_logs":
                    aggregator.record_log(data)
                    await ws_manager.broadcast_log(data)
                
                elif topic == "processed_alerts":
                    alert_id = aggregator.record_alert(data)
                    await ws_manager.broadcast_alert(
                        alert_id=alert_id,
                        service=data.get("service", "unknown"),
                        alert_type=data.get("alert_type", "unknown"),
                        severity="critical" if data.get("is_spike") else "warning",
                        data=data
                    )
                
                elif topic == "remediation_alerts":
                    aggregator.record_remediation(data)
                    await ws_manager.broadcast_remediation(
                        alert_id=data.get("alert_id", ""),
                        remediation_preview=data.get("remediation", "")[:200],
                        data=data
                    )
            
            await asyncio.sleep(0.05)  # Small delay to prevent busy loop
        
        except Exception as e:
            logger.error(f"Error processing Kafka messages: {e}")
            await asyncio.sleep(1)
