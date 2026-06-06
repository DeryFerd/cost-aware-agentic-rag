"""ChromaDB vector store for document embeddings."""

from __future__ import annotations

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import settings

# Global model instance (lazy-loaded)
_embedding_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


class VectorStore:
    """ChromaDB-backed vector store with sentence-transformers embeddings."""

    def __init__(self, collection_name: str = "sec_10k") -> None:
        self.client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using sentence-transformers (local)."""
        model = _get_model()
        embeddings = model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

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
