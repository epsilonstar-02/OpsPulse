"""
ChromaDB-based RAG Server for OpsPulse.

This server uses ChromaDB for persistent vector storage, avoiding
re-embedding documents on every startup.
"""

import os
import glob
import json
import hashlib
from typing import Optional
import yaml

# ChromaDB for persistent vector storage
import chromadb
from chromadb.config import Settings

# PDF parsing
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("Warning: pdfplumber not installed. PDF support disabled.")

# LiteLLM for embeddings and LLM
import litellm
from flask import Flask, request, jsonify


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
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


def get_file_hash(file_path: str) -> str:
    """Get MD5 hash of a file to detect changes."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from a PDF file."""
    if not PDF_SUPPORT:
        raise ImportError("pdfplumber is required for PDF support")
    
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    return full_text


class ChromaRAGServer:
    """RAG Server with ChromaDB for persistent embeddings."""
    
    def __init__(self, config_path: str = "config.yaml", data_path: str = "../run book"):
        self.config = load_config(config_path)
        self.data_path = data_path
        
        # ChromaDB settings
        chroma_config = self.config.get("chroma", {})
        self.persist_dir = chroma_config.get("persist_directory", "./chroma_db")
        self.collection_name = chroma_config.get("collection_name", "opspulse_runbooks")
        
        # Initialize ChromaDB with persistence
        self.chroma_client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Embedding config
        self.embedding_config = self.config.get("embedding", {})
        self.embedding_model = self.embedding_config.get("model", "gemini/text-embedding-004")
        self.api_key = self.embedding_config.get("api_key") or os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError("Please set GOOGLE_API_KEY or provide api_key in config")
        
        # LLM config
        self.llm_config = self.config.get("llm", {})
        
        # Track processed files
        self.metadata_file = os.path.join(self.persist_dir, "file_hashes.json")
        self.file_hashes = self._load_file_hashes()
        
        print(f"ChromaDB initialized at: {self.persist_dir}")
        print(f"Collection: {self.collection_name}")
        print(f"Existing documents: {self.collection.count()}")
    
    def _load_file_hashes(self) -> dict:
        """Load file hashes from metadata file."""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        return {}
    
    def _save_file_hashes(self):
        """Save file hashes to metadata file."""
        os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)
        with open(self.metadata_file, "w") as f:
            json.dump(self.file_hashes, f, indent=2)
    
    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for a text using LiteLLM."""
        response = litellm.embedding(
            model=self.embedding_model,
            input=[text],
            api_key=self.api_key
        )
        return response.data[0]["embedding"]
    
    def _get_embeddings_batch(self, texts: list[str], batch_size: int = 20) -> list[list[float]]:
        """Get embeddings for multiple texts in batches."""
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"  Embedding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            
            response = litellm.embedding(
                model=self.embedding_model,
                input=batch,
                api_key=self.api_key
            )
            
            batch_embeddings = [item["embedding"] for item in response.data]
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def ingest_pdfs(self, force_reingest: bool = False):
        """
        Ingest PDFs from the data folder into ChromaDB.
        Only processes new or changed files unless force_reingest is True.
        """
        if not os.path.isdir(self.data_path):
            print(f"Data path not found: {self.data_path}")
            return
        
        pdf_files = glob.glob(os.path.join(self.data_path, "*.pdf"))
        print(f"Found {len(pdf_files)} PDF files in {self.data_path}")
        
        doc_config = self.config.get("documents", {})
        chunk_size = doc_config.get("chunk_size", 1000)
        chunk_overlap = doc_config.get("chunk_overlap", 200)
        
        for pdf_path in pdf_files:
            filename = os.path.basename(pdf_path)
            file_hash = get_file_hash(pdf_path)
            
            # Check if file needs processing
            if not force_reingest and filename in self.file_hashes:
                if self.file_hashes[filename] == file_hash:
                    print(f"Skipping (unchanged): {filename}")
                    continue
                else:
                    print(f"Re-processing (changed): {filename}")
                    # Delete old chunks for this file
                    self._delete_file_chunks(filename)
            else:
                print(f"Processing (new): {filename}")
            
            try:
                # Extract text
                full_text = extract_pdf_text(pdf_path)
                
                # Chunk text
                chunks = chunk_text(full_text, chunk_size, chunk_overlap)
                print(f"  Extracted {len(chunks)} chunks")
                
                if not chunks:
                    print(f"  Warning: No text extracted from {filename}")
                    continue
                
                # Generate embeddings
                embeddings = self._get_embeddings_batch(chunks)
                
                # Prepare data for ChromaDB
                ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
                metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]
                
                # Add to collection
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=chunks,
                    metadatas=metadatas
                )
                
                # Update file hash
                self.file_hashes[filename] = file_hash
                print(f"  Added {len(chunks)} chunks to ChromaDB")
                
            except Exception as e:
                print(f"  Error processing {filename}: {e}")
        
        # Save file hashes
        self._save_file_hashes()
        print(f"\nTotal documents in collection: {self.collection.count()}")
    
    def _delete_file_chunks(self, filename: str):
        """Delete all chunks for a specific file."""
        # Get all IDs for this file
        results = self.collection.get(
            where={"source": filename}
        )
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            print(f"  Deleted {len(results['ids'])} old chunks")
    
    def query(self, question: str, n_results: int = 2) -> dict:
        """
        Query the RAG system.
        
        Args:
            question: The question to answer
            n_results: Number of relevant chunks to retrieve (default: 2)
            
        Returns:
            Dictionary with answer and sources
        """
        print(f"\n📝 RAG Query received: {question[:80]}...", flush=True)
        print(f"   Collection count: {self.collection.count()}", flush=True)
        
        if self.collection.count() == 0:
            print("   ⚠️ No documents in collection!", flush=True)
            return {
                "answer": "No documents have been ingested yet. Please run ingest_pdfs() first.",
                "sources": []
            }
        
        # Get question embedding
        question_embedding = self._get_embedding(question)
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[question_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        # Build context from retrieved chunks
        context_chunks = results["documents"][0]
        sources = list(set(m["source"] for m in results["metadatas"][0]))
        
        context = "\n\n---\n\n".join(context_chunks)
        
        # Limit context size for DeepSeek R1 (4000 token context window)
        # ~4 chars per token, leave room for system prompt (~200 tokens) and response (~1500 tokens)
        # Target: ~2000 tokens for context = ~2000 chars (being conservative)
        MAX_CONTEXT_CHARS = 2000
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n\n[...]"
        
        print(f"   Context size: {len(context)} chars from {len(context_chunks)} chunks", flush=True)
        
        # Build prompt - keep system prompt short
        system_prompt = """Answer questions using the provided context. Be concise."""

        user_prompt = f"""Context:
{context}

