# Private RAG Pipeline with Pathway, Ollama, and Mistral

This module implements a fully private RAG (Retrieval-Augmented Generation) pipeline using:
- **Pathway**: Real-time data processing and orchestration
- **Ollama**: Local LLM deployment
- **Mistral 7B**: Open-source LLM model
- **Google Gemini**: Embedding generation (text-embedding-004)

Based on: [Pathway Private RAG Tutorial](https://pathway.com/developers/templates/rag/private-rag-ollama-mistral/)

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Documents     │────▶│  Pathway Engine  │────▶│  Vector Index   │
│   (JSONL/Files) │     │  (Orchestration) │     │  (Embeddings)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                 │                        │
                                 ▼                        ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │   REST API       │◀────│  Ollama/Mistral │
                        │   Server         │     │  (Local LLM)    │
                        └──────────────────┘     └─────────────────┘
```

## Prerequisites

### 1. Install Ollama

Download and install Ollama from [ollama.com/download](https://ollama.com/download)

```bash
# For macOS
brew install ollama

# Or download from https://ollama.com/download
```

### 2. Start Ollama and Pull Mistral Model

```bash
# Start Ollama service
ollama serve

# In another terminal, pull the Mistral model
ollama run mistral
```

### 3. Verify Ollama is Running

```bash
curl -X POST http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Hello, how are you?"
}'
```

## Installation

```bash
# Navigate to Rag directory
cd Rag

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Project Structure

```
Rag/
├── config.yaml         # Configuration file
├── rag_pipeline.py     # Main RAG pipeline module
├── server.py           # REST API server
├── requirements.txt    # Python dependencies
├── README.md           # This file
└── data/               # Document storage (create this)
    └── sample.jsonl    # Sample documents
```

## Configuration

Edit `config.yaml` to customize the pipeline:

```yaml
# LLM Configuration
llm:
  model: "ollama/mistral"
  api_base: "http://localhost:11434"
  temperature: 0
  top_p: 1
  format: "json"

# Embedding Model (Gemini)
embedding:
  model: "gemini/text-embedding-004"
  dimension: 768
  api_key_env: "GOOGLE_API_KEY"

# Retrieval Settings
retrieval:
  n_starting_documents: 2
  factor: 2
  max_iterations: 4

# Server Settings
server:
  host: "0.0.0.0"
  port: 8080
```

## Usage

### 1. Prepare Your Data

Create a `data` directory and add your documents:

```bash
mkdir -p data
```

Create a JSONL file with your documents:

```json
{"context": "Your document content here..."}
{"context": "Another document content..."}
```

Or download sample data:

```bash
wget -q -nc https://public-pathway-releases.s3.eu-central-1.amazonaws.com/data/adaptive-rag-contexts.jsonl -O data/sample.jsonl
```

### 2. Run Static Test

Test the pipeline with sample questions:

```bash
python rag_pipeline.py --config config.yaml --data data/sample.jsonl --question "What is your question?"
```

### 3. Start the Server

Run the REST API server:

```bash
python server.py --config config.yaml --data data/
```

### 4. Query the Server

```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the answer to your question?"}'
```

## Python API Usage

```python
from rag_pipeline import RAGPipeline, create_rag_pipeline

# Create pipeline
pipeline = create_rag_pipeline("config.yaml")

# Load documents
pipeline.load_documents_from_jsonl("data/sample.jsonl", mode="static")

# Build index
pipeline.build_index()

# Run queries
pipeline.run_static_test([
    "What is the first question?",
    "What is the second question?"
])
```

## Integration with OpsPulse

This RAG pipeline can be integrated with the OpsPulse logs system:

1. **Log Analysis**: Index logs from the log generator and query for insights
2. **Incident Response**: Use runbooks as context for incident analysis
3. **Knowledge Base**: Build a searchable knowledge base from operational docs

### Example: Indexing Logs

```python
import pathway as pw
from rag_pipeline import RAGPipeline

# Create pipeline
pipeline = RAGPipeline(config_path="config.yaml")

# Connect to Kafka for real-time log ingestion
logs = pw.io.kafka.read(
    rdkafka_settings={"bootstrap.servers": "localhost:9092"},
    topic="opspulse-logs",
    format="json",
    schema=pw.schema_builder(columns={"doc": str}),
)

# Load logs as documents
pipeline.load_documents_from_table(logs)
pipeline.build_index()

# Now the index will update in real-time as new logs arrive
```

## Embedding Models

The default embedding model is **Google Gemini text-embedding-004**. You need to set your Google API key:

```bash
export GOOGLE_API_KEY="your-google-api-key"
```

### Alternative Gemini Embedding Models

| Model | Dimension | Notes |
|-------|-----------|-------|
| `gemini/text-embedding-004` | 768 | Default, recommended |
| `gemini/embedding-001` | 768 | Legacy model |

### Local Embedding Models (Sentence Transformers)

If you prefer fully local embeddings, you can switch to Sentence Transformers:

| Model | Dimension | Size | Quality |
|-------|-----------|------|---------|
| `avsolatorio/GIST-small-Embedding-v0` | 384 | Small | Good |
| `avsolatorio/GIST-Embedding-v0` | 768 | Medium | Better |
| `mixedbread-ai/mxbai-embed-large-v1` | 1024 | Large | Best |

Update `config.yaml` to use a local model (requires code changes to use SentenceTransformerEmbedder):

```yaml
embedding:
  model: "avsolatorio/GIST-small-Embedding-v0"
  dimension: 384
```

## Alternative LLM Models

You can use different Ollama models:

```bash
# Pull alternative models
ollama pull llama2
ollama pull codellama
ollama pull phi
```

Update `config.yaml`:

```yaml
llm:
  model: "ollama/llama2"  # or ollama/codellama, ollama/phi
```

## Troubleshooting

### Ollama Connection Error

```
Error: Connection refused at localhost:11434
```

**Solution**: Make sure Ollama is running:
```bash
ollama serve
```

### Model Not Found

```
Error: model 'mistral' not found
```

**Solution**: Pull the Mistral model:
```bash
ollama pull mistral
```

### Out of Memory

If you run out of memory with large embedding models, try using a smaller model:

```yaml
embedding:
  model: "avsolatorio/GIST-small-Embedding-v0"
  dimension: 384
```

## Key Takeaways

- **Privacy**: All data stays local - no API calls to external services
- **Real-time**: Pathway handles live document updates automatically
- **Adaptive**: Uses geometric retrieval strategy for efficient token usage
- **Scalable**: Can run on single machine or distributed setup

## References

- [Pathway Documentation](https://pathway.com/developers/)
- [Ollama Documentation](https://ollama.com/)
- [Mistral AI](https://mistral.ai/)
- [Sentence Transformers](https://sbert.net/)
- [LiteLLM](https://litellm.ai/)
