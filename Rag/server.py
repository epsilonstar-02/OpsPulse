"""
REST API Server for the Private RAG Pipeline.

This server exposes the RAG pipeline as HTTP endpoints for integration
with other services in the OpsPulse ecosystem.
Supports PDF runbooks and DeepSeek LLM.
"""

import json
import os
import glob
from threading import Thread
import pathway as pw
from pathway.xpacks.llm.servers import QASummaryRestServer
from pathway.stdlib.indexing import default_vector_document_index
from pathway.xpacks.llm import embedders
from pathway.xpacks.llm.embedders import LiteLLMEmbedder
from pathway.xpacks.llm.llms import LiteLLMChat
from pathway.xpacks.llm.question_answering import (
    answer_with_geometric_rag_strategy_from_index,
)
import yaml
import pandas as pd

# PDF parsing imports
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("Warning: pdfplumber not installed. PDF support disabled.")


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    text = text.strip()
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1
        
        if chunk.strip():
            chunks.append(chunk.strip())
        
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks


def load_pdfs_from_folder(folder_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    """Load and parse PDF documents from a folder."""
    if not PDF_SUPPORT:
        raise ImportError("pdfplumber is required for PDF support")
    
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {folder_path}")
    
    all_chunks = []
    
    for pdf_path in pdf_files:
        print(f"Processing: {os.path.basename(pdf_path)}")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
                
                chunks = chunk_text(full_text, chunk_size, chunk_overlap)
                for chunk in chunks:
                    all_chunks.append({"doc": chunk})
                print(f"  Extracted {len(chunks)} chunks")
        except Exception as e:
            print(f"  Error processing {pdf_path}: {e}")
    
    print(f"Total chunks created: {len(all_chunks)}")
    return all_chunks


def build_rag_server(config_path: str = "config.yaml", data_path: str = "../run book"):
    """
    Build and run the RAG server.
    
    Args:
        config_path: Path to configuration file
        data_path: Path to documents directory (PDF runbooks)
    """
    config = load_config(config_path)
    
    # Initialize Gemini embedder
    embedding_config = config.get("embedding", {})
    embedding_model = embedding_config.get("model", "gemini/text-embedding-004")
    
    api_key = embedding_config.get("api_key") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Please set GOOGLE_API_KEY or provide api_key in config")
    
    embedder = LiteLLMEmbedder(
        model=embedding_model,
        api_key=api_key,
    )
    embedding_dimension = embedding_config.get("dimension", 3072)
    print(f"Embedding dimension: {embedding_dimension}")
    
    # Initialize DeepSeek LLM
    llm_config = config.get("llm", {})
    api_base = llm_config.get("api_base", "http://localhost:8080")
    model = LiteLLMChat(
        model=llm_config.get("model", "deepseek/deepseek-r1"),
        temperature=llm_config.get("temperature", 0),
        top_p=llm_config.get("top_p", 1),
        api_base=api_base,
        api_key="not-needed",  # DeepSeek hosted endpoint
    )
    print(f"LLM: {llm_config.get('model', 'deepseek/deepseek-r1')}")
    print(f"API Base: {api_base}")
    
    # Load documents - check for PDFs first
    doc_config = config.get("documents", {})
    pdf_files = glob.glob(os.path.join(data_path, "*.pdf"))
    
    if pdf_files:
        # Load PDFs
        chunks = load_pdfs_from_folder(
            data_path,
            chunk_size=doc_config.get("chunk_size", 1000),
            chunk_overlap=doc_config.get("chunk_overlap", 200)
        )
        df = pd.DataFrame(chunks)
        documents = pw.debug.table_from_pandas(df)
    elif os.path.isfile(data_path):
        # Load from JSONL file
        class InputSchema(pw.Schema):
            doc: str
        json_field_paths = doc_config.get("json_field_paths", {"doc": "/context"})
        
        documents = pw.io.fs.read(
            data_path,
            format="json",
            schema=InputSchema,
            json_field_paths=json_field_paths,
            mode="streaming",
        )
    else:
        # Load from directory - monitor for new files
        documents = pw.io.fs.read(
            data_path,
            format="plaintext_by_file",
            mode="streaming",
        ).select(doc=pw.this.data)
    
    # Build vector index
    index = default_vector_document_index(
        documents.doc,
        documents,
        embedder=embedder,
        dimensions=embedding_dimension,
    )
    
    # Define query handler function
    retrieval_config = config.get("retrieval", {})
    
    def query_handler(query: str) -> str:
        """Handle a single query."""
        # This is handled internally by Pathway's server
        pass
    
    # Create the server
    server_config = config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8080)
    
    # Build the query answering pipeline
    queries, response_writer = pw.io.http.rest_connector(
        host=host,
        port=port,
        schema=pw.schema_builder(columns={"query": str}),
        delete_completed_queries=True,
    )
    
    # Process queries with adaptive RAG
    results = queries.select(
        query_id=queries.id,
        result=answer_with_geometric_rag_strategy_from_index(
            queries.query,
            index,
            documents.doc,
            model,
            n_starting_documents=retrieval_config.get("n_starting_documents", 3),
            factor=retrieval_config.get("factor", 2),
            max_iterations=retrieval_config.get("max_iterations", 5),
        ),
    )
    
    # Write responses back to the HTTP client
    response_writer(results)
    
    print(f"Starting RAG server on {host}:{port}")
    print("Endpoints:")
    print(f"  POST http://{host}:{port}/ - Query the RAG system")
    print("  Body: {{\"query\": \"your question here\"}}")
    
    # Run the Pathway engine
    pw.run()


