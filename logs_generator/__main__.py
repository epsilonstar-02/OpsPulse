"""
Synthetic Logs Generator - Main Entry Point

This script generates realistic synthetic logs with configurable
anomaly patterns for testing anomaly detection systems.

Usage:
    python -m logs_generator                    # Use default config
    python -m logs_generator --config custom.yaml
    python -m logs_generator --total 5000       # Generate 5000 logs
    python -m logs_generator --output stdout    # Output to stdout
    python -m logs_generator --format text      # Text format instead of JSON
"""
import argparse
import sys
from pathlib import Path

import yaml

from .generator import LogGenerator, create_generator
from .output import create_output_handler


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    path = Path(config_path)
    if not path.exists():
        # Try relative to package directory
        package_dir = Path(__file__).parent
        path = package_dir / config_path
    
    if not path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)
    
    with open(path, "r") as f:
        return yaml.safe_load(f)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Generate synthetic logs for anomaly detection"
    )
    
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    
    parser.add_argument(
        "--total", "-n",
        type=int,
        default=None,
        help="Total number of logs to generate (overrides config)"
    )
    
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=None,
        help="Batch size for log generation (overrides config)"
    )
    
    parser.add_argument(
        "--output", "-o",
        choices=["stdout", "file", "both"],
        default=None,
        help="Output destination (overrides config)"
    )
    
    parser.add_argument(
        "--format", "-f",
        choices=["json", "text"],
        default=None,
        help="Output format (overrides config)"
    )
    
    parser.add_argument(
        "--output-path", "-p",
        default=None,
        help="Output file path (overrides config)"
    )
    
    parser.add_argument(
        "--anomaly-rate", "-a",
        type=float,
        default=None,
        help="Anomaly probability 0.0-1.0 (overrides config)"
    )
    
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Exclude anomaly labels from output"
    )
    
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=None,
        help="Interval between batches in seconds (overrides config)"
    )
    
    return parser.parse_args()


def apply_overrides(config: dict, args: argparse.Namespace) -> dict:
    """Apply command line overrides to config"""
    
    if args.total is not None:
        config.setdefault("generator", {})["total_logs"] = args.total
    
    if args.batch_size is not None:
        config.setdefault("generator", {})["batch_size"] = args.batch_size
    
    if args.interval is not None:
        config.setdefault("generator", {})["interval"] = args.interval
    
    if args.output is not None:
        config.setdefault("output", {})["destination"] = args.output
    
    if args.format is not None:
        config.setdefault("output", {})["format"] = args.format
    
    if args.output_path is not None:
        config.setdefault("output", {}).setdefault("file", {})["path"] = args.output_path
    
    if args.anomaly_rate is not None:
        config.setdefault("anomalies", {})["probability"] = args.anomaly_rate
    
    if args.no_labels:
        config.setdefault("output", {})["include_labels"] = False
    
    return config


def main():
    """Main entry point"""
    args = parse_args()
    
    # Load config
    print(f"Loading configuration from: {args.config}")
    config = load_config(args.config)
    
    # Apply command line overrides
    config = apply_overrides(config, args)
    
    # Create output handler
    output_handler = create_output_handler(config)
    
    # Create and run generator
    generator = create_generator(config)
    
    total = config.get("generator", {}).get("total_logs", 1000)
    print(f"Starting log generation...")
    print(f"  Total logs: {total if total > 0 else 'unlimited (streaming mode)'}")
    print(f"  Anomaly rate: {config.get('anomalies', {}).get('probability', 0.05):.1%}")
    print(f"  Output: {config.get('output', {}).get('destination', 'stdout')}")
    print(f"  Format: {config.get('output', {}).get('format', 'json')}")
    print("-" * 50)
    
    generator.run(output_handler)


if __name__ == "__main__":
    main()
