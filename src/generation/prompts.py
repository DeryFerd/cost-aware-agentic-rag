"""Prompt templates for the Agentic RAG system."""

SYSTEM_PROMPT = """You are a financial analyst AI specializing in SEC 10-K filings.
Answer questions about public companies using their 10-K reports.
Always include specific numbers, dates, and citations.
If information is not available, say so clearly."""

ROUTER_PROMPT = """Classify this financial query complexity:
- 'simple': factual lookup, single fact retrieval, definition
- 'complex': comparison, analysis, multi-step reasoning, implications

Query: {query}
Reply with one word only: simple or complex"""

SUMMARIZE_PROMPT = """Summarize the following passages to answer the question.
Include key financial figures, dates, and specific facts.
Be concise but thorough.

Question: {question}

Passages:
{passages}"""

COMPARE_PROMPT = """Compare the following financial metrics across companies/years.
Present the comparison in a structured table format.
Highlight key differences and trends.

Request: {request}

Data:
{data}"""

CITE_PROMPT = """Extract specific citations from the text that support the given claim.
Format each citation as:
[Source: {source}, Page: {page}] — "exact quote from text"

Claim: {claim}

Text: {text}"""

VALIDATE_PROMPT = """Validate the following answer for a financial query.
Check for:
1. Completeness - does it fully answer the question?
2. Accuracy - are the numbers and facts correct?
3. Citations - are sources properly cited?
4. Clarity - is the answer well-structured?

Query: {query}
Answer: {answer}

Respond with a JSON object:
{{"completeness": 0-10, "accuracy": 0-10, "citations": 0-10, "clarity": 0-10, "issues": ["list of issues"]}}"""