def run_simple_server(config_path: str = "config.yaml", data_path: str = "../run book"):
    """
    Run a simple RAG server using Pathway's built-in capabilities.
    
    Args:
        config_path: Path to configuration file
        data_path: Path to documents directory (PDF runbooks) or file
    """
    config = load_config(config_path)
    
    # Initialize Gemini embedder
    embedding_config = config.get("embedding", {})
    embedding_model = embedding_config.get("model", "gemini/text-embedding-004")
    
    api_key = embedding_config.get("api_key") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Please set GOOGLE_API_KEY or provide api_key in config")
    
    embedder = LiteLLMEmbedder(
        model=embedding_model,
        api_key=api_key,
    )
    embedding_dimension = embedding_config.get("dimension", 768)
    
    # Initialize DeepSeek LLM
    llm_config = config.get("llm", {})
    model = LiteLLMChat(
        model=llm_config.get("model", "deepseek/deepseek-r1"),
        temperature=llm_config.get("temperature", 0),
        top_p=llm_config.get("top_p", 1),
        api_base=llm_config.get("api_base", "http://localhost:8080"),
    )
    
    # Load documents - check for PDFs first
    doc_config = config.get("documents", {})
    pdf_files = glob.glob(os.path.join(data_path, "*.pdf")) if os.path.isdir(data_path) else []
    
    if pdf_files:
        # Load PDFs
        chunks = load_pdfs_from_folder(
            data_path,
            chunk_size=doc_config.get("chunk_size", 1000),
            chunk_overlap=doc_config.get("chunk_overlap", 200)
        )
        df = pd.DataFrame(chunks)
        documents = pw.debug.table_from_pandas(df)
    elif os.path.isfile(data_path):
        class InputSchema(pw.Schema):
            doc: str
        json_field_paths = doc_config.get("json_field_paths", {"doc": "/context"})
        
        documents = pw.io.fs.read(
            data_path,
            format="json",
            schema=InputSchema,
            json_field_paths=json_field_paths,
            mode="streaming",
        )
    else:
        documents = pw.io.fs.read(
            data_path,
            format="plaintext_by_file",
            mode="streaming",
        ).select(doc=pw.this.data)
    
    # Build index
    index = default_vector_document_index(
        documents.doc,
        documents,
        embedder=embedder,
        dimensions=embedding_dimension,
    )
    
    # Server configuration
    server_config = config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8080)
    
    retrieval_config = config.get("retrieval", {})
    
    # Define schema class for REST connector
    class QuerySchema(pw.Schema):
        query: str
    
    # Create REST connector
    queries, response_writer = pw.io.http.rest_connector(
        host=host,
        port=port,
        schema=QuerySchema,
        delete_completed_queries=True,
    )
    
    # Answer queries
    results = queries.select(
        query_id=queries.id,
        result=answer_with_geometric_rag_strategy_from_index(
            queries.query,
            index,
            documents.doc,
            model,
            n_starting_documents=retrieval_config.get("n_starting_documents", 2),
            factor=retrieval_config.get("factor", 2),
            max_iterations=retrieval_config.get("max_iterations", 4),
        ),
    )
    
    response_writer(results)
    
    print(f"\n{'='*60}")
    print(f"RAG Server Starting")
    print(f"{'='*60}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Data path: {data_path}")
    print(f"PDFs loaded: {len(pdf_files) if pdf_files else 'N/A'}")
    print(f"LLM: {llm_config.get('model', 'deepseek/deepseek-r1')}")
    print(f"LLM API: {llm_config.get('api_base', 'http://localhost:8080')}")
    print(f"Embedding model: {embedding_model}")
    print(f"{'='*60}")
    print(f"\nExample usage:")
    print(f'  curl -X POST http://{host}:{port}/ \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"query": "What are the best practices for incident response?"}}\'\n')
    print(f"{'='*60}\n")
    
    pw.run()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Server for OpsPulse")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--data", default="../run book", help="Path to PDF runbooks directory or data file")
    args = parser.parse_args()
    
    run_simple_server(args.config, args.data)
