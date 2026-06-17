"""Streamlit dashboard for Cost-Aware Agentic RAG."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import requests
import json

st.set_page_config(
    page_title="Cost-Aware Agentic RAG",
    page_icon=" ",
    layout="wide",
)

API_BASE = "http://localhost:8000"

st.title("Cost-Aware Agentic RAG")
st.caption("SEC 10-K Financial Document Analysis with Model Routing")

# Sidebar
with st.sidebar:
    st.header("Settings")
    api_url = st.text_input("API URL", API_BASE)

    st.divider()
    st.header("System Status")
    try:
        health = requests.get(f"{api_url}/health").json()
        st.success(f"API: Connected")
        st.metric("Vector Store", health.get("vector_store_count", 0))
        st.metric("BM25 Index", health.get("bm25_count", 0))
    except Exception:
        st.error("API: Disconnected")

# Main query interface
st.header("Ask about SEC 10-K Filings")

query = st.text_area(
    "Enter your financial question:",
    placeholder="e.g., What was Microsoft's total revenue in 2024?",
    height=100,
)

col1, col2 = st.columns([1, 4])
with col1:
    run_query = st.button("Ask", type="primary", use_container_width=True)

if run_query and query:
    with st.spinner("Analyzing..."):
        try:
            response = requests.post(
                f"{api_url}/query",
                json={"query": query},
                timeout=120,
            )
            result = response.json()

            # Display answer
            st.markdown("### Answer")
            st.markdown(result.get("answer", ""))

            # Metrics row
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Model", result.get("model_used", "N/A"))
            col2.metric("Complexity", result.get("complexity", "N/A"))
            col3.metric("Cost", f"${result.get('cost_usd', 0):.6f}")
            col4.metric("Latency", f"{result.get('latency_ms', 0):.0f}ms")

            # Citations
            citations = result.get("citations", [])
            if citations:
                st.markdown("### Citations")
                for c in citations:
                    st.markdown(f"- {c}")

        except Exception as e:
            st.error(f"Error: {e}")

# Cost analytics
st.divider()
st.header("Cost Analytics")

try:
    cost_data = requests.get(f"{api_url}/cost/summary").json()
    if cost_data.get("total_queries", 0) > 0:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Queries", cost_data.get("total_queries", 0))
        col2.metric("Total Cost", f"${cost_data.get('total_cost', 0):.6f}")
        col3.metric("Avg Latency", f"{cost_data.get('avg_latency_ms', 0):.0f}ms")

        # Model breakdown
        model_costs = cost_data.get("cost_by_model", {})
        if model_costs:
            st.subheader("Cost by Model")
            for model, cost in model_costs.items():
                st.write(f"- **{model}**: ${cost:.6f}")
    else:
        st.info("No queries yet. Start asking questions to see analytics.")
except Exception:
    st.info("Run some queries to see cost analytics.")
