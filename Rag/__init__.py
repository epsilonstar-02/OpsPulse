"""
OpsPulse RAG Module

Private RAG pipeline for automated remediation using:
- ChromaDB for persistent vector storage
- Gemini text-embedding-004 for embeddings
- DeepSeek R1 for reasoning/answer generation

Components:
- ChromaRAGServer: Flask-based RAG server with ChromaDB backend
- RAGClient: Async client for querying the RAG server
- AnomalyAlert: Data class for structuring anomaly alerts
- AlertRemediationService: Service for processing alerts and retrieving remediation
"""

# Import main components
try:
    from .chroma_rag_server import ChromaRAGServer, create_flask_app
except ImportError:
    ChromaRAGServer = None
    create_flask_app = None

try:
    from .rag_integration import (
        AnomalyAlert,
        RemediationResponse,
        RAGClient,
        AlertRemediationService,
        create_rag_query_udf,
        process_kafka_alert,
    )
except ImportError:
    AnomalyAlert = None
    RemediationResponse = None
    RAGClient = None
    AlertRemediationService = None
    create_rag_query_udf = None
    process_kafka_alert = None

# Legacy imports for backwards compatibility
try:
    from .rag_pipeline import RAGPipeline, create_rag_pipeline
except ImportError:
    RAGPipeline = None
    create_rag_pipeline = None

__all__ = [
    # Main RAG server
    "ChromaRAGServer",
    "create_flask_app",
    # Integration components
    "AnomalyAlert",
    "RemediationResponse",
    "RAGClient",
    "AlertRemediationService",
    "create_rag_query_udf",
    "process_kafka_alert",
    # Legacy
    "RAGPipeline",
    "create_rag_pipeline",
]
