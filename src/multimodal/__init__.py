"""Multimodal module for table and image understanding."""

from src.multimodal.tables import (
    Table,
    extract_tables_from_text,
    extract_financial_data,
    format_table_for_context,
)

__all__ = [
    "Table",
    "extract_tables_from_text",
    "extract_financial_data",
    "format_table_for_context",
]
