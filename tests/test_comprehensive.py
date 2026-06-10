"""Comprehensive test suite for Cost-Aware Agentic RAG."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Test config
class TestConfig:
    def test_settings_load(self):
        from src.config import settings
        assert settings.ollama_host is not None
        assert settings.embedding_model == "all-MiniLM-L6-v2"

    def test_directories_exist(self):
        from src.config import settings
        assert settings.raw_dir.exists()
        assert settings.indexes_dir.exists()


# Test vector store
class TestVectorStore:
    def test_vector_store_init(self):
        from src.retrieval.vector_store import VectorStore
        store = VectorStore()
        assert store.collection is not None

    def test_count(self):
        from src.retrieval.vector_store import VectorStore
        store = VectorStore()
        count = store.count()
        assert isinstance(count, int)
        assert count >= 0


# Test BM25 index
class TestBM25Index:
    def test_bm25_init(self):
        from src.retrieval.bm25_index import BM25Index
        bm25 = BM25Index()
        assert bm25 is not None

    def test_bm25_count(self):
        from src.retrieval.bm25_index import BM25Index
        bm25 = BM25Index()
        count = bm25.count()
        assert isinstance(count, int)
        assert count >= 0


# Test hybrid retriever
class TestHybridRetriever:
    def test_hybrid_init(self):
        from src.retrieval.hybrid import HybridRetriever
        retriever = HybridRetriever()
        assert retriever is not None

    def test_stats(self):
        from src.retrieval.hybrid import HybridRetriever
        retriever = HybridRetriever()
        stats = retriever.stats()
        assert "vector_count" in stats
        assert "bm25_count" in stats


# Test LLM client
class TestLLMClient:
    def test_client_init(self):
        from src.generation.llm_client import OllamaClient
        client = OllamaClient()
        assert client.client is not None

    def test_model_costs(self):
        from src.generation.llm_client import MODEL_COSTS
        assert "gemma3:4b" in MODEL_COSTS
        assert "gemma3:27b" in MODEL_COSTS

    def test_estimate_cost(self):
        from src.generation.llm_client import OllamaClient
        client = OllamaClient()
        cost = client._estimate_cost("gemma3:4b", 100, 50)
        assert isinstance(cost, float)
        assert cost >= 0


# Test orchestrator
class TestOrchestrator:
    def test_orchestrator_init(self):
        from src.agents.orchestrator import AgenticOrchestrator
        orch = AgenticOrchestrator()
        assert orch.llm is not None
        assert orch.retriever is not None

    def test_tools_dict(self):
        from src.agents.orchestrator import TOOLS
        assert "search" in TOOLS
        assert "get_financials" in TOOLS
        assert "compare_companies" in TOOLS

    def test_agent_response_dataclass(self):
        from src.agents.orchestrator import AgentResponse
        response = AgentResponse(
            answer="test",
            complexity="simple",
            model_used="gemma3:4b",
        )
        assert response.answer == "test"
        assert response.total_cost_usd == 0.0
        assert response.tools_used == []


# Test memory
class TestMemory:
    def test_memory_init(self):
        from src.agents.memory import ConversationMemory
        mem = ConversationMemory()
        assert mem.messages == []

    def test_add_message(self):
        from src.agents.memory import ConversationMemory
        mem = ConversationMemory()
        mem.add_message("user", "test query")
        assert len(mem.messages) == 1
        assert mem.messages[0]["role"] == "user"

    def test_get_context(self):
        from src.agents.memory import ConversationMemory
        mem = ConversationMemory()
        mem.add_message("user", "test")
        mem.add_message("assistant", "response")
        context = mem.get_context_string()
        assert "test" in context


# Test tables extraction
class TestTables:
    def test_extract_tables(self):
        from src.multimodal.tables import extract_tables_from_text
        text = "Revenue was $100 million in 2024."
        tables = extract_tables_from_text(text, "MSFT", "2024")
        assert isinstance(tables, list)

    def test_format_table(self):
        from src.multimodal.tables import format_table_for_context
        tables = [{"ticker": "MSFT", "year": "2024", "data": {"revenue": "$100B"}}]
        formatted = format_table_for_context(tables)
        assert isinstance(formatted, str)


# Test cost tracker
class TestCostTracker:
    def test_tracker_init(self):
        from src.generation.cost_tracker import CostTracker
        tracker = CostTracker()
        assert tracker is not None

    def test_summary(self):
        from src.generation.cost_tracker import CostTracker
        tracker = CostTracker()
        summary = tracker.summary()
        assert "total_queries" in summary
        assert "total_cost_usd" in summary


# Test API models
class TestAPIModels:
    def test_query_request(self):
        from api.models import QueryRequest
        req = QueryRequest(query="test query")
        assert req.query == "test query"

    def test_query_response(self):
        from api.models import QueryResponse
        resp = QueryResponse(
            answer="test answer",
            complexity="simple",
            model_used="gemma3:4b",
        )
        assert resp.answer == "test answer"

    def test_health_response(self):
        from api.models import HealthResponse
        resp = HealthResponse(
            status="ok",
            document_count=10,
            chunk_count=1000,
        )
        assert resp.status == "ok"


# Test ML evaluation
class TestMLEvaluation:
    def test_evaluator_init(self):
        from src.ml.evaluation import MLEvaluator
        evaluator = MLEvaluator()
        assert evaluator.results == []

    def test_relevance_score(self):
        from src.ml.evaluation import MLEvaluator
        evaluator = MLEvaluator()
        score = evaluator.evaluate_relevance("revenue growth", "The revenue growth was 15%")
        assert 0 <= score <= 1

    def test_cost_optimizer(self):
        from src.ml.evaluation import CostOptimizer
        optimizer = CostOptimizer()
        model = optimizer.select_model("What is revenue?")
        assert model in ["gemma3:4b", "gemma3:27b"]


# Test ingestion
class TestIngestion:
    def test_parser_functions(self):
        from src.ingestion.parser import _extract_metadata, _split_into_sections
        # Test metadata extraction
        path = Path("data/raw/MSFT/2024/MSFT_2024_10K.html")
        metadata = _extract_metadata(path)
        assert metadata["ticker"] == "MSFT"
        assert metadata["year"] == "2024"

    def test_split_sections(self):
        from src.ingestion.parser import _split_into_sections
        text = "Item 1. Business\nWe are a tech company.\nItem 1A. Risk Factors\nCompetition."
        sections = _split_into_sections(text)
        assert len(sections) >= 1


# Test integration (requires indices)
class TestIntegration:
    @pytest.mark.slow
    def test_retrieval_integration(self):
        from src.retrieval.hybrid import HybridRetriever
        retriever = HybridRetriever()
        retriever.load_indices()
        results = retriever.retrieve("Microsoft revenue")
        assert isinstance(results, list)

    @pytest.mark.slow
    def test_orchestrator_integration(self):
        from src.agents.orchestrator import AgenticOrchestrator
        orch = AgenticOrchestrator()
        orch.retriever.load_indices()
        response = orch.run("What is Microsoft revenue?")
        assert response.answer is not None
        assert response.model_used is not None
