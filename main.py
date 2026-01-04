#!/usr/bin/env python
"""
OpsPulse AI - Unified Backend Runner

This module provides a unified entry point to run all backend components
of the OpsPulse AI system. It can launch:
  - RAG Server (ChromaDB + Gemini embeddings + DeepSeek LLM)
  - Pathway Consumer (Kafka log processing + anomaly detection)
  - Full Stack (both RAG and Pathway together)

Usage:
  python main.py --help                    # Show all options
  python main.py rag                       # Start RAG server only
  python main.py consumer                  # Start Pathway consumer only
  python main.py full                      # Start full stack
  python main.py full --ingest             # Full stack with PDF ingestion
"""

import argparse
import subprocess
import sys
import os
import time
import signal
from typing import Optional, List
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()

# Default configuration
DEFAULT_RAG_HOST = "0.0.0.0"
DEFAULT_RAG_PORT = 5000
DEFAULT_RAG_URL = f"http://localhost:{DEFAULT_RAG_PORT}"
DEFAULT_KAFKA_TOPIC = "raw_logs"
DEFAULT_OUTPUT_TOPIC = "processed_alerts"


class ProcessManager:
    """Manages subprocess lifecycle for backend services."""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully."""
        print("\n🛑 Shutdown signal received...")
        self.shutdown_all()
        sys.exit(0)
    
    def start_process(
        self,
        name: str,
        cmd: List[str],
        cwd: Optional[str] = None,
        env: Optional[dict] = None
    ) -> subprocess.Popen:
        """Start a subprocess and track it."""
        print(f"🚀 Starting {name}...")
        print(f"   Command: {' '.join(cmd)}")
        
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        
        process = subprocess.Popen(
            cmd,
            cwd=cwd or str(PROJECT_ROOT),
            env=process_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self.processes.append(process)
        return process
    
    def shutdown_all(self):
        """Gracefully shutdown all managed processes."""
        print("🔄 Shutting down all processes...")
        for process in self.processes:
            if process.poll() is None:  # Still running
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        self.processes.clear()
        print("✅ All processes stopped")


def check_rag_server_ready(
    url: str, 
    max_attempts: int = 30, 
    delay: float = 1.0,
    with_ingestion: bool = False
) -> bool:
    """
    Wait for RAG server to be ready.
    
    Args:
        url: RAG server URL
        max_attempts: Maximum number of attempts
        delay: Delay between attempts in seconds
        with_ingestion: If True, use longer timeout (PDF processing takes time)
    """
    import httpx
    
    # When ingesting PDFs, it can take 10+ minutes for large documents
    if with_ingestion:
        max_attempts = 600  # 10 minutes with 1s delay
        print(f"⏳ Waiting for RAG server at {url}...")
        print(f"   (PDF ingestion in progress - this may take several minutes)")
    else:
        print(f"⏳ Waiting for RAG server at {url}...")
    
    last_status_time = time.time()
    status_interval = 30  # Print status every 30 seconds
    
    for attempt in range(max_attempts):
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{url}/health")
                if response.status_code == 200:
                    print(f"   ✓ RAG server ready after {attempt + 1} seconds")
                    return True
        except Exception:
            pass
        
        # Print periodic status during long waits
        current_time = time.time()
        if with_ingestion and (current_time - last_status_time) >= status_interval:
            elapsed = attempt + 1
            print(f"   ... still waiting ({elapsed}s elapsed, PDF processing may take 5-10 minutes)")
            last_status_time = current_time
        
        if attempt < max_attempts - 1:
            time.sleep(delay)
    
    print(f"   ⚠️ RAG server not ready after {max_attempts} attempts")
    return False


def stream_process_output(process: subprocess.Popen, prefix: str = ""):
    """Stream process output to console."""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"{prefix}{line.rstrip()}")
            if process.poll() is not None:
                break
    except Exception:
        pass


def run_rag_server(
    ingest: bool = False,
    force_ingest: bool = False,
    host: str = DEFAULT_RAG_HOST,
    port: int = DEFAULT_RAG_PORT,
) -> subprocess.Popen:
    """Start the RAG server as a subprocess."""
    cmd = [
        sys.executable,
        "-m", "Rag.chroma_rag_server",
        "--config", str(PROJECT_ROOT / "Rag" / "config.yaml"),
        "--data", str(PROJECT_ROOT / "run book"),
    ]
    
    if force_ingest:
        cmd.append("--force-ingest")
    elif ingest:
        cmd.append("--ingest")
    
    return subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
    )


def run_pathway_consumer(
    rag_url: Optional[str] = None,
    topic: str = DEFAULT_KAFKA_TOPIC,
    output_topic: str = DEFAULT_OUTPUT_TOPIC,
    skip_rag_check: bool = False,
) -> subprocess.Popen:
    """Start the Pathway consumer as a subprocess."""
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "Message_queue_kafka" / "pathway_consumer.py"),
        "--topic", topic,
        "--output-topic", output_topic,
    ]
    
    if rag_url:
        cmd.extend(["--rag-url", rag_url])
    
    if skip_rag_check:
        cmd.append("--skip-rag-check")
    
    return subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
    )


def cmd_rag(args):
    """Run RAG server only."""
    print("=" * 60)
    print("🤖 OpsPulse AI - RAG Server")
    print("=" * 60)
    
    # Run RAG server in current process (blocking)
    rag_cmd = [
        sys.executable,
        str(PROJECT_ROOT / "Rag" / "chroma_rag_server.py"),
        "--config", str(PROJECT_ROOT / "Rag" / "config.yaml"),
        "--data", str(PROJECT_ROOT / "run book"),
    ]
    
    if args.force_ingest:
        rag_cmd.append("--force-ingest")
    elif args.ingest:
        rag_cmd.append("--ingest")
    
    os.execv(sys.executable, rag_cmd)


def cmd_consumer(args):
    """Run Pathway consumer only."""
    print("=" * 60)
    print("📊 OpsPulse AI - Pathway Consumer")
    print("=" * 60)
    
    # Run consumer in current process (blocking)
    consumer_cmd = [
        sys.executable,
        str(PROJECT_ROOT / "Message_queue_kafka" / "pathway_consumer.py"),
        "--topic", args.topic,
        "--output-topic", args.output_topic,
    ]
    
    if args.rag_url:
        consumer_cmd.extend(["--rag-url", args.rag_url])
    
    if args.skip_rag_check:
        consumer_cmd.append("--skip-rag-check")
    
    os.execv(sys.executable, consumer_cmd)


def cmd_full(args):
    """Run full stack (RAG + Pathway consumer)."""
    print("=" * 60)
    print("🚀 OpsPulse AI - Full Stack Backend")
    print("=" * 60)
    print()
    
    manager = ProcessManager()
    
    # Step 1: Start RAG server in background (redirect output to devnull or log file)
    print("📦 Step 1/3: Starting RAG Server (background)...")
    rag_cmd = [
        sys.executable,
        "-u",  # Unbuffered output for real-time logging
        str(PROJECT_ROOT / "Rag" / "chroma_rag_server.py"),
        "--config", str(PROJECT_ROOT / "Rag" / "config.yaml"),
        "--data", str(PROJECT_ROOT / "run book"),
    ]
    
    if args.force_ingest:
        rag_cmd.append("--force-ingest")
    elif args.ingest:
        rag_cmd.append("--ingest")
    
    # Start RAG server with output redirected to log file
    rag_log_path = PROJECT_ROOT / "rag_server.log"
    rag_log_file = open(rag_log_path, "w")
    
    # Set PYTHONUNBUFFERED for real-time logging
    rag_env = os.environ.copy()
    rag_env["PYTHONUNBUFFERED"] = "1"
    
    rag_process = subprocess.Popen(
        rag_cmd,
        cwd=str(PROJECT_ROOT),
        env=rag_env,
        stdout=rag_log_file,
        stderr=subprocess.STDOUT,
    )
    manager.processes.append(rag_process)
    print(f"   ✓ RAG server started (PID: {rag_process.pid})")
    print(f"   ✓ Logs: {rag_log_path}")
    print(f"   💡 View logs: tail -f rag_server.log")
    
    # Step 2: Wait for RAG server to be ready
    print("\n📦 Step 2/3: Waiting for RAG Server to be ready...")
    rag_url = f"http://localhost:{args.rag_port}"
    
    # Use longer timeout if ingesting PDFs
    with_ingestion = args.ingest or args.force_ingest
    if not check_rag_server_ready(rag_url, with_ingestion=with_ingestion):
        print("❌ RAG server failed to start. Check logs at:", rag_log_path)
        manager.shutdown_all()
        rag_log_file.close()
        sys.exit(1)
    
    # Step 3: Start Pathway consumer (foreground - output visible)
    print("\n📦 Step 3/3: Starting Pathway Consumer...")
    consumer_cmd = [
        sys.executable,
        str(PROJECT_ROOT / "Message_queue_kafka" / "pathway_consumer.py"),
        "--topic", args.topic,
        "--output-topic", args.output_topic,
        "--rag-url", rag_url,
        "--skip-rag-check",  # We already checked
        "--window-seconds", str(args.window_seconds),
    ]
    
    # Add --fresh flag if specified
    if args.fresh:
        consumer_cmd.append("--fresh")
    
    print(f"   ✓ Consumer command ready")
    
    # Print summary before starting consumer
    print()
    print("=" * 60)
    print("✅ OpsPulse AI Backend Running")
    print("=" * 60)
    print(f"   RAG Server       : {rag_url} (background, logs: rag_server.log)")
    print(f"   Kafka Input      : {args.topic}")
    print(f"   Kafka Output     : {args.output_topic}")
    print(f"   Remediation Topic: remediation_alerts")
    print(f"   Window Size      : {args.window_seconds} seconds")
    print()
    print("   Press Ctrl+C to stop all services")
    print()
    if with_ingestion:
        print("💡 TIP: Next time, run without --ingest for faster startup:")
        print("        python main.py full")
    print("=" * 60)
    print()
    print("🎯 Starting Pathway Consumer (output below)...")
    print("-" * 60)
    
    # Run consumer in foreground (replace current process to show output directly)
    # But first, set up cleanup for RAG server
    import atexit
    
    def cleanup():
        print("\n🔄 Cleaning up...")
        if rag_process.poll() is None:
            rag_process.terminate()
            try:
                rag_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rag_process.kill()
        rag_log_file.close()
        print("✅ RAG server stopped")
    
    atexit.register(cleanup)
    
    # Run consumer - this will block and show output
    try:
        consumer_process = subprocess.Popen(
            consumer_cmd,
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy(),
        )
        manager.processes.append(consumer_process)
        
        # Wait for consumer (blocking)
        consumer_process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted!")
    finally:
        cleanup()
        manager.shutdown_all()


def cmd_status(args):
    """Check status of OpsPulse services."""
    import httpx
    
    print("=" * 60)
    print("📊 OpsPulse AI - Service Status")
    print("=" * 60)
    print()
    
    # Check RAG server
    rag_url = f"http://localhost:{args.rag_port}"
    print(f"🔍 RAG Server ({rag_url}):")
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{rag_url}/health")
            if response.status_code == 200:
                print("   ✓ Status: Healthy")
                
                # Get stats
                stats_response = client.get(f"{rag_url}/stats")
                if stats_response.status_code == 200:
                    stats = stats_response.json()
                    print(f"   ✓ Documents indexed: {stats.get('total_documents', 'N/A')}")
                    print(f"   ✓ Collection: {stats.get('collection_name', 'N/A')}")
                    print(f"   ✓ LLM model: {stats.get('llm_model', 'N/A')}")
            else:
                print(f"   ⚠️ Status: Unhealthy (HTTP {response.status_code})")
    except httpx.ConnectError:
        print("   ✗ Status: Not running")
    except Exception as e:
        print(f"   ✗ Status: Error ({e})")
    
    print()
    print("💡 To start services:")
    print("   python main.py rag        # Start RAG server only")
    print("   python main.py consumer   # Start Pathway consumer only")
    print("   python main.py full       # Start full stack")


def main():
    parser = argparse.ArgumentParser(
        description="OpsPulse AI - Unified Backend Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py rag                       # Start RAG server only
  python main.py rag --ingest              # Start RAG with PDF ingestion
  python main.py consumer                  # Start Pathway consumer only
  python main.py consumer --rag-url http://localhost:5000  # Consumer with RAG
  python main.py full                      # Start full stack
  python main.py full --ingest             # Full stack with PDF ingestion
  python main.py status                    # Check service status
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # RAG command
    rag_parser = subparsers.add_parser("rag", help="Run RAG server only")
    rag_parser.add_argument("--ingest", action="store_true", help="Ingest PDFs on startup")
    rag_parser.add_argument("--force-ingest", action="store_true", help="Force re-ingest all PDFs")
    rag_parser.add_argument("--port", type=int, default=DEFAULT_RAG_PORT, help=f"RAG server port (default: {DEFAULT_RAG_PORT})")
    
    # Consumer command
    consumer_parser = subparsers.add_parser("consumer", help="Run Pathway consumer only")
    consumer_parser.add_argument("--rag-url", type=str, default=None, help="RAG server URL for remediation")
    consumer_parser.add_argument("--topic", type=str, default=DEFAULT_KAFKA_TOPIC, help=f"Kafka input topic (default: {DEFAULT_KAFKA_TOPIC})")
    consumer_parser.add_argument("--output-topic", type=str, default=DEFAULT_OUTPUT_TOPIC, help=f"Kafka output topic (default: {DEFAULT_OUTPUT_TOPIC})")
    consumer_parser.add_argument("--skip-rag-check", action="store_true", help="Skip RAG health check")
    
    # Full stack command
    full_parser = subparsers.add_parser("full", help="Run full stack (RAG + Pathway consumer)")
    full_parser.add_argument("--ingest", action="store_true", help="Ingest PDFs on startup")
    full_parser.add_argument("--force-ingest", action="store_true", help="Force re-ingest all PDFs")
    full_parser.add_argument("--rag-port", type=int, default=DEFAULT_RAG_PORT, help=f"RAG server port (default: {DEFAULT_RAG_PORT})")
    full_parser.add_argument("--topic", type=str, default=DEFAULT_KAFKA_TOPIC, help=f"Kafka input topic (default: {DEFAULT_KAFKA_TOPIC})")
    full_parser.add_argument("--output-topic", type=str, default=DEFAULT_OUTPUT_TOPIC, help=f"Kafka output topic (default: {DEFAULT_OUTPUT_TOPIC})")
    full_parser.add_argument("--window-seconds", type=int, default=15, help="Tumbling window duration in seconds (default: 15)")
    full_parser.add_argument("--fresh", action="store_true", help="Use fresh consumer group (re-read all messages)")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check service status")
    status_parser.add_argument("--rag-port", type=int, default=DEFAULT_RAG_PORT, help=f"RAG server port (default: {DEFAULT_RAG_PORT})")
    
    args = parser.parse_args()
    
    if args.command == "rag":
        cmd_rag(args)
    elif args.command == "consumer":
        cmd_consumer(args)
    elif args.command == "full":
        cmd_full(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        # No command - print help
        parser.print_help()
        print()
        print("=" * 60)
        print("🚀 OpsPulse AI - Quick Start")
        print("=" * 60)
        print()
        print("1. Start the full backend stack:")
        print("   python main.py full --ingest")
        print()
        print("2. In another terminal, start the producer:")
        print("   python Message_queue_kafka/producer.py --continuous")
        print()
        print("3. Watch the alerts and remediations flow!")
        print()


if __name__ == "__main__":
    main()
