"""ChromaDB vector store for document embeddings."""

from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings


class VectorStore:
    """ChromaDB-backed vector store with Ollama embeddings."""

    def __init__(self, collection_name: str = "sec_10k") -> None:
        self.client = chromadb.Client(
            ChromaSettings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(settings.chroma_path),
                anonymized_telemetry=False,
            )
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using Ollama."""
        from ollama import Client

        client = Client(
            host=settings.ollama_host,
            headers={"Authorization": f"Bearer {settings.ollama_api_key}"},
        )
        embeddings = []
        for text in texts:
            resp = client.embeddings(model=settings.embedding_model, prompt=text)
            embeddings.append(resp["embedding"])
        return embeddings

    def add_documents(self, chunks: list[dict], ticker: str) -> int:
        """Add document chunks to the vector store."""
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = self._embed(texts)

        ids = [f"{ticker}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "ticker": ticker,
                "source": c["metadata"].get("source", ""),
                "chunk_index": c["metadata"].get("chunk_index", i),
                "start_page": c["metadata"].get("start_page", 0),
                "end_page": c["metadata"].get("end_page", 0),
            }
            for i, c in enumerate(chunks)
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        return len(ids)

    def search(self, query: str, top_k: int = settings.top_k) -> list[dict]:
        """Search for similar documents."""
        query_embedding = self._embed([query])[0]

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        return [
            {
                "text": doc,
                "score": 1 - dist,  # cosine distance → similarity
                "metadata": meta,
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def count(self) -> int:
        return self.collection.count()

    def delete_all(self) -> None:
        """Clear the collection."""
        self.client.delete_collection("sec_10k")
        self.collection = self.client.get_or_create_collection(
            name="sec_10k",
            metadata={"hnsw:space": "cosine"},
        )
