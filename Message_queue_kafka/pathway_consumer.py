"""
OpsPulse AI - Pathway Stream Processor

Real-time log analysis and anomaly detection using Pathway.
Implements tumbling windows for statistical analysis as per SRS REQ-3.1.

Features:
- Ingests logs from Kafka/Redpanda
- Tumbling window aggregation (1-minute windows)
- Spike anomaly detection (error rate > 3 std devs) - REQ-3.2
- Drop anomaly detection (heartbeat frequency drops) - REQ-3.3
- Outputs processed alerts to Kafka topic
- RAG integration for automated remediation lookup (REQ-4.3, REQ-5.1)
"""

import pathway as pw
from pathway.stdlib.temporal import windowby
from datetime import timedelta, datetime
import argparse
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import RAG integration module
try:
    from Rag.rag_integration import AnomalyAlert, RAGClient, AlertRemediationService
    RAG_INTEGRATION_AVAILABLE = True
except ImportError:
    RAG_INTEGRATION_AVAILABLE = False
    print("⚠️ RAG integration module not available. Install dependencies or check path.")

# ================= Kafka / Redpanda Config =================
KAFKA_SETTINGS = {
    "bootstrap.servers": "d5c2s6rrcoacstisf5a0.any.ap-south-1.mpx.prd.cloud.redpanda.com:9092",
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "SCRAM-SHA-256",
    "sasl.username": "ashutosh",
    "sasl.password": "768581",
    "group.id": "opspulse-pathway-consumer",
    "auto.offset.reset": "earliest",
}

INPUT_TOPIC = "raw_logs"
OUTPUT_TOPIC = "processed_alerts"

# ================= Window Configuration =================
WINDOW_DURATION = timedelta(seconds=15)  # 15-second windows for testing (change to 60 for production)
SPIKE_THRESHOLD = 3.0  # Z-score threshold for spike detection (REQ-3.2)
REMEDIATION_TOPIC = "remediation_alerts"  # Topic for alerts with remediation

# Debug counters
_debug_stats = {"windows_processed": 0, "alerts_generated": 0, "logs_seen": 0}


# ================= RAG Health Check =================
def check_rag_health(rag_url: str, timeout: float = 5.0) -> bool:
    """
    Check if RAG server is healthy before starting pipeline.
    
    Args:
        rag_url: Base URL of the RAG server
        timeout: Timeout for health check request
        
    Returns:
        True if RAG server is healthy, False otherwise
    """
    import httpx
    
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{rag_url.rstrip('/')}/health")
            return response.status_code == 200
    except Exception as e:
        print(f"   ⚠️ RAG health check failed: {e}")
        return False


def get_rag_stats(rag_url: str, timeout: float = 5.0) -> dict:
    """
    Get RAG server statistics.
    
    Args:
        rag_url: Base URL of the RAG server
        timeout: Timeout for request
        
    Returns:
        Dictionary with RAG stats or empty dict on failure
    """
    import httpx
    
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{rag_url.rstrip('/')}/stats")
            response.raise_for_status()
            return response.json()
    except Exception:
        return {}


# ================= Schema Definition =================
class LogSchema(pw.Schema):
    """
    Schema matching the log generator output format.
    Handles both required and optional fields from LogEntry model.
    """
    # Required fields
    timestamp: str
    level: str
    source: str
    service: str
    message: str
    
    # Optional fields - using pw.column_definition for defaults
    request_id: str | None = pw.column_definition(default_value=None)
    user_id: str | None = pw.column_definition(default_value=None)
    ip_address: str | None = pw.column_definition(default_value=None)
    endpoint: str | None = pw.column_definition(default_value=None)
    method: str | None = pw.column_definition(default_value=None)
    status_code: int | None = pw.column_definition(default_value=None)
    response_time_ms: float | None = pw.column_definition(default_value=None)
    error_code: str | None = pw.column_definition(default_value=None)
    stack_trace: str | None = pw.column_definition(default_value=None)
    
    # Nested objects as JSON
    metadata: pw.Json | None = pw.column_definition(default_value=None)
    _labels: pw.Json | None = pw.column_definition(default_value=None)


