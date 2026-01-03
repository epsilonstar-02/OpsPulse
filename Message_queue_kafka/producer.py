from confluent_kafka import Producer
import json
import requests
import time
import signal
import sys
import argparse
import threading
from typing import List, Dict, Any, Optional, Generator

# ================= Kafka Config =================
KAFKA_CONF = {
    "bootstrap.servers": "d5c2s6rrcoacstisf5a0.any.ap-south-1.mpx.prd.cloud.redpanda.com:9092",
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "SCRAM-SHA-256",
    "sasl.username": "ashutosh",
    "sasl.password": "768581",
    "client.id": "opspulse-producer",
}

TOPIC = "raw_logs"
DEFAULT_SERVER_URL = "http://34.56.145.168:8000"

# Global state for graceful shutdown
_running = True
_producer: Optional[Producer] = None
_stats = {"sent": 0, "anomalies": 0, "errors": 0}
_stats_lock = threading.Lock()


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global _running
    print("\n🛑 Shutdown signal received, stopping...")
    _running = False


def create_producer() -> Producer:
    """Create and return a Kafka producer"""
    return Producer(KAFKA_CONF)


# ================= Delivery Callback =================
def delivery_report(err, msg):
    """Callback for message delivery reports"""
    if err:
        print(f"❌ Delivery failed: {err}")
    else:
        print(f"✅ Delivered to {msg.topic()} [{msg.partition()}] offset {msg.offset()}")


def delivery_report_quiet(err, msg):
    """Quiet callback - only report errors"""
    global _stats
    with _stats_lock:
        if err:
            _stats["errors"] += 1
            print(f"❌ Delivery failed: {err}")


