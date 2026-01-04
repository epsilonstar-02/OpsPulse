# 🚀 OpsPulse AI

**Real-time Log Analysis & Automated Remediation System**

OpsPulse AI is an intelligent system that generates synthetic logs with anomaly injection, streams them through Kafka/Redpanda, processes them with Pathway for windowed anomaly detection, and uses RAG (Retrieval-Augmented Generation) with DeepSeek R1 for intelligent remediation suggestions.

## 🏗️ Architecture

```
Log Generator → Kafka/Redpanda → Pathway Consumer → RAG Pipeline → Alerts
   (FastAPI)     (raw_logs)        (anomaly detection)    (DeepSeek LLM)
                     ↓                    ↓                    ↓
                 raw_logs         processed_alerts    remediation_alerts
```

## ⚡ Quick Start

### Prerequisites
- Python 3.10-3.12
- `GOOGLE_API_KEY` environment variable (for Gemini embeddings)
- PDF runbooks in `run book/` directory

### 1. Install Dependencies
```bash
pip install -r Rag/requirements.txt
pip install -r Message_queue_kafka/requirements.txt
```

### 2. Start Full Backend Stack
```bash
# Start RAG server + Pathway consumer together
python main.py full --ingest

# In another terminal, start the producer
python Message_queue_kafka/producer.py --continuous
```

### 3. Watch the Magic! 🎉
Anomalies will be detected in real-time and remediation suggestions will be generated automatically.

## 📦 Components

| Component | Description | Port |
|-----------|-------------|------|
| **Log Generator** | FastAPI server generating synthetic logs | :8000 |
| **Kafka Producer** | Sends logs to Kafka/Redpanda | - |
| **Pathway Consumer** | Real-time anomaly detection with tumbling windows | - |
| **RAG Server** | ChromaDB + Gemini embeddings + DeepSeek LLM | :5000 |
| **DeepSeek LLM** | Reasoning model for remediation | :8080 |

## 🎮 Commands

```bash
# Check service status
python main.py status

# Start individual components
python main.py rag                        # RAG server only
python main.py consumer                   # Pathway consumer only
python main.py full                       # Full stack

# With options
python main.py rag --ingest               # Ingest PDFs on startup
python main.py full --ingest              # Full stack with ingestion
python main.py consumer --rag-url http://localhost:5000  # Consumer with RAG
```

## 📊 Kafka Topics

| Topic | Description |
|-------|-------------|
| `raw_logs` | Incoming log entries from producer |
| `processed_alerts` | Anomaly alerts (without remediation) |
| `remediation_alerts` | Alerts with RAG-generated remediation |

## 🔧 Configuration

- **Anomalies**: `logs_generator/config.yaml`
- **RAG Pipeline**: `Rag/config.yaml`
- **Kafka Settings**: Hardcoded in `pathway_consumer.py` and `producer.py`

## 📚 Documentation

- [Architecture Details](ARCHITECTURE.md)
- [Software Requirements](OpsPulseAI - SRS.md)
- [Design Document](OpsPulse - DDS.md)

## 🤝 Contributing

1. Follow the patterns in `.github/copilot-instructions.md`
2. Ensure `_labels` JSON structure is preserved in log entries
3. Use `@pw.udf` decorators for Pathway stream processing

---

Built with ❤️ for the hackathon
