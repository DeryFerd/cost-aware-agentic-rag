"""Vision capabilities for image understanding."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from dataclasses import dataclass

from src.generation.llm_client import OllamaClient
from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysis:
    """Result of image analysis."""
    description: str
    data_points: list[str]
    chart_type: str | None = None
    insights: list[str] = None

    def __post_init__(self):
        if self.insights is None:
            self.insights = []


class VisionAnalyzer:
    """Analyze images using vision-capable models."""

    def __init__(self) -> None:
        self.llm = OllamaClient()
        self.vision_model = settings.ollama_complex_model  # gemma3:27b supports vision

    def analyze_image(
        self,
        image_path: str | Path,
        question: str = "Describe this image in detail. If it contains a chart or graph, extract all data points.",
    ) -> ImageAnalysis:
        """Analyze an image using vision model."""
        image_path = Path(image_path)

        if not image_path.exists():
            return ImageAnalysis(
                description=f"Image not found: {image_path}",
                data_points=[],
            )

        # Read and encode image
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Determine image type
        suffix = image_path.suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")

        # Call vision model
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image", "image": f"data:{mime_type};base64,{image_b64}"},
                ],
            }
        ]

        resp = self.llm.chat_with_image(
            model=self.vision_model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000,
        )

        # Parse response
        return self._parse_analysis(resp.content)

    def analyze_image_bytes(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        question: str = "Describe this image. Extract any data points from charts or graphs.",
    ) -> ImageAnalysis:
        """Analyze image from bytes."""
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image", "image": f"data:{mime_type};base64,{image_b64}"},
                ],
            }
        ]

        resp = self.llm.chat_with_image(
            model=self.vision_model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000,
        )

        return self._parse_analysis(resp.content)

    def _parse_analysis(self, response: str) -> ImageAnalysis:
        """Parse vision model response into structured data."""
        # Simple parsing - extract key information
        lines = response.strip().split("\n")

        description = response[:500] if len(response) > 500 else response
        data_points = []
        insights = []
        chart_type = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for data points (numbers, percentages)
            if any(char.isdigit() for char in line) and len(line) < 200:
                data_points.append(line)

            # Look for chart type mentions
            lower = line.lower()
            if any(ct in lower for ct in ["bar chart", "line graph", "pie chart", "scatter plot", "table"]):
                chart_type = line

            # Look for insights
            if any(kw in lower for kw in ["shows", "indicates", "reveals", "trend", "increase", "decrease"]):
                insights.append(line)

        return ImageAnalysis(
            description=description,
            data_points=data_points[:10],
            chart_type=chart_type,
            insights=insights[:5],
        )

    def extract_chart_data(self, image_path: str | Path) -> dict:
        """Extract structured data from a chart image."""
        analysis = self.analyze_image(
            image_path,
            question="Extract all data from this chart. Return as JSON with keys: title, x_axis, y_axis, data_points (list of {label, value}).",
        )

        # Try to parse JSON from response
        import json
        import re

        try:
            json_match = re.search(r'\{.*\}', analysis.description, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {
            "title": "Chart",
            "description": analysis.description,
            "data_points": analysis.data_points,
        }
