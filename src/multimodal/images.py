"""Image extraction from PDF documents."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    """An image extracted from a document."""
    image_bytes: bytes
    mime_type: str
    page_number: int
    caption: str | None = None
    source: str = ""


def extract_images_from_pdf(pdf_path: str | Path) -> list[ExtractedImage]:
    """Extract images from a PDF file.

    Uses Docling for PDF parsing with image extraction.
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        logger.warning(f"PDF not found: {pdf_path}")
        return []

    try:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_table_structure = True
        pipeline_options.do_image_extraction = True  # Enable image extraction

        converter = DocumentConverter(
            format_options={
                "pdf": PdfFormatOption(pipeline_options=pipeline_options),
            }
        )

        result = converter.convert(str(pdf_path))
        doc = result.document

        images = []

        # Extract images from document
        if hasattr(doc, "pictures"):
            for _i, picture in enumerate(doc.pictures):
                if hasattr(picture, "image") and picture.image:
                    images.append(ExtractedImage(
                        image_bytes=picture.image,
                        mime_type="image/png",
                        page_number=getattr(picture, "page_number", 0),
                        caption=getattr(picture, "caption", None),
                        source=str(pdf_path),
                    ))

        logger.info(f"Extracted {len(images)} images from {pdf_path.name}")
        return images

    except Exception as e:
        logger.warning(f"Failed to extract images from {pdf_path.name}: {e}")
        return []


def extract_images_from_bytes(pdf_bytes: bytes, filename: str = "document.pdf") -> list[ExtractedImage]:
    """Extract images from PDF bytes."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        return extract_images_from_pdf(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def get_image_description(image: ExtractedImage) -> str:
    """Get a description of the image for context."""
    parts = [f"Image from page {image.page_number}"]

    if image.caption:
        parts.append(f"Caption: {image.caption}")

    return " | ".join(parts)
