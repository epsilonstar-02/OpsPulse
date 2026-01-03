"""
Private RAG Pipeline with Pathway and DeepSeek
Based on: https://pathway.com/developers/templates/rag/private-rag-ollama-mistral/

This module implements a RAG (Retrieval-Augmented Generation) pipeline
using Pathway for orchestration and DeepSeek for local LLM deployment.
Supports PDF runbooks for embedding.
"""

import os
import glob
import yaml
import pandas as pd
import pathway as pw
from pathway.stdlib.indexing import default_vector_document_index
from pathway.xpacks.llm import embedders
from pathway.xpacks.llm.embedders import LiteLLMEmbedder
from pathway.xpacks.llm.llms import LiteLLMChat
from pathway.xpacks.llm.question_answering import (
    answer_with_geometric_rag_strategy_from_index,
)

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


class RAGPipeline:
    """
    Private RAG Pipeline using Pathway with local LLM (Ollama/Mistral).
    
    This pipeline:
    1. Loads documents from a specified source
    2. Creates embeddings using a local sentence transformer model
    3. Builds a vector index for efficient retrieval
    4. Uses adaptive RAG strategy for answering questions
    """
    
    def __init__(self, config: dict = None, config_path: str = "config.yaml"):
        """
        Initialize the RAG pipeline.
        
        Args:
            config: Configuration dictionary (optional)
            config_path: Path to config YAML file (used if config not provided)
        """
        if config is None:
            config = load_config(config_path)
        
        self.config = config
        self.embedder = None
        self.model = None
        self.index = None
        self.documents = None
        
        self._initialize_embedder()
        self._initialize_llm()
    
    def _initialize_embedder(self):
        """Initialize the embedding model (Gemini)."""
        embedding_config = self.config.get("embedding", {})
        embedding_model = embedding_config.get("model", "gemini/text-embedding-004")
        
        # Get API key directly from config or environment
        api_key = embedding_config.get("api_key") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Please set GOOGLE_API_KEY or provide api_key in config")
        
        self.embedder = LiteLLMEmbedder(
            model=embedding_model,
            api_key=api_key,
        )
        self.embedding_dimension = embedding_config.get("dimension", 3072)
        print(f"Initialized Gemini embedder with model: {embedding_model}")
        print(f"Embedding dimension: {self.embedding_dimension}")
    
    def _initialize_llm(self):
        """Initialize the LLM model (DeepSeek)."""
        llm_config = self.config.get("llm", {})
        
        self.model = LiteLLMChat(
            model=llm_config.get("model", "deepseek/deepseek-r1"),
            temperature=llm_config.get("temperature", 0),
            top_p=llm_config.get("top_p", 1),
            api_base=llm_config.get("api_base", "http://localhost:8080"),
        )
        print(f"Initialized LLM: {llm_config.get('model', 'deepseek/deepseek-r1')}")
        print(f"API Base: {llm_config.get('api_base', 'http://localhost:8080')}")
    
    def load_documents_from_jsonl(self, file_path: str, mode: str = "static"):
        """
        Load documents from a JSONL file.
        
        Args:
            file_path: Path to the JSONL file
            mode: "static" for testing, "streaming" for production
        """
        class InputSchema(pw.Schema):
            doc: str
        
        doc_config = self.config.get("documents", {})
        json_field_paths = doc_config.get("json_field_paths", {"doc": "/context"})
        
        self.documents = pw.io.fs.read(
            file_path,
            format="json",
            schema=InputSchema,
            json_field_paths=json_field_paths,
            mode=mode,
        )
        print(f"Loaded documents from: {file_path}")
        return self.documents
    
    def load_documents_from_folder(self, folder_path: str, mode: str = "streaming"):
        """
        Load documents from a folder (for production use with live updates).
        
        Args:
            folder_path: Path to the folder containing documents
            mode: "static" for testing, "streaming" for production
        """
        class InputSchema(pw.Schema):
            doc: str
        
        self.documents = pw.io.fs.read(
            folder_path,
            format="plaintext",
            schema=InputSchema,
            mode=mode,
        )
        print(f"Loaded documents from folder: {folder_path}")
        return self.documents
    
    def load_pdfs_from_folder(self, folder_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Load and parse PDF documents from a folder.
        
        Args:
            folder_path: Path to folder containing PDF files
            chunk_size: Size of text chunks for embedding
            chunk_overlap: Overlap between chunks
        """
        if not PDF_SUPPORT:
            raise ImportError("pdfplumber is required for PDF support. Install with: pip install pdfplumber")
        
        # Find all PDF files
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
                    
                    # Chunk the text
                    chunks = self._chunk_text(full_text, chunk_size, chunk_overlap)
                    for chunk in chunks:
                        all_chunks.append({
                            "doc": chunk,
                            "source": os.path.basename(pdf_path)
                        })
                    print(f"  Extracted {len(chunks)} chunks")
            except Exception as e:
                print(f"  Error processing {pdf_path}: {e}")
        
        print(f"Total chunks created: {len(all_chunks)}")
        
        # Create Pathway table from chunks
        df = pd.DataFrame(all_chunks)
        self.documents = pw.debug.table_from_pandas(df)
        return self.documents
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
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
    
    def load_documents_from_table(self, docs_table: pw.Table):
        """
        Load documents from a Pathway table.
        
        Args:
            docs_table: Pathway table with documents
        """
        self.documents = docs_table
        print("Loaded documents from Pathway table")
        return self.documents
    
    def build_index(self):
        """Build the vector document index."""
        if self.documents is None:
            raise ValueError("Documents not loaded. Call load_documents_* first.")
        
        self.index = default_vector_document_index(
            self.documents.doc,
            self.documents,
            embedder=self.embedder,
            dimensions=self.embedding_dimension,
        )
        print("Built vector document index")
        return self.index
    
    def query(self, queries: pw.Table) -> pw.Table:
        """
        Answer questions using adaptive RAG strategy.
        
        Args:
            queries: Pathway table with 'query' column
            
        Returns:
            Pathway table with questions and answers
        """
        if self.index is None:
            raise ValueError("Index not built. Call build_index() first.")
        
        retrieval_config = self.config.get("retrieval", {})
        
        result = queries.select(
            question=queries.query,
            result=answer_with_geometric_rag_strategy_from_index(
                queries.query,
                self.index,
                self.documents.doc,
                self.model,
                n_starting_documents=retrieval_config.get("n_starting_documents", 2),
                factor=retrieval_config.get("factor", 2),
                max_iterations=retrieval_config.get("max_iterations", 4),
            ),
        )
        return result
    
    def run_static_test(self, questions: list[str]) -> None:
        """
        Run a static test with provided questions.
        
        Args:
            questions: List of questions to answer
        """
        df = pd.DataFrame({"query": questions})
        query_table = pw.debug.table_from_pandas(df)
        
        result = self.query(query_table)
        pw.debug.compute_and_print(result)


def create_rag_pipeline(config_path: str = "config.yaml") -> RAGPipeline:
    """
    Factory function to create a RAG pipeline.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Initialized RAGPipeline instance
    """
    return RAGPipeline(config_path=config_path)


if __name__ == "__main__":
    # Example usage for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Private RAG Pipeline")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--data", default="../run book", help="Path to data file or PDF folder")
    parser.add_argument("--pdf", action="store_true", help="Load PDFs from folder")
    parser.add_argument("--question", type=str, help="Question to ask")
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = create_rag_pipeline(args.config)
    
    # Load documents
    if os.path.exists(args.data):
        if args.pdf or args.data.endswith("run book") or os.path.isdir(args.data):
            # Check if directory contains PDFs
            pdf_files = glob.glob(os.path.join(args.data, "*.pdf"))
            if pdf_files:
                doc_config = pipeline.config.get("documents", {})
                pipeline.load_pdfs_from_folder(
                    args.data,
                    chunk_size=doc_config.get("chunk_size", 1000),
                    chunk_overlap=doc_config.get("chunk_overlap", 200)
                )
            else:
                pipeline.load_documents_from_folder(args.data, mode="static")
        else:
            pipeline.load_documents_from_jsonl(args.data, mode="static")
        
        pipeline.build_index()
        
        if args.question:
            pipeline.run_static_test([args.question])
        else:
            print("Pipeline initialized. Use --question to ask a question.")
            print("Example: python rag_pipeline.py --question 'What are the best practices for incident response?'")
    else:
        print(f"Data path not found: {args.data}")
        print("Please provide a valid data path with --data")
