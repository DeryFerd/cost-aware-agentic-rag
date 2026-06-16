"""Export query results to PDF and CSV formats."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from src.config import settings


class QueryExporter:
    """Export query results and analytics to various formats."""

    def __init__(self) -> None:
        self.export_dir = settings.data_dir / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_query_pdf(
        self,
        query: str,
        answer: str,
        citations: list[str],
        model_used: str,
        cost_usd: float,
        latency_ms: float,
        steps_count: int,
    ) -> Path:
        """Export a single query result to PDF."""
        pdf = FPDF()
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "FinRAG Query Report", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        # Timestamp
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(128, 128, 128)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.cell(0, 8, f"Generated: {timestamp}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        # Query
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Query:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, query)
        pdf.ln(5)

        # Answer
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Answer:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, answer)
        pdf.ln(5)

        # Metadata
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Metadata:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)

        meta_items = [
            ("Model Used", model_used),
            ("Complexity", "complex" if "27b" in model_used else "simple"),
            ("Cost", f"${cost_usd:.6f}"),
            ("Latency", f"{latency_ms:.0f}ms"),
            ("Steps", str(steps_count)),
        ]

        for label, value in meta_items:
            pdf.cell(40, 6, f"{label}:")
            pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")

        pdf.ln(5)

        # Citations
        if citations:
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Sources:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            for cite in citations[:10]:
                pdf.cell(5, 6, chr(8226))  # bullet
                pdf.cell(0, 6, f" {cite}", new_x="LMARGIN", new_y="NEXT")

        # Save
        filename = f"query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = self.export_dir / filename
        pdf.output(str(filepath))

        return filepath

    def export_queries_csv(self, queries: list[dict]) -> Path:
        """Export multiple query results to CSV."""
        filename = f"queries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "query",
                    "answer",
                    "model_used",
                    "complexity",
                    "cost_usd",
                    "latency_ms",
                    "citations",
                    "timestamp",
                ],
            )
            writer.writeheader()

            for q in queries:
                writer.writerow({
                    "query": q.get("query", ""),
                    "answer": q.get("answer", "")[:500],
                    "model_used": q.get("model_used", ""),
                    "complexity": q.get("complexity", ""),
                    "cost_usd": q.get("cost_usd", 0),
                    "latency_ms": q.get("latency_ms", 0),
                    "citations": "; ".join(q.get("citations", [])),
                    "timestamp": q.get("timestamp", ""),
                })

        return filepath

    def export_analytics_pdf(self, analytics_data: dict) -> Path:
        """Export analytics summary to PDF."""
        pdf = FPDF()
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "FinRAG Analytics Report", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        # Timestamp
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(128, 128, 128)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.cell(0, 8, f"Generated: {timestamp}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        pdf.set_text_color(0, 0, 0)

        # Model comparison
        if "models" in analytics_data:
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, "Model Performance", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)

            for model in analytics_data["models"]:
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 8, model["model"], new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 10)

                stats = [
                    f"  Queries: {model['query_count']}",
                    f"  Total Cost: ${model['total_cost']:.6f}",
                    f"  Avg Cost: ${model['avg_cost']:.6f}",
                    f"  Avg Latency: {model['avg_latency_ms']:.0f}ms",
                ]
                for stat in stats:
                    pdf.cell(0, 6, stat, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)

        # Routing efficiency
        if "routing_efficiency" in analytics_data:
            eff = analytics_data["routing_efficiency"]
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, "Routing Efficiency", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)

            stats = [
                f"Simple queries routed: {eff.get('simple_queries_routed', 0)}",
                f"Complex queries routed: {eff.get('complex_queries_routed', 0)}",
                f"Estimated savings: ${eff.get('estimated_savings_usd', 0):.4f}",
                f"Savings rate: {eff.get('savings_percentage', 0):.1f}%",
            ]
            for stat in stats:
                pdf.cell(0, 6, stat, new_x="LMARGIN", new_y="NEXT")

        # Save
        filename = f"analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = self.export_dir / filename
        pdf.output(str(filepath))

        return filepath

    def list_exports(self) -> list[dict]:
        """List all exported files."""
        exports = []
        for f in sorted(self.export_dir.glob("*"), reverse=True):
            if f.is_file():
                exports.append({
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
                })
        return exports

    def get_export_path(self, filename: str) -> Path | None:
        """Get full path to an export file."""
        filepath = self.export_dir / filename
        if filepath.exists():
            return filepath
        return None
