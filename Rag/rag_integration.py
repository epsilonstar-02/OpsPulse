"""
RAG Integration Module for OpsPulse AI.

This module provides integration between the Pathway stream processor and the RAG
system for automated remediation lookup. When anomalies are detected by the
Pathway consumer, this module queries the RAG system to retrieve relevant
runbook remediation steps.

Implements:
- SRS REQ-4.3: Upon detecting an anomaly, RAG component queries Document Store
- SRS REQ-5.1: Generate alerts with recommended remediation steps
- Architecture: Pathway Consumer -> RAG Pipeline -> DeepSeek LLM -> Alerts
"""

import json
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import httpx
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AnomalyAlert:
    """
    Represents an anomaly alert from Pathway consumer.
    Matches the format_alert() output from pathway_consumer.py.
    """
    service: str
    log_level: str
    total_logs: int
    anomaly_count: int
    avg_response_time_ms: float
    is_spike: bool
    alert_type: str
    timestamp: str
    
    @classmethod
    def from_json(cls, json_str: str) -> "AnomalyAlert":
        """Parse from JSON string (Kafka message)."""
        data = json.loads(json_str)
        return cls(**data)
    
    def to_rag_query(self) -> str:
        """
        Convert alert to a RAG query string.
        Uses the anomaly context to find relevant runbook sections.
        """
        query_parts = []
        
        # Build query based on alert type
        if self.alert_type == "spike":
            query_parts.append(f"How to handle error spike in {self.service} service?")
            query_parts.append(f"Remediation steps for high error rate ({self.anomaly_count} anomalies detected).")
        
        if self.avg_response_time_ms > 1000:
            query_parts.append(f"What to do when {self.service} has high latency ({self.avg_response_time_ms:.0f}ms)?")
        
        if self.log_level in ("ERROR", "CRITICAL"):
            query_parts.append(f"Troubleshooting {self.log_level} level issues in {self.service}.")
        
        # Default fallback query
        if not query_parts:
            query_parts.append(f"What are the best practices for handling anomalies in {self.service}?")
        
        return " ".join(query_parts)


@dataclass
class RemediationResponse:
    """
    Represents a remediation response from the RAG system.
    Combines the original alert with RAG-generated remediation.
    """
    alert: AnomalyAlert
    remediation: str
    sources: list[str]
    query_used: str
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert": asdict(self.alert),
            "remediation": self.remediation,
            "sources": self.sources,
            "query_used": self.query_used,
            "timestamp": self.timestamp,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_slack_message(self) -> Dict[str, Any]:
        """Format as Slack message payload."""
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 OpsPulse Alert: {self.alert.service}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Service:*\n{self.alert.service}"},
                        {"type": "mrkdwn", "text": f"*Alert Type:*\n{self.alert.alert_type}"},
                        {"type": "mrkdwn", "text": f"*Log Level:*\n{self.alert.log_level}"},
                        {"type": "mrkdwn", "text": f"*Anomaly Count:*\n{self.alert.anomaly_count}"},
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*📋 Recommended Remediation:*\n{self.remediation[:1500]}..."
                        if len(self.remediation) > 1500 else
                        f"*📋 Recommended Remediation:*\n{self.remediation}"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"📚 Sources: {', '.join(self.sources) if self.sources else 'N/A'}"
                        }
                    ]
                }
            ]
        }