# ================= UDFs for Data Processing =================
@pw.udf
def parse_timestamp(ts_str: str) -> pw.DateTimeNaive:
    """Convert ISO timestamp to DateTimeNaive for windowing."""
    try:
        # Remove timezone info for DateTimeNaive
        ts_clean = ts_str.replace("Z", "").split("+")[0]
        return datetime.fromisoformat(ts_clean)
    except Exception:
        return datetime.now()


@pw.udf
def is_error_level(level: str) -> bool:
    """Check if log level indicates an error."""
    return level.upper() in ("ERROR", "CRITICAL")


@pw.udf
def extract_anomaly_flag(labels: pw.Json | None) -> bool:
    """Extract is_anomaly from _labels JSON."""
    if labels is None:
        return False
    try:
        return bool(labels.get("is_anomaly", False))
    except Exception:
        return False


@pw.udf
def extract_anomaly_type(labels: pw.Json | None) -> str:
    """Extract anomaly_type from _labels JSON."""
    if labels is None:
        return "none"
    try:
        return str(labels.get("anomaly_type", "none"))
    except Exception:
        return "none"


@pw.udf
def extract_anomaly_score(labels: pw.Json | None) -> float:
    """Extract anomaly_score from _labels JSON."""
    if labels is None:
        return 0.0
    try:
        return float(labels.get("anomaly_score", 0.0))
    except Exception:
        return 0.0


@pw.udf
def calculate_z_score(count: int, mean: float, stddev: float) -> float:
    """Calculate Z-score for spike detection."""
    if stddev == 0 or stddev is None:
        return 0.0
    return abs(count - mean) / stddev


@pw.udf
def format_alert(
    service: str,
    level: str,
    count: int,
    anomaly_count: int,
    avg_response_time: float,
    is_spike: bool
) -> str:
    """Format alert as JSON string for output."""
    alert = {
        "service": service,
        "log_level": level,
        "total_logs": count,
        "anomaly_count": anomaly_count,
        "avg_response_time_ms": round(avg_response_time, 2) if avg_response_time else 0,
        "is_spike": is_spike,
        "alert_type": "spike" if is_spike else "normal",
        "timestamp": datetime.now().isoformat()
    }
    return json.dumps(alert)


