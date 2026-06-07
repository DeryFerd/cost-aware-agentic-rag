"""Table extraction and structured data from documents."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Table:
    """Represents a table extracted from a document."""
    headers: list[str]
    rows: list[list[str]]
    source: str = ""
    ticker: str = ""
    year: str = ""

    def to_markdown(self) -> str:
        """Convert table to markdown format."""
        if not self.headers:
            return ""

        header_line = "| " + " | ".join(self.headers) + " |"
        separator = "| " + " | ".join(["---"] * len(self.headers)) + " |"
        rows = []
        for row in self.rows:
            # Pad row to match header length
            padded = row + [""] * (len(self.headers) - len(row))
            rows.append("| " + " | ".join(padded[:len(self.headers)]) + " |")

        return "\n".join([header_line, separator] + rows)

    def to_dict(self) -> dict:
        """Convert table to dictionary (first column as key)."""
        if not self.headers or not self.rows:
            return {}
        return {row[0]: row[1] if len(row) > 1 else "" for row in self.rows}


def extract_tables_from_text(text: str, ticker: str = "", year: str = "") -> list[Table]:
    """Extract tables from text content."""
    tables = []

    # Pattern for markdown-like tables
    table_pattern = r'(\|.+\|[\r\n]+\|[\-\| :]+\|[\r\n](?:\|.+\|[\r\n]*)+)'

    for match in re.finditer(table_pattern, text):
        table_text = match.group(1)
        lines = [line.strip() for line in table_text.split('\n') if line.strip()]

        if len(lines) < 2:
            continue

        # Parse header
        headers = [cell.strip() for cell in lines[0].split('|') if cell.strip()]

        # Parse rows (skip separator)
        rows = []
        for line in lines[2:]:
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if cells:
                rows.append(cells)

        if headers and rows:
            tables.append(Table(
                headers=headers,
                rows=rows,
                ticker=ticker,
                year=year,
            ))

    # Pattern for bullet-point lists that look like tables
    list_pattern = r'(?:^|\n)((?:[-•]\s+.+\n?){2,})'
    for match in re.finditer(list_pattern, text):
        list_text = match.group(1)
        items = []
        for line in list_text.split('\n'):
            line = line.strip()
            if line.startswith(('- ', '• ')):
                items.append(line[2:].strip())

        if len(items) >= 2:
            # Convert to key-value table
            rows = []
            for item in items:
                if ':' in item:
                    key, value = item.split(':', 1)
                    rows.append([key.strip(), value.strip()])
                else:
                    rows.append([item, ""])

            if rows:
                tables.append(Table(
                    headers=["Item", "Value"],
                    rows=rows,
                    ticker=ticker,
                    year=year,
                ))

    return tables


def extract_financial_data(text: str, ticker: str = "", year: str = "") -> dict:
    """Extract structured financial data from text."""
    data = {
        "ticker": ticker,
        "year": year,
        "revenue": None,
        "employees": None,
        "risks": [],
        "metrics": {},
    }

    # Extract revenue
    rev_match = re.search(r'revenue.*?\$[\d,.]+\s*(?:billion|million|B|M)', text, re.IGNORECASE)
    if rev_match:
        data["revenue"] = rev_match.group(0)

    # Extract employees
    emp_match = re.search(r'(\d[\d,]*)\s*(?:full-time\s+)?employees', text, re.IGNORECASE)
    if emp_match:
        data["employees"] = emp_match.group(1).replace(',', '')

    # Extract risks
    risk_section = re.search(r'risk factors?(.*?)(?:item \d|\Z)', text, re.IGNORECASE | re.DOTALL)
    if risk_section:
        risks = re.findall(r'[-•]\s+(.+)', risk_section.group(1))
        data["risks"] = [r.strip() for r in risks[:5]]

    # Extract other metrics
    metric_patterns = {
        "gross_margin": r'gross margin.*?(\d+\.?\d*)%',
        "operating_income": r'operating income.*?\$([\d,.]+)\s*(?:billion|million)',
        "net_income": r'net income.*?\$([\d,.]+)\s*(?:billion|million)',
    }

    for metric_name, pattern in metric_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["metrics"][metric_name] = match.group(1)

    return data


def format_table_for_context(tables: list[Table]) -> str:
    """Format tables for LLM context."""
    if not tables:
        return ""

    parts = []
    for i, table in enumerate(tables[:3]):  # Limit to 3 tables
        parts.append(f"Table {i+1} [{table.ticker} {table.year}]:\n{table.to_markdown()}")

    return "\n\n".join(parts)
