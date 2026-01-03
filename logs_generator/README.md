# Synthetic Logs Generator

A configurable synthetic log generator for testing and training anomaly detection systems. Generates realistic log data with various anomaly patterns that can be used as input for ML-based anomaly detection and automated remediation projects.

## Features

- **Realistic Log Generation**: Generates logs from multiple sources (web servers, applications, databases, infrastructure)
- **Configurable Anomaly Patterns**:
  - Error spikes (sudden increase in error rates)
  - Latency degradation (gradual performance slowdown)
  - Security threats (brute force, SQL injection, XSS, unauthorized access)
  - Resource exhaustion (memory, CPU, disk, connections)
  - Service outages (complete or intermittent)
  - Data anomalies (null values, out of range, format errors)
- **Multiple Output Formats**: JSON or text format
- **Flexible Output Destinations**: stdout, file, or both
- **File Rotation**: Automatic log file rotation based on size
- **ML-Ready Labels**: Optional anomaly labels included for supervised learning

## Installation

```bash
cd logs_generator
pip install -r requirements.txt
```

## Quick Start

### CLI Usage

```bash
# Generate 1000 logs with default settings (output to file)
python -m logs_generator

# Generate 5000 logs to stdout
python -m logs_generator --total 5000 --output stdout

# Generate logs in text format
python -m logs_generator --format text

# Higher anomaly rate (20%)
python -m logs_generator --anomaly-rate 0.2

# Streaming mode (continuous generation)
python -m logs_generator --total 0 --interval 0.5
```

### Web Server

```bash
# Start the FastAPI server
python -m logs_generator.server

# Or with uvicorn directly
uvicorn logs_generator.server:app --reload --port 8000
```

The server will be available at `http://localhost:8000` with interactive docs at `/docs`.

## Configuration

Edit `config.yaml` to customize the generator:

### Generator Settings
```yaml
generator:
  batch_size: 100      # Logs per batch
  interval: 1.0        # Seconds between batches
  total_logs: 1000     # Total logs (0 = unlimited)
```

### Log Sources
```yaml
sources:
  - name: "web-server"
    weight: 0.4
    services: ["nginx", "apache", "traefik"]
  - name: "application"
    weight: 0.3
    services: ["auth-service", "payment-service", "user-service"]
```

### Anomaly Configuration
```yaml
anomalies:
  probability: 0.05    # 5% chance of anomaly per batch
  
  types:
    error_spike:
      enabled: true
      weight: 0.25
      duration_logs: 20
      error_rate: 0.8
    
    latency_degradation:
      enabled: true
      weight: 0.20
      duration_logs: 50
      multiplier: 5.0
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--config, -c` | Path to config file (default: config.yaml) |
| `--total, -n` | Total logs to generate |
| `--batch-size, -b` | Batch size |
| `--output, -o` | Output destination (stdout/file/both) |
| `--format, -f` | Output format (json/text) |
| `--output-path, -p` | Output file path |
| `--anomaly-rate, -a` | Anomaly probability (0.0-1.0) |
| `--no-labels` | Exclude anomaly labels |
| `--interval, -i` | Interval between batches (seconds) |

## REST API Endpoints

When running the FastAPI server, the following endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/api/status` | GET | Generator status and statistics |
| `/api/config` | GET | Current configuration |
| `/api/config/generator` | PUT | Update generator config |
| `/api/config/anomalies` | PUT | Update anomaly config |
| `/api/generate` | POST | Generate a batch of logs |
| `/api/generate/single` | POST | Generate a single log |
| `/api/inject-anomaly` | POST | Inject specific anomaly type |
| `/api/stream` | GET | Stream logs via SSE |
| `/api/reset` | POST | Reset statistics |
| `/ws/logs` | WebSocket | Real-time log streaming |
| `/health` | GET | Health check |

### Example API Usage

```bash
# Generate 100 logs
curl -X POST "http://localhost:8000/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"count": 100, "anomaly_rate": 0.1}'

# Inject an error spike anomaly
curl -X POST "http://localhost:8000/api/inject-anomaly" \
  -H "Content-Type: application/json" \
  -d '{"anomaly_type": "error_spike", "duration_logs": 30}'

# Stream logs (SSE)
curl "http://localhost:8000/api/stream?batch_size=10&interval=1"
```

### WebSocket Usage

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/logs');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received logs:', data.logs);
};

// Configure streaming
ws.send(JSON.stringify({
  action: 'configure',
  config: { batch_size: 5, interval: 0.5, anomaly_rate: 0.1 }
}));

// Inject anomaly
ws.send(JSON.stringify({
  action: 'inject_anomaly',
  anomaly_type: 'security_threat'
}));
```

## Output Format

### JSON Format (default)
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "ERROR",
  "source": "web-server",
  "service": "nginx",
  "message": "502 Bad Gateway - upstream auth-service unavailable",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "ip_address": "192.168.1.100",
  "response_time_ms": 3500.5,
  "status_code": 502,
  "endpoint": "/api/v1/auth/login",
  "method": "POST",
  "error_code": "ERR_SERVICE_UNAVAILABLE",
  "_labels": {
    "is_anomaly": true,
    "anomaly_type": "service_outage",
    "anomaly_score": 0.85
  }
}
```

### Text Format
```
[2024-01-15T10:30:45.123456] [ERROR   ] [web-server/nginx] [a1b2c3d4] 502 Bad Gateway - upstream auth-service unavailable (3500.50ms) [502] [ANOMALY:service_outage:0.85]
```

## Anomaly Types

### Error Spike
Sudden burst of error logs with high error rates (default 80%).

### Latency Degradation
Gradual increase in response times, simulating performance degradation.

### Security Threat
- Brute force attacks
- SQL injection attempts
- XSS attempts
- Unauthorized access

### Resource Exhaustion
- Memory pressure
- CPU saturation
- Disk full
- Connection pool exhaustion

### Service Outage
Complete or intermittent service failures.

### Data Anomaly
- Null/missing values
- Out-of-range values
- Format errors

## Usage for Anomaly Detection

The generated logs include labels that can be used for:

1. **Training supervised ML models**: Use `_labels.is_anomaly` as the target variable
2. **Evaluating detection algorithms**: Compare detected anomalies against ground truth
3. **Testing alerting systems**: Verify alert thresholds and escalation rules
4. **Benchmarking**: Measure detection latency and accuracy

### Example: Loading logs for ML training
```python
import json
import pandas as pd

# Load JSON lines file
logs = []
with open('output/logs_20240115_103045_0.json', 'r') as f:
    for line in f:
        logs.append(json.loads(line))

df = pd.DataFrame(logs)

# Extract features and labels
features = df[['level', 'source', 'service', 'response_time_ms', 'status_code']]
labels = df['_labels'].apply(lambda x: x['is_anomaly'])
```

## Project Structure

```
logs_generator/
├── __init__.py       # Package initialization
├── __main__.py       # CLI entry point
├── server.py         # FastAPI web server
├── config.yaml       # Default configuration
├── generator.py      # Main log generation engine
├── anomalies.py      # Anomaly pattern generators
├── models.py         # Data models (LogEntry, etc.)
├── templates.py      # Message templates
├── output.py         # Output handlers
├── requirements.txt  # Dependencies
└── README.md         # This file
```

## License

MIT License - Part of OpsPulse.ai project
