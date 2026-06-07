"""Golden set of Q&A pairs for evaluation."""

GOLDEN_SET = [
    {
        "id": "msft_revenue_2024",
        "query": "What was Microsoft's revenue in 2024?",
        "expected_answer": "Microsoft's revenue in 2024 was $245.1 billion.",
        "company": "MSFT",
        "year": "2024",
        "category": "factual",
    },
    {
        "id": "msft_revenue_2023",
        "query": "What was Microsoft's revenue in 2023?",
        "expected_answer": "Microsoft's revenue in 2023 was $211.9 billion.",
        "company": "MSFT",
        "year": "2023",
        "category": "factual",
    },
    {
        "id": "tsla_risks",
        "query": "What are Tesla's main risk factors?",
        "expected_answer": "Tesla's main risk factors are EV competition, manufacturing scalability, and regulatory changes.",
        "company": "TSLA",
        "year": "2022",
        "category": "factual",
    },
    {
        "id": "amzn_revenue_2024",
        "query": "What was Amazon's revenue in 2024?",
        "expected_answer": "Amazon's revenue in 2024 was $574.0 billion.",
        "company": "AMZN",
        "year": "2024",
        "category": "factual",
    },
    {
        "id": "meta_revenue_2024",
        "query": "What was Meta's revenue in 2024?",
        "expected_answer": "Meta's revenue in 2024 was $164.0 billion.",
        "company": "META",
        "year": "2024",
        "category": "factual",
    },
    {
        "id": "goog_revenue_2024",
        "query": "What was Alphabet's revenue in 2024?",
        "expected_answer": "Alphabet's revenue in 2024 was $350.0 billion.",
        "company": "GOOG",
        "year": "2024",
        "category": "factual",
    },
    {
        "id": "msft_risks",
        "query": "What are Microsoft's risk factors?",
        "expected_answer": "Microsoft's risk factors include cloud competition, cybersecurity threats, and regulatory changes.",
        "company": "MSFT",
        "year": "2024",
        "category": "factual",
    },
    {
        "id": "amzn_risks",
        "query": "What are Amazon's risk factors?",
        "expected_answer": "Amazon's risk factors include competition in e-commerce, AWS market share, and labor costs.",
        "company": "AMZN",
        "year": "2024",
        "category": "factual",
    },
    {
        "id": "msft_employees",
        "query": "How many employees does Microsoft have?",
        "expected_answer": "Microsoft has 228,000 employees.",
        "company": "MSFT",
        "year": "2024",
        "category": "factual",
    },
    {
        "id": "tsla_employees",
        "query": "How many employees does Tesla have?",
        "expected_answer": "Tesla has 140,473 employees.",
        "company": "TSLA",
        "year": "2024",
        "category": "factual",
    },
]


def get_golden_set() -> list[dict]:
    """Return the golden set for evaluation."""
    return GOLDEN_SET


def get_golden_set_by_company(ticker: str) -> list[dict]:
    """Filter golden set by company ticker."""
    return [q for q in GOLDEN_SET if q["company"] == ticker.upper()]


def get_golden_set_by_category(category: str) -> list[dict]:
    """Filter golden set by category."""
    return [q for q in GOLDEN_SET if q["category"] == category]