class RAGClient:
    """
    Async HTTP client for querying the RAG server.
    Supports both ChromaDB RAG server (Flask) and Pathway RAG server.
    """
    
    def __init__(
        self,
        rag_url: str = "http://localhost:5000",
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        Initialize the RAG client.
        
        Args:
            rag_url: Base URL of the RAG server
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on failure
        """
        self.rag_url = rag_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    async def query(self, question: str, n_results: int = 5) -> Dict[str, Any]:
        """
        Query the RAG system for remediation.
        
        Args:
            question: The query string
            n_results: Number of relevant chunks to retrieve
            
        Returns:
            Dictionary with 'answer' and 'sources' keys
        """
        if not self._client:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        
        payload = {"query": question, "n_results": n_results}
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    f"{self.rag_url}/",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                last_error = e
                logger.warning(f"RAG query attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # Return fallback response on failure
        logger.error(f"RAG query failed after {self.max_retries} attempts: {last_error}")
        return {
            "answer": f"Unable to retrieve remediation. Error: {last_error}",
            "sources": [],
        }
    
    async def health_check(self) -> bool:
        """Check if RAG server is healthy."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=5.0)
        
        try:
            response = await self._client.get(f"{self.rag_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False


class AlertRemediationService:
    """
    Service that processes anomaly alerts and retrieves remediation.
    Acts as the bridge between Pathway consumer and RAG system.
    """
    
    def __init__(
        self,
        rag_client: RAGClient,
        slack_webhook_url: Optional[str] = None,
    ):
        """
        Initialize the remediation service.
        
        Args:
            rag_client: RAG client instance
            slack_webhook_url: Optional Slack webhook for notifications
        """
        self.rag_client = rag_client
        self.slack_webhook_url = slack_webhook_url
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def process_alert(self, alert: AnomalyAlert) -> RemediationResponse:
        """
        Process an anomaly alert and retrieve remediation.
        
        Args:
            alert: The anomaly alert from Pathway
            
        Returns:
            RemediationResponse with the alert and remediation
        """
        # Generate RAG query from alert context
        query = alert.to_rag_query()
        logger.info(f"Processing alert for {alert.service}: {query[:100]}...")
        
        # Query RAG system
        rag_response = await self.rag_client.query(query)
        
        # Build remediation response
        response = RemediationResponse(
            alert=alert,
            remediation=rag_response.get("answer", "No remediation found."),
            sources=rag_response.get("sources", []),
            query_used=query,
            timestamp=datetime.now().isoformat(),
        )
        
        logger.info(f"Remediation retrieved for {alert.service} (sources: {len(response.sources)})")
        
        return response
    
    async def process_and_notify(self, alert: AnomalyAlert) -> RemediationResponse:
        """
        Process alert and send notifications.
        
        Args:
            alert: The anomaly alert
            
        Returns:
            RemediationResponse
        """
        response = await self.process_alert(alert)
        
        # Send to Slack if configured
        if self.slack_webhook_url:
            await self._send_slack_notification(response)
        
        return response
    
    async def _send_slack_notification(self, response: RemediationResponse):
        """Send remediation to Slack."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        
        try:
            await self._http_client.post(
                self.slack_webhook_url,
                json=response.to_slack_message(),
            )
            logger.info(f"Slack notification sent for {response.alert.service}")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send Slack notification: {e}")


async def process_kafka_alert(
    alert_json: str,
    rag_url: str = "http://localhost:5000",
) -> RemediationResponse:
    """
    Convenience function to process a single Kafka alert.
    
    Args:
        alert_json: JSON string from Kafka processed_alerts topic
        rag_url: URL of the RAG server
        
    Returns:
        RemediationResponse with remediation
    """
    alert = AnomalyAlert.from_json(alert_json)
    
    async with RAGClient(rag_url) as client:
        service = AlertRemediationService(client)
        return await service.process_alert(alert)


# ================= Pathway UDF for Direct Integration =================
# This can be used directly in pathway_consumer.py for inline RAG queries

def create_rag_query_udf(rag_url: str = "http://localhost:5000"):
    """
    Create a Pathway UDF for RAG queries.
    
    Usage in pathway_consumer.py:
        from Rag.rag_integration import create_rag_query_udf
        query_rag = create_rag_query_udf("http://localhost:5000")
        
        alerts_with_remediation = alerts.select(
            ...,
            remediation=query_rag(pw.this.alert_json)
        )
    """
    import pathway as pw
    
    @pw.udf
    def query_rag_sync(alert_json: str) -> str:
        """Synchronous RAG query for use in Pathway."""
        import httpx
        
        try:
            alert = AnomalyAlert.from_json(alert_json)
            query = alert.to_rag_query()
            
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{rag_url}/",
                    json={"query": query, "n_results": 5},
                )
                response.raise_for_status()
                result = response.json()
                return result.get("answer", "No remediation found.")
        except Exception as e:
            return f"Error querying RAG: {e}"
    
    return query_rag_sync


# ================= CLI for Testing =================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Integration Test")
    parser.add_argument("--rag-url", default="http://localhost:5000", help="RAG server URL")
    parser.add_argument("--alert", type=str, help="JSON alert string to process")
    parser.add_argument("--test", action="store_true", help="Run with test alert")
    args = parser.parse_args()
    
    # Test alert
    test_alert = AnomalyAlert(
        service="auth-service",
        log_level="ERROR",
        total_logs=150,
        anomaly_count=12,
        avg_response_time_ms=2500.0,
        is_spike=True,
        alert_type="spike",
        timestamp=datetime.now().isoformat(),
    )
    
    async def main():
        alert_json = args.alert if args.alert else test_alert.to_rag_query()
        
        if args.alert:
            alert = AnomalyAlert.from_json(args.alert)
        else:
            alert = test_alert
        
        print(f"\n{'='*60}")
        print("RAG Integration Test")
        print(f"{'='*60}")
        print(f"RAG Server: {args.rag_url}")
        print(f"Service: {alert.service}")
        print(f"Alert Type: {alert.alert_type}")
        print(f"Query: {alert.to_rag_query()}")
        print(f"{'='*60}\n")
        
        async with RAGClient(args.rag_url) as client:
            # Health check
            healthy = await client.health_check()
            print(f"RAG Server Health: {'✓ Healthy' if healthy else '✗ Unhealthy'}")
            
            if healthy:
                service = AlertRemediationService(client)
                response = await service.process_alert(alert)
                
                print(f"\n{'='*60}")
                print("Remediation Response")
                print(f"{'='*60}")
                print(f"Sources: {response.sources}")
                print(f"\nRemediation:\n{response.remediation}")
                print(f"{'='*60}\n")
            else:
                print("\nCannot query RAG - server is not healthy.")
                print("Make sure to start the RAG server first:")
                print("  cd Rag && python chroma_rag_server.py --ingest")
    
    asyncio.run(main())
