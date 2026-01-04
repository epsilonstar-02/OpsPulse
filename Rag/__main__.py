"""
OpsPulse RAG Module Entry Point

Allows running the RAG server with: python -m Rag
"""

from .chroma_rag_server import main

if __name__ == "__main__":
    main()
