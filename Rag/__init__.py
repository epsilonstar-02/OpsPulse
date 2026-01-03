"""
OpsPulse RAG Module

Private RAG pipeline using Pathway, Ollama, and Mistral.
"""

from .rag_pipeline import RAGPipeline, create_rag_pipeline

__all__ = ["RAGPipeline", "create_rag_pipeline"]