# ================= Fetch Logs from Server =================
def fetch_logs(
    server_url: str = DEFAULT_SERVER_URL,
    count: int = 100,
    anomaly_rate: float = 0.05,
    include_labels: bool = True,
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Fetch logs from the log generator HTTP server.
    
    Uses the /api/generate endpoint which returns a JSON response
    with a 'logs' array.
    
    Args:
        server_url: Base URL of the log generator server
        count: Number of logs to generate per request
        anomaly_rate: Probability of anomalies (0.0 to 1.0)
        include_labels: Include anomaly labels in output
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        List of log dictionaries
    """
    endpoint = f"{server_url}/api/generate"
    params = {
        "count": count,
        "anomaly_rate": anomaly_rate,
        "include_labels": include_labels,
        "format": "json"
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(endpoint, json=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # The /api/generate endpoint returns {"count": N, "anomaly_count": M, "logs": [...]}
            if isinstance(data, dict) and "logs" in data:
                return data["logs"]
            
            # Fallback: if response is a list directly
            if isinstance(data, list):
                return data
            
            print(f"⚠️ Unexpected response format: {type(data)}")
            return []
            
        except requests.exceptions.Timeout:
            print(f"⚠️ Request timeout (attempt {attempt + 1}/{max_retries})")
        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ Connection error (attempt {attempt + 1}/{max_retries}): {e}")
        except requests.exceptions.HTTPError as e:
            print(f"⚠️ HTTP error (attempt {attempt + 1}/{max_retries}): {e}")
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON decode error (attempt {attempt + 1}/{max_retries}): {e}")
        except Exception as e:
            print(f"⚠️ Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")
        
        if attempt < max_retries - 1:
            print(f"   Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    print("❌ All retry attempts failed")
    return []


# ================= Produce Logs =================
def send_logs_to_kafka(producer: Producer, logs: List[Dict[str, Any]], verbose: bool = True) -> int:
    """
    Send logs to Kafka topic.
    
    Args:
        producer: Kafka producer instance
        logs: List of log dictionaries to send
        verbose: Print delivery confirmation for each message
    
    Returns:
        Number of logs successfully queued
    """
    queued = 0
    for log in logs:
        try:
            producer.produce(
                topic=TOPIC,
                value=json.dumps(log).encode('utf-8'),
                callback=delivery_report if verbose else None
            )
            producer.poll(0)  # Trigger delivery callbacks
            queued += 1
        except BufferError:
            print("⚠️ Producer buffer full, waiting...")
            producer.poll(1)  # Wait for some messages to be delivered
            # Retry the message
            producer.produce(
                topic=TOPIC,
                value=json.dumps(log).encode('utf-8'),
                callback=delivery_report if verbose else None
            )
            queued += 1
        except Exception as e:
            print(f"❌ Failed to produce message: {e}")
    
    # Ensure all messages are sent
    producer.flush()
    return queued


def run_continuous(
    server_url: str = DEFAULT_SERVER_URL,
    batch_size: int = 100,
    interval: float = 5.0,
    anomaly_rate: float = 0.05,
    verbose: bool = True
):
    """
    Continuously fetch logs and send to Kafka.
    
    Args:
        server_url: Base URL of the log generator server
        batch_size: Number of logs to fetch per batch
        interval: Seconds between batches
        anomaly_rate: Probability of anomalies
        verbose: Print detailed delivery information
    """
    global _running, _producer
    
    _producer = create_producer()
    total_sent = 0
    batch_count = 0
    
    print(f"🚀 Starting continuous producer (batch_size={batch_size}, interval={interval}s)")
    print(f"   Server: {server_url}")
    print(f"   Topic: {TOPIC}")
    print("   Press Ctrl+C to stop\n")
    
    while _running:
        try:
            logs = fetch_logs(
                server_url=server_url,
                count=batch_size,
                anomaly_rate=anomaly_rate,
                include_labels=True
            )
            
            if logs:
                batch_count += 1
                sent = send_logs_to_kafka(_producer, logs, verbose=verbose)
                total_sent += sent
                
                anomaly_count = sum(1 for log in logs if log.get('_labels', {}).get('is_anomaly', False))
                print(f"📤 Batch {batch_count}: Sent {sent} logs ({anomaly_count} anomalies) | Total: {total_sent}")
            else:
                print("⚠️ No logs fetched, skipping batch")
            
            # Wait for next batch
            if _running:
                time.sleep(interval)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error in continuous loop: {e}")
            if _running:
                time.sleep(interval)
    
    print(f"\n✅ Producer stopped. Total logs sent: {total_sent}")
    if _producer:
        _producer.flush()


def run_once(
    server_url: str = DEFAULT_SERVER_URL,
    count: int = 100,
    anomaly_rate: float = 0.05,
    verbose: bool = True
):
    """
    Fetch and send logs once.
    
    Args:
        server_url: Base URL of the log generator server
        count: Number of logs to fetch
        anomaly_rate: Probability of anomalies
        verbose: Print detailed delivery information
    """
    producer = create_producer()
    
    print(f"📥 Fetching {count} logs from {server_url}...")
    logs = fetch_logs(
        server_url=server_url,
        count=count,
        anomaly_rate=anomaly_rate,
        include_labels=True
    )
    
    if logs:
        print(f"📤 Sending {len(logs)} logs to Kafka topic '{TOPIC}'...")
        sent = send_logs_to_kafka(producer, logs, verbose=verbose)
        anomaly_count = sum(1 for log in logs if log.get('_labels', {}).get('is_anomaly', False))
        print(f"✅ Successfully sent {sent} logs ({anomaly_count} anomalies)")
    else:
        print("❌ No logs to send")


# ================= Streaming Mode =================
def stream_logs_from_api(
    server_url: str = DEFAULT_SERVER_URL,
    batch_size: int = 1,
    interval: float = 0.5,
    anomaly_rate: float = 0.05,
    include_labels: bool = True
) -> Generator[Dict[str, Any], None, None]:
    """
    Stream logs from the NDJSON streaming endpoint.
    
    Args:
        server_url: Base URL of the log generator server
        batch_size: Number of logs per streaming batch
        interval: Server-side interval between log batches
        anomaly_rate: Probability of anomalies
        include_labels: Include anomaly labels
        
    Yields:
        Individual log dictionaries
    """
    endpoint = f"{server_url}/api/stream/ndjson"
    params = {
        "batch_size": batch_size,
        "interval": interval,
        "anomaly_rate": anomaly_rate,
        "include_labels": str(include_labels).lower()
    }
    
    while _running:
        try:
            print(f"🔗 Connecting to streaming endpoint: {endpoint}")
            
            with requests.get(endpoint, params=params, stream=True, timeout=None) as response:
                response.raise_for_status()
                print("✅ Connected to log stream")
                
                for line in response.iter_lines():
                    if not _running:
                        break
                    
                    if line:
                        try:
                            log = json.loads(line.decode('utf-8'))
                            yield log
                        except json.JSONDecodeError as e:
                            print(f"⚠️ Failed to parse log: {e}")
                            continue
                            
        except requests.exceptions.ConnectionError as e:
            if _running:
                print(f"⚠️ Connection lost: {e}")
                print("   Reconnecting in 5 seconds...")
                time.sleep(5)
        except requests.exceptions.Timeout:
            if _running:
                print("⚠️ Connection timeout, reconnecting...")
                time.sleep(2)
        except Exception as e:
            if _running:
                print(f"❌ Stream error: {e}")
                print("   Reconnecting in 5 seconds...")
                time.sleep(5)


def run_streaming(
    server_url: str = DEFAULT_SERVER_URL,
    batch_size: int = 10,
    interval: float = 1.0,
    anomaly_rate: float = 0.05,
    verbose: bool = False
):
    """
    Stream logs continuously from API and send to Kafka in real-time.
    
    This mode connects to the server's NDJSON streaming endpoint and
    sends each log to Kafka as it arrives.
    
    Args:
        server_url: Base URL of the log generator server
        batch_size: Number of logs per streaming batch (server-side)
        interval: Interval between batches on server (seconds)
        anomaly_rate: Probability of anomalies
        verbose: Print delivery confirmation for each message
    """
    global _running, _producer, _stats
    
    _producer = create_producer()
    _stats = {"sent": 0, "anomalies": 0, "errors": 0}
    last_status_time = time.time()
    status_interval = 10  # Print status every 10 seconds
    
    print("🌊 Starting STREAMING producer mode")
    print(f"   Server: {server_url}")
    print(f"   Topic: {TOPIC}")
    print(f"   Batch size: {batch_size}, Interval: {interval}s")
    print("   Press Ctrl+C to stop\n")
    
    try:
        for log in stream_logs_from_api(
            server_url=server_url,
            batch_size=batch_size,
            interval=interval,
            anomaly_rate=anomaly_rate,
            include_labels=True
        ):
            if not _running:
                break
            
            try:
                # Send to Kafka immediately
                _producer.produce(
                    topic=TOPIC,
                    value=json.dumps(log).encode('utf-8'),
                    callback=delivery_report if verbose else delivery_report_quiet
                )
                _producer.poll(0)
                
                with _stats_lock:
                    _stats["sent"] += 1
                    if log.get('_labels', {}).get('is_anomaly', False):
                        _stats["anomalies"] += 1
                
                # Print periodic status update
                current_time = time.time()
                if current_time - last_status_time >= status_interval:
                    with _stats_lock:
                        rate = _stats["sent"] / (current_time - last_status_time + status_interval)
                        print(f"📊 Status: {_stats['sent']} sent | {_stats['anomalies']} anomalies | {_stats['errors']} errors | ~{rate:.1f} logs/sec")
                    last_status_time = current_time
                    
            except BufferError:
                print("⚠️ Buffer full, flushing...")
                _producer.flush()
                # Retry
                _producer.produce(
                    topic=TOPIC,
                    value=json.dumps(log).encode('utf-8'),
                    callback=delivery_report if verbose else delivery_report_quiet
                )
            except Exception as e:
                with _stats_lock:
                    _stats["errors"] += 1
                print(f"❌ Failed to produce: {e}")
                
    except KeyboardInterrupt:
        pass
    finally:
        if _producer:
            print("\n🔄 Flushing remaining messages...")
            _producer.flush()
        
        with _stats_lock:
            print(f"\n📊 Final Statistics:")
            print(f"   Total sent: {_stats['sent']}")
            print(f"   Anomalies: {_stats['anomalies']}")
            print(f"   Errors: {_stats['errors']}")
        print("✅ Streaming producer stopped")


# ================= Main =================
if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    parser = argparse.ArgumentParser(description="OpsPulse Kafka Log Producer")
    parser.add_argument(
        "--server", "-s",
        default=DEFAULT_SERVER_URL,
        help=f"Log generator server URL (default: {DEFAULT_SERVER_URL})"
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=100,
        help="Number of logs per batch (default: 100)"
    )
    parser.add_argument(
        "--anomaly-rate", "-a",
        type=float,
        default=0.05,
        help="Anomaly rate 0.0-1.0 (default: 0.05)"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run in continuous batch mode (fetches batches periodically)"
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Run in streaming mode (connects to NDJSON stream, real-time)"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=1.0,
        help="Interval between batches (default: 1.0s)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress per-message delivery reports"
    )
    
    args = parser.parse_args()
    
    try:
        if args.stream:
            # Streaming mode - real-time NDJSON stream
            run_streaming(
                server_url=args.server,
                batch_size=args.count,
                interval=args.interval,
                anomaly_rate=args.anomaly_rate,
                verbose=not args.quiet
            )
        elif args.continuous:
            # Continuous batch mode - periodic batch fetches
            run_continuous(
                server_url=args.server,
                batch_size=args.count,
                interval=args.interval,
                anomaly_rate=args.anomaly_rate,
                verbose=not args.quiet
            )
        else:
            # One-shot mode
            run_once(
                server_url=args.server,
                count=args.count,
                anomaly_rate=args.anomaly_rate,
                verbose=not args.quiet
            )
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