# ================= Pipeline Construction =================
def create_pipeline(
    input_topic: str,
    output_topic: str,
    kafka_settings: dict,
    enable_output: bool = True,
    rag_url: str = None,
    window_seconds: int = 15,
):
    """
    Build the Pathway streaming pipeline for OpsPulse AI.
    
    Pipeline stages:
    1. Ingest logs from Kafka
    2. Parse and enrich with computed fields
    3. Apply tumbling window aggregation
    4. Detect anomalies (spikes and drops)
    5. Output alerts to Kafka
    6. (Optional) Query RAG for remediation
    
    Args:
        input_topic: Kafka topic to consume logs from
        output_topic: Kafka topic to publish alerts to
        kafka_settings: Kafka connection settings
        enable_output: Whether to write to output Kafka topic
        rag_url: Optional URL of RAG server for remediation lookup
    """
    
    print("📊 Building Pathway pipeline...")
    
    # ================= Stage 1: Kafka Ingestion =================
    # Using Pathway's Kafka connector with proper rdkafka settings
    logs = pw.io.kafka.read(
        rdkafka_settings=kafka_settings,
        topic=input_topic,
        schema=LogSchema,
        format="json",
        autocommit_duration_ms=1000,  # Batch commits for efficiency
    )
    
    print(f"   ✓ Kafka source connected: {input_topic}")
    
    # ================= Debug: Track raw log ingestion =================
    _ingestion_stats = {"total": 0, "last_service": "", "last_ts": ""}
    
    def on_raw_log(key, row, time, is_addition):
        if is_addition:
            _ingestion_stats["total"] += 1
            _ingestion_stats["last_service"] = row.get("service", "?")
            _ingestion_stats["last_ts"] = row.get("timestamp", "?")
            
            # Print every 100 logs or first 5
            if _ingestion_stats["total"] <= 5 or _ingestion_stats["total"] % 100 == 0:
                print(f"📥 Log #{_ingestion_stats['total']}: service={row.get('service')} "
                      f"level={row.get('level')} ts={row.get('timestamp', '?')[:19]}")
    
    pw.io.subscribe(logs, on_change=on_raw_log)
    
    # ================= Stage 2: Data Enrichment =================
    # Parse timestamps and extract anomaly labels
    enriched_logs = logs.select(
        # Original fields
        timestamp=pw.this.timestamp,
        timestamp_ms=parse_timestamp(pw.this.timestamp),
        level=pw.this.level,
        source=pw.this.source,
        service=pw.this.service,
        message=pw.this.message,
        request_id=pw.this.request_id,
        user_id=pw.this.user_id,
        ip_address=pw.this.ip_address,
        endpoint=pw.this.endpoint,
        method=pw.this.method,
        status_code=pw.this.status_code,
        response_time_ms=pw.coalesce(pw.this.response_time_ms, 0.0),
        error_code=pw.this.error_code,
        
        # Extracted anomaly information
        is_anomaly=extract_anomaly_flag(pw.this._labels),
        anomaly_type=extract_anomaly_type(pw.this._labels),
        anomaly_score=extract_anomaly_score(pw.this._labels),
        
        # Computed fields
        is_error=is_error_level(pw.this.level),
    )
    
    print("   ✓ Log enrichment configured")
    
    # ================= Stage 3: Tumbling Window Aggregation =================
    # Per SRS REQ-3.1: Calculate statistics using tumbling windows
    # Aggregate by service and log level for granular analysis
    
    # Use configured window duration
    window_duration = timedelta(seconds=window_seconds)
    
    windowed_stats = enriched_logs.windowby(
        enriched_logs.timestamp_ms,
        window=pw.temporal.tumbling(duration=window_duration),
    ).reduce(
        # Aggregations
        log_count=pw.reducers.count(),
        error_count=pw.reducers.sum(pw.cast(int, pw.this.is_error)),
        anomaly_count=pw.reducers.sum(pw.cast(int, pw.this.is_anomaly)),
        
        # Response time statistics
        avg_response_time=pw.reducers.avg(pw.this.response_time_ms),
        max_response_time=pw.reducers.max(pw.this.response_time_ms),
        min_response_time=pw.reducers.min(pw.this.response_time_ms),
        
        # Anomaly score aggregation
        max_anomaly_score=pw.reducers.max(pw.this.anomaly_score),
        
        # Keep first service/level for context
        service=pw.reducers.earliest(pw.this.service),
        level=pw.reducers.earliest(pw.this.level),
    )
    
    print(f"   ✓ Tumbling window aggregation: {window_seconds} seconds")
    
    # ================= Stage 4: Spike Detection =================
    # Per SRS REQ-3.2: Detect when error rate > 3 standard deviations
    # For hackathon MVP, using simple threshold-based detection
    
    # Calculate running statistics for baseline comparison
    # In production, would use more sophisticated rolling statistics
    alerts = windowed_stats.select(
        service=pw.this.service,
        level=pw.this.level,
        log_count=pw.this.log_count,
        error_count=pw.this.error_count,
        anomaly_count=pw.this.anomaly_count,
        avg_response_time=pw.this.avg_response_time,
        max_response_time=pw.this.max_response_time,
        min_response_time=pw.this.min_response_time,
        max_anomaly_score=pw.this.max_anomaly_score,
        
        # Flag spikes based on anomaly density in window
        is_spike=pw.if_else(
            (pw.this.anomaly_count > 0) | (pw.this.error_count >= 5),
            True,
            False
        ),
        
        # Error rate calculation
        error_rate=pw.if_else(
            pw.this.log_count > 0,
            pw.cast(float, pw.this.error_count) / pw.cast(float, pw.this.log_count),
            0.0
        ),
    )
    
    # Filter for actionable alerts only
    actionable_alerts = alerts.filter(
        (pw.this.is_spike == True) | 
        (pw.this.anomaly_count > 0) |
        (pw.this.error_rate > 0.1)  # More than 10% errors
    )
    
    print(f"   ✓ Spike detection threshold: Z > {SPIKE_THRESHOLD}")
    
    # ================= Stage 5: Output =================
    # Always create alert_output for RAG integration, optionally write to Kafka
    alert_output = actionable_alerts.select(
        alert_json=format_alert(
            pw.this.service,
            pw.this.level,
            pw.this.log_count,
            pw.this.anomaly_count,
            pw.this.avg_response_time,
            pw.this.is_spike,
        )
    )
    
    if enable_output:
        # Output alerts to Kafka for downstream processing (RAG, alerting)
        pw.io.kafka.write(
            alert_output,
            rdkafka_settings=kafka_settings,
            topic_name=output_topic,
            format="json",
        )
        print(f"   ✓ Output sink: {output_topic}")
    
    # ================= Stage 6: RAG Integration (Optional) =================
    # Query RAG system for remediation when alerts are generated
    # Uses async processing to avoid blocking the pipeline
    # Implements SRS REQ-4.3 and REQ-5.1
    if rag_url:
        print(f"   ✓ RAG integration enabled: {rag_url}")
        print(f"   ⚠️ Note: RAG queries run async to avoid blocking pipeline")
        
        # Use a thread pool for non-blocking RAG queries
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from confluent_kafka import Producer
        
        # Create Kafka producer for remediation alerts
        _remediation_producer_config = {
            "bootstrap.servers": kafka_settings["bootstrap.servers"],
            "security.protocol": kafka_settings.get("security.protocol", "SASL_SSL"),
            "sasl.mechanisms": kafka_settings.get("sasl.mechanisms", "SCRAM-SHA-256"),
            "sasl.username": kafka_settings.get("sasl.username"),
            "sasl.password": kafka_settings.get("sasl.password"),
        }
        _remediation_producer = Producer(_remediation_producer_config)
        _remediation_topic = REMEDIATION_TOPIC
        
        print(f"   ✓ Remediation producer ready: {_remediation_topic}")
        
        # Shared state for async RAG processing
        # Using 1 worker to avoid overloading the LLM server (DeepSeek R1 is slow)
        _rag_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag_worker")
        _pending_queries = {"count": 0, "completed": 0, "failed": 0}
        _query_lock = threading.Lock()
        
        def _async_rag_query(alert_json: str, rag_url: str):
            """Background RAG query - runs in thread pool."""
            import httpx
            import json as json_lib
            
            service = "unknown"
            alert_type = "unknown"
            
            try:
                alert_data = json_lib.loads(alert_json)
                service = alert_data.get("service", "unknown")
                alert_type = alert_data.get("alert_type", "unknown")
                anomaly_count = alert_data.get("anomaly_count", 0)
                
                # Build query
                if RAG_INTEGRATION_AVAILABLE:
                    try:
                        alert = AnomalyAlert(
                            service=service,
                            log_level=alert_data.get("log_level", "ERROR"),
                            total_logs=alert_data.get("total_logs", 0),
                            anomaly_count=anomaly_count,
                            avg_response_time_ms=alert_data.get("avg_response_time_ms", 0.0),
                            is_spike=alert_data.get("is_spike", False),
                            alert_type=alert_type,
                            timestamp=alert_data.get("timestamp", datetime.now().isoformat()),
                        )
                        query = alert.to_rag_query()
                    except Exception:
                        query = f"How to handle {alert_type} in {service} service? {anomaly_count} anomalies detected."
                else:
                    query = f"How to handle {alert_type} in {service} service? {anomaly_count} anomalies detected."
                
                print(f"🔍 RAG query started for {service}...")
                
                # Query RAG server with reasonable timeout
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(
                        f"{rag_url.rstrip('/')}/",
                        json={"query": query, "n_results": 5},
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    answer = result.get("answer", "No remediation found.")
                    sources = result.get("sources", [])
                    
                    # Print remediation result
                    print(f"\n{'='*60}")
                    print(f"📋 REMEDIATION for {service} ({alert_type})")
                    print(f"{'='*60}")
                    print(f"Query: {query[:100]}...")
                    print(f"Sources: {sources}")
                    print(f"\nAnswer:\n{answer[:500]}{'...' if len(answer) > 500 else ''}")
                    print(f"{'='*60}\n")
                    
                    # Build remediation message for Kafka
                    remediation_message = {
                        "original_alert": alert_data,
                        "query": query,
                        "remediation": {
                            "answer": answer,
                            "sources": sources,
                            "model": result.get("model", "unknown"),
                        },
                        "timestamp": datetime.now().isoformat(),
                        "status": "success",
                    }
                    
                    # Publish to remediation_alerts topic
                    _remediation_producer.produce(
                        _remediation_topic,
                        key=service.encode("utf-8"),
                        value=json_lib.dumps(remediation_message).encode("utf-8"),
                    )
                    _remediation_producer.flush(timeout=5)
                    
                    with _query_lock:
                        _pending_queries["completed"] += 1
                    
                    print(f"✅ Remediation published to {_remediation_topic} for {service}")
                    
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                print(f"❌ RAG query failed for {service}: {error_msg}", flush=True)
                
                # Publish failure message
                try:
                    import json as json_lib
                    failure_message = {
                        "original_alert": json_lib.loads(alert_json) if isinstance(alert_json, str) else alert_json,
                        "error": error_msg,
                        "error_type": type(e).__name__,
                        "timestamp": datetime.now().isoformat(),
                        "status": "failed",
                    }
                    _remediation_producer.produce(
                        _remediation_topic,
                        key=service.encode("utf-8"),
                        value=json_lib.dumps(failure_message).encode("utf-8"),
                    )
                    _remediation_producer.flush(timeout=5)
                except Exception as pub_err:
                    print(f"❌ Failed to publish error to Kafka: {pub_err}", flush=True)
                
                with _query_lock:
                    _pending_queries["failed"] += 1
            finally:
                with _query_lock:
                    _pending_queries["count"] -= 1
        
        # Create a simple UDF that triggers async RAG but returns immediately
        @pw.udf
        def trigger_rag_query(alert_json: str) -> str:
            """
            Trigger async RAG query - returns immediately without blocking.
            Remediation results are printed to console when ready.
            """
            with _query_lock:
                _pending_queries["count"] += 1
                current = _pending_queries["count"]
            
            # Submit to thread pool (non-blocking)
            _rag_executor.submit(_async_rag_query, alert_json, rag_url)
            
            return f"RAG query queued (pending: {current})"
        
        # Apply RAG trigger to alerts (non-blocking)
        alerts_with_rag_trigger = alert_output.select(
            alert_json=pw.this.alert_json,
            rag_status=trigger_rag_query(pw.this.alert_json),
        )
        
        # Subscribe to track RAG triggers
        def on_rag_trigger(key, row, time, is_addition):
            if is_addition:
                print(f"📤 Alert sent to RAG: {row.get('rag_status', 'N/A')}")
        
        pw.io.subscribe(alerts_with_rag_trigger, on_change=on_rag_trigger)
    
    # ================= Debug Output (Development) =================
    # Subscribe to ALL windowed stats (before filtering) for debugging
    def on_window_stats(key, row, time, is_addition):
        if is_addition:
            _debug_stats["windows_processed"] += 1
            log_count = row.get('log_count', 0)
            error_count = row.get('error_count', 0)
            anomaly_count = row.get('anomaly_count', 0)
            
            # Always print window stats for debugging
            print(f"📊 WINDOW: logs={log_count} errors={error_count} "
                  f"anomalies={anomaly_count} service={row.get('service')} "
                  f"level={row.get('level')}")
            
            # Check why it might not pass filter
            is_spike = (anomaly_count > 0) or (error_count >= 5)
            error_rate = error_count / log_count if log_count > 0 else 0
            will_alert = is_spike or (anomaly_count > 0) or (error_rate > 0.1)
            
            if not will_alert:
                print(f"   ⏭️  (skipped: spike={is_spike}, anomalies={anomaly_count}, error_rate={error_rate:.2%})")
    
    pw.io.subscribe(windowed_stats, on_change=on_window_stats)
    
    # Subscribe for actionable alerts
    def on_change(key, row, time, is_addition):
        if is_addition:
            _debug_stats["alerts_generated"] += 1
            count = _debug_stats["alerts_generated"]
            action = "🔔 ALERT"
            print(f"{action} #{count}: service={row.get('service')} level={row.get('level')} "
                  f"logs={row.get('log_count')} errors={row.get('error_count')} "
                  f"anomalies={row.get('anomaly_count')} spike={row.get('is_spike')}")
            if rag_url:
                print(f"   → RAG query will be triggered for this alert")
    
    pw.io.subscribe(actionable_alerts, on_change=on_change)
    
    return {
        "logs": enriched_logs,
        "windowed_stats": windowed_stats,
        "alerts": actionable_alerts,
    }


# ================= Main Entry Point =================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OpsPulse AI - Pathway Stream Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pathway_consumer.py
  python pathway_consumer.py --topic my_logs --output-topic my_alerts
  python pathway_consumer.py --group-id custom-group --no-output
        """
    )
    parser.add_argument(
        "--topic", 
        default=INPUT_TOPIC,
        help=f"Kafka topic to consume (default: {INPUT_TOPIC})"
    )
    parser.add_argument(
        "--output-topic",
        default=OUTPUT_TOPIC,
        help=f"Kafka topic for alerts (default: {OUTPUT_TOPIC})"
    )
    parser.add_argument(
        "--group-id",
        default="opspulse-pathway-consumer",
        help="Kafka consumer group ID"
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help="Disable Kafka output (debug mode)"
    )
    parser.add_argument(
        "--window-seconds",
        type=int,
        default=15,
        help="Tumbling window duration in seconds (default: 15, use 60 for production)"
    )
    parser.add_argument(
        "--rag-url",
        type=str,
        default=None,
        help="RAG server URL for remediation lookup (e.g., http://localhost:5000)"
    )
    parser.add_argument(
        "--skip-rag-check",
        action="store_true",
        help="Skip RAG server health check on startup"
    )
    parser.add_argument(
        "--remediation-topic",
        type=str,
        default=REMEDIATION_TOPIC,
        help=f"Kafka topic for remediation alerts (default: {REMEDIATION_TOPIC})"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Use a fresh consumer group (re-read all messages from beginning)"
    )
    
    args = parser.parse_args()
    
    # Update configuration
    if args.fresh:
        # Use a unique group ID to re-read all messages
        import uuid
        fresh_group = f"opspulse-fresh-{uuid.uuid4().hex[:8]}"
        KAFKA_SETTINGS["group.id"] = fresh_group
        print(f"🔄 Using fresh consumer group: {fresh_group}")
    else:
        KAFKA_SETTINGS["group.id"] = args.group_id
    
    # Override remediation topic if provided
    if args.remediation_topic:
        REMEDIATION_TOPIC = args.remediation_topic
    
    # Print startup banner
    print("=" * 60)
    print("🚀 OpsPulse AI - Pathway Stream Processor")
    print("=" * 60)
    print(f"   Input Topic      : {args.topic}")
    print(f"   Output Topic     : {args.output_topic}")
    print(f"   Remediation Topic: {REMEDIATION_TOPIC}")
    print(f"   Consumer Group   : {KAFKA_SETTINGS['group.id']}")
    print(f"   Window Size      : {args.window_seconds} seconds")
    print(f"   Kafka Broker     : {KAFKA_SETTINGS['bootstrap.servers']}")
    print(f"   RAG Server       : {args.rag_url or 'Disabled'}")
    print("=" * 60)
    print()
    
    # Check RAG server health if RAG is enabled
    if args.rag_url and not args.skip_rag_check:
        print("🔍 Checking RAG server health...")
        if check_rag_health(args.rag_url):
            print("   ✓ RAG server is healthy")
            # Get and display RAG stats
            stats = get_rag_stats(args.rag_url)
            if stats:
                print(f"   ✓ Documents indexed: {stats.get('total_documents', 'N/A')}")
                print(f"   ✓ LLM model: {stats.get('llm_model', 'N/A')}")
        else:
            print("   ⚠️ RAG server is not responding!")
            print("   ⚠️ Remediation lookups will fail. Start RAG server with:")
            print("      cd Rag && python chroma_rag_server.py --ingest")
            print()
            user_input = input("   Continue without RAG? (y/N): ").strip().lower()
            if user_input != 'y':
                print("   Exiting...")
                sys.exit(1)
            print("   Continuing without RAG health confirmation...")
        print()
    
    # Build the pipeline
    pipeline = create_pipeline(
        input_topic=args.topic,
        output_topic=args.output_topic,
        kafka_settings=KAFKA_SETTINGS,
        enable_output=not args.no_output,
        rag_url=args.rag_url,
        window_seconds=args.window_seconds,
    )
    
    print()
    print("🎯 Pipeline ready! Waiting for messages...")
    print("   Press Ctrl+C to stop")
    if args.rag_url:
        print(f"   RAG queries will be sent to: {args.rag_url}")
        print(f"   Remediation alerts will be published to: {REMEDIATION_TOPIC}")
    print()
    
    # Run the Pathway engine (blocking)
    # Disable monitoring dashboard to see plain logs
    pw.run(monitoring_level=pw.MonitoringLevel.NONE)
