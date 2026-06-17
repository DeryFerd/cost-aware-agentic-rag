"""Multimodal activation: CLIP embeddings and visual retrieval."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VisualEmbedding:
    """Visual embedding with metadata."""
    image_path: str
    embedding: list[float]
    description: str = ""
    source_page: int = 0
    chunk_id: str = ""


class MultimodalActivator:
    """Activate multimodal capabilities: CLIP embeddings + visual retrieval."""

    def __init__(self, clip_model: str = "clip-vit-base-patch32"):
        self.clip_model = clip_model
        self._processor = None
        self._model = None
        self._text_model = None

    def _load_clip(self):
        """Lazy-load CLIP model."""
        if self._model is not None:
            return

        try:
            from transformers import CLIPModel, CLIPProcessor

            self._processor = CLIPProcessor.from_pretrained(f"openai/{self.clip_model}")
            self._model = CLIPModel.from_pretrained(f"openai/{self.clip_model}")
            self._model.eval()
            logger.info(f"Loaded CLIP model: {self.clip_model}")
        except Exception as e:
            logger.warning(f"Failed to load CLIP: {e}")
            self._model = False

    def embed_image(self, image_path: str) -> list[float] | None:
        """Generate embedding for an image.

        Args:
            image_path: Path to image file

        Returns:
            Embedding vector or None if failed
        """
        self._load_clip()

        if self._model is False:
            return None

        try:
            import torch
            from PIL import Image

            image = Image.open(image_path).convert("RGB")
            inputs = self._processor(images=image, return_tensors="pt")

            with torch.no_grad():
                outputs = self._model.get_image_features(**inputs)

            embedding = outputs[0].tolist()
            # Normalize
            norm = sum(x * x for x in embedding) ** 0.5
            return [x / norm for x in embedding] if norm > 0 else embedding
        except Exception as e:
            logger.warning(f"Image embedding failed: {e}")
            return None

    def embed_text(self, text: str) -> list[float] | None:
        """Generate CLIP embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        self._load_clip()

        if self._model is False:
            return None

        try:
            import torch

            inputs = self._processor(text=[text], return_tensors="pt", padding=True)

            with torch.no_grad():
                outputs = self._model.get_text_features(**inputs)

            embedding = outputs[0].tolist()
            norm = sum(x * x for x in embedding) ** 0.5
            return [x / norm for x in embedding] if norm > 0 else embedding
        except Exception as e:
            logger.warning(f"Text embedding failed: {e}")
            return None

    def compute_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Similarity score between -1 and 1
        """
        dot = sum(a * b for a, b in zip(embedding1, embedding2, strict=False))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (norm1 * norm2)

    def process_document_images(
        self,
        image_paths: list[str],
        descriptions: list[str] | None = None,
        source_page: int = 0,
    ) -> list[VisualEmbedding]:
        """Process multiple images from a document.

        Args:
            image_paths: List of image file paths
            descriptions: Optional descriptions for each image
            source_page: Page number

        Returns:
            List of VisualEmbedding
        """
        embeddings = []
        descriptions = descriptions or [""] * len(image_paths)

        for i, (path, desc) in enumerate(zip(image_paths, descriptions, strict=False)):
            emb = self.embed_image(path)
            if emb:
                embeddings.append(VisualEmbedding(
                    image_path=path,
                    embedding=emb,
                    description=desc,
                    source_page=source_page,
                    chunk_id=f"img_{source_page}_{i}",
                ))

        return embeddings

    def find_similar_images(
        self,
        query_text: str,
        image_embeddings: list[VisualEmbedding],
        top_k: int = 5,
    ) -> list[tuple[VisualEmbedding, float]]:
        """Find images similar to a text query.

        Args:
            query_text: Text query
            image_embeddings: List of VisualEmbedding to search
            top_k: Number of results

        Returns:
            List of (VisualEmbedding, similarity_score) tuples
        """
        text_emb = self.embed_text(query_text)
        if not text_emb:
            return []

        results = []
        for img_emb in image_embeddings:
            score = self.compute_similarity(text_emb, img_emb.embedding)
            results.append((img_emb, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class TableProcessor:
    """Process and extract tables from documents using Docling."""

    def extract_tables(self, document_path: str) -> list[dict]:
        """Extract tables from a document.

        Args:
            document_path: Path to document

        Returns:
            List of dicts with 'data' (2D list) and 'metadata'
        """
        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            result = converter.convert(document_path)
            doc = result.document

            tables = []
            for table in doc.tables:
                # Convert table to 2D list
                data = []
                if hasattr(table, "data") and table.data:
                    for row in table.data:
                        data.append([str(cell) for cell in row])

                tables.append({
                    "data": data,
                    "metadata": {
                        "num_rows": len(data),
                        "num_cols": len(data[0]) if data else 0,
                    },
                })

            return tables
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")
            return []

    def table_to_text(self, table_data: list[list[str]]) -> str:
        """Convert table data to readable text.

        Args:
            table_data: 2D list of cell values

        Returns:
            Formatted text representation
        """
        if not table_data:
            return ""

        lines = []
        # Header
        lines.append(" | ".join(table_data[0]))
        lines.append("-" * len(lines[0]))

        # Rows
        for row in table_data[1:]:
            lines.append(" | ".join(row))

        return "\n".join(lines)
