# OpsPulse AI - Dashboard Backend API

Real-time analytics and monitoring API for the OpsPulse AI dashboard.

## Features

- 📊 **Real-time Analytics** - Live metrics, service stats, and anomaly tracking
- 🔌 **WebSocket Support** - Real-time data streaming to dashboard
- 🏥 **Health Monitoring** - Component health checks and system status
- 📈 **Time Series Data** - Historical data for charts and visualizations
- 🔔 **Alert Management** - View, acknowledge, and resolve alerts
- 🤖 **RAG Integration** - Query remediation suggestions

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Start the API Server

```bash
# From project root
python -m backend.main

# Or with uvicorn
uvicorn backend.main:app --reload --port 8001
```

### 3. Access the API

- **API Docs**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
- **WebSocket**: ws://localhost:8001/ws/live

## API Endpoints

### Analytics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analytics/overview` | GET | Dashboard overview with key metrics |
| `/api/analytics/summary` | GET | Complete analytics summary |
| `/api/analytics/services` | GET | Service statistics |
| `/api/analytics/anomalies` | GET | Anomaly detection metrics |
| `/api/analytics/pipeline` | GET | Pipeline performance metrics |
| `/api/analytics/realtime` | GET | Real-time statistics |
| `/api/analytics/timeseries/{metric}` | GET | Time series data for charts |

### Logs & Alerts

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/logs/recent` | GET | Recent log entries |
| `/api/logs/generate` | POST | Trigger log generation |
| `/api/alerts/recent` | GET | Recent alerts |
| `/api/alerts/{id}` | GET | Alert details with remediation |
| `/api/alerts/{id}/acknowledge` | POST | Acknowledge an alert |
| `/api/alerts/{id}/resolve` | POST | Mark alert as resolved |
| `/api/remediations/recent` | GET | Recent remediation suggestions |
| `/api/remediations/query` | POST | Query RAG for remediation |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/system/health` | GET | Full system health check |
| `/api/system/info` | GET | System information |
| `/api/system/components` | GET | All component statuses |
| `/api/system/config` | GET | Current configuration |
| `/api/system/metrics` | GET | Prometheus-format metrics |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws/live` | Real-time data feed |
| `/ws/stats` | WebSocket connection stats |
| `/ws/info` | WebSocket documentation |

## WebSocket Usage

### Connect and Subscribe

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/live');

ws.onopen = () => {
    // Subscribe to channels
    ws.send(JSON.stringify({
        type: 'subscribe',
        channels: ['logs', 'alerts', 'stats']
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch (data.type) {
        case 'log':
            console.log('New log:', data.data);
            break;
        case 'alert':
            console.log('New alert:', data);
            break;
        case 'stats':
            console.log('Stats update:', data);
            break;
    }
};
```

### Available Channels

| Channel | Description |
|---------|-------------|
| `logs` | Real-time log entries |
| `alerts` | Alert notifications |
| `remediations` | RAG remediation suggestions |
| `stats` | Statistics updates (every 5s) |
| `health` | Component health changes |
| `pipeline` | Pipeline events |
| `all` | All channels |

## Configuration

Environment variables (or `.env` file):

```env
# API Settings
DEBUG=false
HOST=0.0.0.0
PORT=8001

# Component URLs
LOG_GENERATOR_URL=http://localhost:8000
RAG_SERVER_URL=http://localhost:5000
DEEPSEEK_URL=http://localhost:8080

# Kafka Settings
KAFKA_USERNAME=your_username
KAFKA_PASSWORD=your_password

# Data Retention
METRICS_HISTORY_MINUTES=60
MAX_RECENT_LOGS=1000
MAX_RECENT_ALERTS=500
```

## Architecture

```
backend/
├── __init__.py
├── main.py              # FastAPI application entry point
├── config.py            # Settings and configuration
├── models/              # Pydantic models
│   ├── analytics.py     # Analytics/metrics models
│   ├── logs.py          # Log/alert models
│   ├── system.py        # System health models
│   └── websocket.py     # WebSocket message models
├── routes/              # API route handlers
│   ├── analytics.py     # Analytics endpoints
│   ├── logs.py          # Logs/alerts endpoints
│   ├── system.py        # System health endpoints
│   └── websocket.py     # WebSocket endpoint
├── services/            # Business logic
│   ├── data_aggregator.py    # Data aggregation service
│   ├── health_checker.py     # Component health checks
│   └── websocket_manager.py  # WebSocket connection manager
├── requirements.txt
└── README.md
```

## Integration with Dashboard

The API is designed to power a React/Vue/Angular dashboard:

1. **Initial Load**: Fetch `/api/analytics/summary` for full dashboard state
2. **Real-time Updates**: Connect to `/ws/live` and subscribe to channels
3. **Charts**: Use `/api/analytics/timeseries/{metric}` for historical data
4. **Alerts**: Fetch `/api/alerts/recent` and subscribe to `alerts` channel
5. **Health**: Monitor `/api/system/health` and `health` channel

## Development

```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest

# Run with auto-reload
uvicorn backend.main:app --reload --port 8001
```
