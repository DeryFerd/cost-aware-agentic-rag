"""Knowledge graph for financial documents using NetworkX."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)

# Try SpaCy for NER-based entity extraction
_SPACY_AVAILABLE = False
_spacy_nlp = None
try:
    import spacy
    _spacy_nlp = spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
    logger.info("SpaCy NER available for entity extraction")
except (ImportError, OSError):
    logger.info("SpaCy not available, using regex-only entity extraction")


@dataclass
class Entity:
    """A named entity extracted from text."""
    name: str
    entity_type: str  # COMPANY, PERSON, MONEY, DATE, METRIC
    properties: dict | None = None


@dataclass
class Relation:
    """A relation between two entities."""
    source: str
    target: str
    relation_type: str  # HAS_REVENUE, REPORTED_BY, etc.
    properties: dict | None = None


@dataclass
class KnowledgeTriple:
    """A subject-predicate-object triple."""
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0


class FinancialKnowledgeGraph:
    """Knowledge graph for financial documents."""

    # SpaCy NER labels we extract
    SPACY_NER_LABELS = {"PERSON", "ORG", "MONEY", "DATE", "GPE"}

    # Map SpaCy labels to our entity types
    SPACY_LABEL_MAP = {
        "PERSON": "PERSON",
        "ORG": "COMPANY",
        "MONEY": "MONEY",
        "DATE": "DATE",
        "GPE": "LOCATION",
    }

    def __init__(self, storage_path: str | Path | None = None, llm_client=None):
        self.graph = nx.DiGraph()
        self.storage_path = Path(storage_path) if storage_path else None
        self._triple_patterns = self._init_patterns()
        self._llm_client = llm_client

    def _init_patterns(self) -> list[tuple[str, str, str]]:
        """Initialize regex patterns for entity extraction."""
        return [
            (r'\$[\d,.]+\s*(?:billion|million|B|M)', "MONEY"),
            (r'(?:Q[1-4]\s+)?(?:20[12]\d)', "DATE"),
            (r'(?:revenue|net income|earnings|profit|loss)', "METRIC"),
            (r'(?:Apple|Microsoft|Google|Amazon|Tesla|NVIDIA|Meta)', "COMPANY"),
            (r'(?:CEO|CFO|CTO|Director|Officer)\s+[A-Z][a-z]+\s+[A-Z][a-z]+', "PERSON"),
        ]

    def _extract_entities_spacy(self, text: str) -> list[Entity]:
        """Extract entities using SpaCy NER.

        Args:
            text: Document text

        Returns:
            List of extracted entities
        """
        if not _SPACY_AVAILABLE or _spacy_nlp is None:
            return []

        doc = _spacy_nlp(text)
        entities = []
        for ent in doc.ents:
            if ent.label_ in self.SPACY_NER_LABELS:
                entity_type = self.SPACY_LABEL_MAP.get(ent.label_, ent.label_)
                entities.append(Entity(
                    name=ent.text.strip(),
                    entity_type=entity_type,
                ))
        return entities

    def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities from text using pattern matching.

        Combines regex patterns and SpaCy NER when available.

        Args:
            text: Document text

        Returns:
            List of extracted entities
        """
        entities = []

        # Regex-based extraction
        for pattern, entity_type in self._triple_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append(Entity(
                    name=match.group().strip(),
                    entity_type=entity_type,
                ))

        # SpaCy NER extraction
        entities.extend(self._extract_entities_spacy(text))

        # Deduplicate
        seen = set()
        unique = []
        for e in entities:
            key = (e.name.lower(), e.entity_type)
            if key not in seen:
                seen.add(key)
                unique.append(e)

        return unique

    def _extract_triples_llm(self, text: str) -> list[KnowledgeTriple]:
        """Extract triples using an LLM client.

        Args:
            text: Document text

        Returns:
            List of KnowledgeTriple from LLM
        """
        if self._llm_client is None:
            return []

        prompt = (
            "Extract entity-relationship triples from this text. "
            "Return as a JSON list of objects with keys: subject, predicate, object. "
            "Only return the JSON array, no explanation.\n\n"
            f"Text: {text[:3000]}"
        )

        try:
            response = self._llm_client.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)

            # Parse JSON response
            import json as _json
            # Try to extract JSON from the response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not json_match:
                return []

            triples_data = _json.loads(json_match.group())
            triples = []
            for item in triples_data:
                if all(k in item for k in ("subject", "predicate", "object")):
                    triples.append(KnowledgeTriple(
                        subject=item["subject"],
                        predicate=item["predicate"],
                        object=item["object"],
                        confidence=0.7,
                    ))
            return triples
        except Exception as e:
            logger.warning(f"LLM triple extraction failed: {e}")
            return []

    def extract_triples(self, text: str) -> list[KnowledgeTriple]:
        """Extract knowledge triples from financial text.

        Uses heuristic patterns and optionally an LLM.

        Args:
            text: Document text

        Returns:
            List of KnowledgeTriple
        """
        triples = []

        # Pattern: "Company reported $X revenue"
        revenue_pattern = (
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+reported\s+'
            r'\$([\d,.]+)\s*(billion|million)?\s*(?:in\s+)?(?:total\s+)?revenue'
        )
        for match in re.finditer(revenue_pattern, text):
            company, amount, unit = match.groups()
            triples.append(KnowledgeTriple(
                subject=company.strip(),
                predicate="REPORTED_REVENUE",
                object=f"${amount} {unit or ''}".strip(),
                confidence=0.9,
            ))

        # Pattern: "Company's net income was $X"
        income_pattern = (
            r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)'?s?\s+net\s+income\s+"
            r"(?:was|were)\s+\$([\d,.]+)\s*(billion|million)?"
        )
        for match in re.finditer(income_pattern, text):
            company, amount, unit = match.groups()
            triples.append(KnowledgeTriple(
                subject=company.strip(),
                predicate="NET_INCOME",
                object=f"${amount} {unit or ''}".strip(),
                confidence=0.9,
            ))

        # Pattern: "Company acquired/merged with Company2"
        acquisition_pattern = (
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+'
            r'(?:acquired|merged\s+with)\s+'
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)'
        )
        for match in re.finditer(acquisition_pattern, text):
            company1, company2 = match.groups()
            triples.append(KnowledgeTriple(
                subject=company1.strip(),
                predicate="ACQUIRED",
                object=company2.strip(),
                confidence=0.8,
            ))

        # Pattern: "Company operates in Industry"
        industry_pattern = (
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+operates?\s+in\s+the\s+'
            r'([a-zA-Z]+(?:\s+[a-zA-Z]+)*)\s+(?:industry|sector)'
        )
        for match in re.finditer(industry_pattern, text):
            company, industry = match.groups()
            triples.append(KnowledgeTriple(
                subject=company.strip(),
                predicate="OPERATES_IN",
                object=industry.strip(),
                confidence=0.85,
            ))

        # LLM-based extraction
        triples.extend(self._extract_triples_llm(text))

        return triples

    def add_triples(self, triples: list[KnowledgeTriple]):
        """Add triples to the knowledge graph.

        Args:
            triples: List of KnowledgeTriple to add
        """
        for triple in triples:
            # Add nodes if they don't exist
            if triple.subject not in self.graph:
                self.graph.add_node(triple.subject, type="entity")
            if triple.object not in self.graph:
                self.graph.add_node(triple.object, type="entity")

            # Add edge
            self.graph.add_edge(
                triple.subject,
                triple.object,
                relation=triple.predicate,
                confidence=triple.confidence,
            )

    def build_from_text(self, text: str) -> dict:
        """Extract and build knowledge graph from text.

        Args:
            text: Document text

        Returns:
            Summary of extracted knowledge
        """
        entities = self.extract_entities(text)
        triples = self.extract_triples(text)

        # Add to graph
        self.add_triples(triples)

        return {
            "entities": len(entities),
            "triples": len(triples),
            "graph_nodes": self.graph.number_of_nodes(),
            "graph_edges": self.graph.number_of_edges(),
        }

    def query_entity(self, entity: str, depth: int = 1) -> dict:
        """Query the knowledge graph for an entity and its neighbors.

        Args:
            entity: Entity name to query
            depth: How many hops to traverse

        Returns:
            Dict with entity info and connections
        """
        if entity not in self.graph:
            return {"entity": entity, "found": False}

        result = {
            "entity": entity,
            "found": True,
            "connections": [],
        }

        # Get neighbors
        for neighbor in self.graph.neighbors(entity):
            edge_data = self.graph[entity][neighbor]
            result["connections"].append({
                "target": neighbor,
                "relation": edge_data.get("relation", "RELATED_TO"),
                "confidence": edge_data.get("confidence", 1.0),
            })

        # Get incoming connections
        for predecessor in self.graph.predecessors(entity):
            edge_data = self.graph[predecessor][entity]
            result["connections"].append({
                "source": predecessor,
                "relation": edge_data.get("relation", "RELATED_TO"),
                "confidence": edge_data.get("confidence", 1.0),
                "direction": "incoming",
            })

        return result

    def get_entity_context(self, entity: str) -> str:
        """Get human-readable context about an entity.

        Args:
            entity: Entity name

        Returns:
            Text description of entity and its relationships
        """
        info = self.query_entity(entity)
        if not info["found"]:
            return f"No information found for {entity}"

        lines = [f"Entity: {entity}"]
        for conn in info["connections"]:
            target = conn.get("target") or conn.get("source")
            relation = conn.get("relation", "RELATED_TO")
            lines.append(f"  - {relation} -> {target}")

        return "\n".join(lines)

    def save(self, path: str | Path | None = None):
        """Save knowledge graph to file."""
        save_path = Path(path) if path else self.storage_path
        if not save_path:
            raise ValueError("No storage path specified")

        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = nx.node_link_data(self.graph)
        with open(save_path, "w") as f:
            json.dump(data, f, indent=2)

        nodes = self.graph.number_of_nodes()
        edges = self.graph.number_of_edges()
        logger.info(f"Knowledge graph saved to {save_path} ({nodes} nodes, {edges} edges)")

    def load(self, path: str | Path | None = None):
        """Load knowledge graph from file."""
        load_path = Path(path) if path else self.storage_path
        if not load_path or not load_path.exists():
            logger.warning(f"Knowledge graph file not found: {load_path}")
            return

        with open(load_path) as f:
            data = json.load(f)

        self.graph = nx.node_link_graph(data)
        nodes = self.graph.number_of_nodes()
        edges = self.graph.number_of_edges()
        logger.info(f"Knowledge graph loaded: {nodes} nodes, {edges} edges")

    def get_stats(self) -> dict:
        """Get knowledge graph statistics."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "connected_components": nx.number_weakly_connected_components(self.graph),
            "density": nx.density(self.graph) if self.graph.number_of_nodes() > 0 else 0,
        }