Question: {question}

Answer:"""

        print(f"   Prompt size: {len(user_prompt)} chars (~{len(user_prompt)//4} tokens)", flush=True)

        # Query LLM
        try:
            llm_model = self.llm_config.get("model", "deepseek/deepseek-r1")
            llm_base = self.llm_config.get("api_base", "http://localhost:8080")
            
            print(f"  Querying LLM: {llm_model} at {llm_base}", flush=True)
            
            response = litellm.completion(
                model=llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                api_base=llm_base,
                temperature=self.llm_config.get("temperature", 0),
                api_key="not-needed",  # DeepSeek hosted endpoint doesn't require API key
                timeout=120,  # 2 minutes timeout
                max_tokens=1500,  # Limited for DeepSeek R1's 4000 token window
            )
            
            # DeepSeek R1 returns reasoning in 'reasoning_content' and answer in 'content'
            # If content is empty, fall back to reasoning_content
            message = response.choices[0].message
            answer = message.content or ""
            
            # Check for reasoning_content (DeepSeek R1 specific)
            reasoning = getattr(message, 'reasoning_content', None)
            if reasoning:
                print(f"  DeepSeek R1 reasoning: {len(reasoning)} chars", flush=True)
                # If no final answer, use reasoning as the response
                if not answer.strip():
                    answer = reasoning
                else:
                    # Optionally include reasoning with answer
                    # answer = f"**Reasoning:**\n{reasoning}\n\n**Answer:**\n{answer}"
                    pass  # Just use the final answer
            
            print(f"  LLM response received: {len(answer)} chars", flush=True)
        except Exception as e:
            print(f"  LLM Error: {type(e).__name__}: {e}", flush=True)
            answer = f"Error querying LLM: {e}\n\nRelevant context:\n{context[:1000]}..."
        
        return {
            "answer": answer,
            "sources": sources,
            "num_chunks_used": len(context_chunks),
            "model": self.llm_config.get("model", "deepseek/deepseek-r1"),
        }
    
    def get_stats(self) -> dict:
        """Get statistics about the vector store."""
        return {
            "total_documents": self.collection.count(),
            "persist_directory": self.persist_dir,
            "collection_name": self.collection_name,
            "files_processed": list(self.file_hashes.keys()),
            "embedding_model": self.embedding_model,
            "llm_model": self.llm_config.get("model", "deepseek/deepseek-r1")
        }


def create_flask_app(rag_server: ChromaRAGServer) -> Flask:
    """Create Flask app with RAG endpoints."""
    app = Flask(__name__)
    
    @app.route("/", methods=["POST"])
    def query():
        """Query the RAG system."""
        data = request.get_json()
        if not data or "query" not in data:
            return jsonify({"error": "Missing 'query' field"}), 400
        
        question = data["query"]
        n_results = data.get("n_results", 5)
        
        result = rag_server.query(question, n_results)
        return jsonify(result)
    
    @app.route("/ingest", methods=["POST"])
    def ingest():
        """Ingest or re-ingest PDFs."""
        data = request.get_json() or {}
        force = data.get("force", False)
        
        rag_server.ingest_pdfs(force_reingest=force)
        return jsonify({"status": "ok", "stats": rag_server.get_stats()})
    
    @app.route("/stats", methods=["GET"])
    def stats():
        """Get vector store statistics."""
        return jsonify(rag_server.get_stats())
    
    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({"status": "healthy"})
    
    return app


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ChromaDB RAG Server for OpsPulse")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--data", default="../run book", help="Path to PDF runbooks directory")
    parser.add_argument("--ingest", action="store_true", help="Ingest PDFs before starting server")
    parser.add_argument("--force-ingest", action="store_true", help="Force re-ingest all PDFs")
    parser.add_argument("--query", type=str, help="Run a single query (no server)")
    args = parser.parse_args()
    
    # Initialize RAG server
    rag_server = ChromaRAGServer(config_path=args.config, data_path=args.data)
    
    # Ingest if requested
    if args.ingest or args.force_ingest:
        rag_server.ingest_pdfs(force_reingest=args.force_ingest)
    
    # Single query mode
    if args.query:
        result = rag_server.query(args.query)
        print(f"\nQuestion: {args.query}")
        print(f"\nAnswer: {result['answer']}")
        print(f"\nSources: {result['sources']}")
        return
    
    # Start Flask server
    server_config = rag_server.config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8080)
    
    print(f"\n{'='*60}")
    print("ChromaDB RAG Server Starting")
    print(f"{'='*60}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Data path: {args.data}")
    print(f"ChromaDB: {rag_server.persist_dir}")
    print(f"Documents indexed: {rag_server.collection.count()}")
    print(f"{'='*60}")
    print("\nEndpoints:")
    print(f"  POST /        - Query the RAG system")
    print(f"  POST /ingest  - Ingest/re-ingest PDFs")
    print(f"  GET  /stats   - Get vector store stats")
    print(f"  GET  /health  - Health check")
    print(f"\nExample:")
    print(f'  curl -X POST http://{host}:{port}/ \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"query": "What is a checklist?"}}\'\n')
    print(f"{'='*60}\n")
    
    app = create_flask_app(rag_server)
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
