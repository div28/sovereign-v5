"""
RAG Engine for Sovereign V5

Complete RAG orchestrator with adaptive query routing,
hybrid search (semantic + BM25), Reciprocal Rank Fusion,
and cross-encoder reranking.
"""

import os
import re
import logging
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import math

from anthropic import Anthropic

from .retriever import RAGRetriever, get_retriever
from .embeddings import get_embeddings_client

logger = logging.getLogger(__name__)


# =============================================================================
# CROSS-ENCODER RERANKING
# =============================================================================

class CrossEncoderReranker:
    """
    Cross-encoder reranker for final result refinement.

    Uses a neural cross-encoder model to compute relevance scores
    for (query, document) pairs, providing more accurate ranking
    than bi-encoder embeddings alone.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize cross-encoder reranker.

        Args:
            model_name: HuggingFace cross-encoder model name.
        """
        self.model_name = model_name
        self._model = None
        logger.info(f"CrossEncoderReranker configured with {model_name}")

    def _lazy_load_model(self):
        """Lazy load the cross-encoder model to avoid cold start delays."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name, max_length=512)
                logger.info(f"Loaded cross-encoder model: {self.model_name}")
            except ImportError:
                logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"Failed to load cross-encoder: {e}")
                raise

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using cross-encoder.

        Args:
            query: Search query.
            documents: List of document chunks with 'text' field.
            top_k: Number of top results to return (default: all).

        Returns:
            Reranked documents with 'cross_encoder_score' added.
        """
        if not documents:
            return []

        # Lazy load model
        self._lazy_load_model()

        # Prepare (query, doc) pairs
        pairs = [[query, doc.get("text", "")] for doc in documents]

        # Compute cross-encoder scores
        try:
            scores = self._model.predict(pairs)
        except Exception as e:
            logger.error(f"Cross-encoder prediction failed: {e}")
            return documents  # Return original order on failure

        # Add scores to documents
        for doc, score in zip(documents, scores):
            doc["cross_encoder_score"] = float(score)

        # Sort by score
        reranked = sorted(documents, key=lambda x: x.get("cross_encoder_score", 0), reverse=True)

        # Apply top_k limit
        if top_k:
            reranked = reranked[:top_k]

        logger.info(f"Reranked {len(documents)} documents, returning top {len(reranked)}")
        return reranked


class QueryType(Enum):
    """Classification of query types for adaptive retrieval."""
    SPECIFIC_ARTICLE = "specific_article"      # References specific regulation article
    BROAD_FRAMEWORK = "broad_framework"        # General framework question
    CROSS_FRAMEWORK = "cross_framework"        # Spans multiple frameworks
    TECHNICAL_DEEP = "technical_deep"          # Technical implementation detail
    VAGUE_QUESTION = "vague_question"          # Unclear or general question


@dataclass
class QueryStrategy:
    """Retrieval strategy based on query type."""
    query_type: QueryType
    top_k: int
    semantic_weight: float
    bm25_weight: float
    expand_query: bool


class AdaptiveQueryRouter:
    """
    Routes queries to optimal retrieval strategies using Claude Haiku.

    Classifies queries into 5 types and determines the best
    retrieval parameters for each type.
    """

    CLASSIFICATION_PROMPT = """Classify this compliance query into exactly one category.

Query: {query}

Categories:
1. specific_article - References a specific regulation article (e.g., "GDPR Article 17", "SOX Section 404")
2. broad_framework - General question about a framework (e.g., "What does GDPR require?")
3. cross_framework - Spans multiple frameworks (e.g., "How do GDPR and SOX overlap?")
4. technical_deep - Technical implementation detail (e.g., "encryption requirements for data at rest")
5. vague_question - Unclear or very general (e.g., "Is this compliant?")

Respond with ONLY the category name, nothing else."""

    STRATEGIES: Dict[QueryType, QueryStrategy] = {
        QueryType.SPECIFIC_ARTICLE: QueryStrategy(
            query_type=QueryType.SPECIFIC_ARTICLE,
            top_k=5,
            semantic_weight=0.3,
            bm25_weight=0.7,  # Keyword matching important for articles
            expand_query=False
        ),
        QueryType.BROAD_FRAMEWORK: QueryStrategy(
            query_type=QueryType.BROAD_FRAMEWORK,
            top_k=15,
            semantic_weight=0.7,
            bm25_weight=0.3,
            expand_query=True
        ),
        QueryType.CROSS_FRAMEWORK: QueryStrategy(
            query_type=QueryType.CROSS_FRAMEWORK,
            top_k=20,
            semantic_weight=0.6,
            bm25_weight=0.4,
            expand_query=True
        ),
        QueryType.TECHNICAL_DEEP: QueryStrategy(
            query_type=QueryType.TECHNICAL_DEEP,
            top_k=10,
            semantic_weight=0.5,
            bm25_weight=0.5,
            expand_query=False
        ),
        QueryType.VAGUE_QUESTION: QueryStrategy(
            query_type=QueryType.VAGUE_QUESTION,
            top_k=20,
            semantic_weight=0.8,
            bm25_weight=0.2,
            expand_query=True
        ),
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the query router with Anthropic client."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        # Create Anthropic client with explicit proxy=None to avoid Render proxy issues
        import httpx
        http_client = httpx.Client(proxy=None)
        self._client = Anthropic(api_key=self.api_key, http_client=http_client)
        self.model = "claude-3-5-haiku-20241022"

    def classify(self, query: str) -> QueryType:
        """
        Classify a query into one of 5 types using Claude Haiku.

        Args:
            query: The user's compliance query.

        Returns:
            QueryType classification.
        """
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=50,
                messages=[{
                    "role": "user",
                    "content": self.CLASSIFICATION_PROMPT.format(query=query)
                }]
            )

            result = response.content[0].text.strip().lower()

            # Map response to QueryType
            type_map = {
                "specific_article": QueryType.SPECIFIC_ARTICLE,
                "broad_framework": QueryType.BROAD_FRAMEWORK,
                "cross_framework": QueryType.CROSS_FRAMEWORK,
                "technical_deep": QueryType.TECHNICAL_DEEP,
                "vague_question": QueryType.VAGUE_QUESTION,
            }

            query_type = type_map.get(result, QueryType.VAGUE_QUESTION)
            logger.info(f"Query classified as: {query_type.value}")
            return query_type

        except Exception as e:
            logger.error(f"Query classification failed: {e}")
            return QueryType.VAGUE_QUESTION

    def get_strategy(self, query: str) -> QueryStrategy:
        """
        Get the retrieval strategy for a query.

        Args:
            query: The user's compliance query.

        Returns:
            QueryStrategy with optimal parameters.
        """
        query_type = self.classify(query)
        return self.STRATEGIES[query_type]


class HybridSearch:
    """
    Hybrid search combining semantic and BM25 with RRF fusion.

    Uses Reciprocal Rank Fusion to combine results from
    semantic (vector) search and keyword (BM25) search.
    """

    RRF_K = 60  # RRF constant, typically 60

    def __init__(self, retriever: RAGRetriever):
        """Initialize hybrid search with a retriever."""
        self.retriever = retriever

    def bm25_score(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> List[tuple]:
        """
        Calculate BM25 scores for documents.

        Simple BM25 implementation for re-ranking retrieved documents.

        Args:
            query: Search query.
            documents: List of document chunks.

        Returns:
            List of (doc_id, score) tuples sorted by score.
        """
        # Tokenize query
        query_terms = self._tokenize(query)

        # Calculate document frequencies
        doc_freqs = defaultdict(int)
        for doc in documents:
            text = doc.get("text", "")
            terms = set(self._tokenize(text))
            for term in terms:
                doc_freqs[term] += 1

        # BM25 parameters
        k1 = 1.5
        b = 0.75
        n_docs = len(documents)
        avg_doc_len = sum(len(self._tokenize(d.get("text", ""))) for d in documents) / max(n_docs, 1)

        scores = []
        for doc in documents:
            text = doc.get("text", "")
            doc_terms = self._tokenize(text)
            doc_len = len(doc_terms)
            term_freqs = defaultdict(int)
            for term in doc_terms:
                term_freqs[term] += 1

            score = 0.0
            for term in query_terms:
                if term in term_freqs:
                    tf = term_freqs[term]
                    df = doc_freqs.get(term, 0)
                    idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
                    tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
                    score += idf * tf_norm

            scores.append((doc.get("id", ""), score))

        return sorted(scores, key=lambda x: x[1], reverse=True)

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase and split on non-alphanumeric."""
        return re.findall(r'\w+', text.lower())

    def reciprocal_rank_fusion(
        self,
        semantic_results: List[Dict[str, Any]],
        bm25_rankings: List[tuple],
        semantic_weight: float = 0.5,
        bm25_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Combine semantic and BM25 results using RRF.

        Args:
            semantic_results: Results from semantic search.
            bm25_rankings: BM25 (doc_id, score) rankings.
            semantic_weight: Weight for semantic scores.
            bm25_weight: Weight for BM25 scores.

        Returns:
            Fused results sorted by combined RRF score.
        """
        rrf_scores = defaultdict(float)
        doc_map = {doc["id"]: doc for doc in semantic_results}

        # RRF from semantic rankings
        for rank, doc in enumerate(semantic_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] += semantic_weight * (1.0 / (self.RRF_K + rank + 1))

        # RRF from BM25 rankings
        for rank, (doc_id, _) in enumerate(bm25_rankings):
            rrf_scores[doc_id] += bm25_weight * (1.0 / (self.RRF_K + rank + 1))

        # Sort by RRF score and rebuild results
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        fused_results = []
        for doc_id in sorted_ids:
            if doc_id in doc_map:
                doc = doc_map[doc_id].copy()
                doc["rrf_score"] = rrf_scores[doc_id]
                fused_results.append(doc)

        return fused_results

    def search(
        self,
        query: str,
        frameworks: List[str],
        top_k: int = 10,
        semantic_weight: float = 0.5,
        bm25_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search with RRF fusion.

        Args:
            query: Search query.
            frameworks: List of frameworks to search.
            top_k: Number of final results.
            semantic_weight: Weight for semantic search.
            bm25_weight: Weight for BM25.

        Returns:
            Top-k results after RRF fusion.
        """
        # Get more results for re-ranking
        fetch_k = top_k * 3

        # Semantic search
        semantic_results = self.retriever.retrieve(
            query_text=query,
            frameworks=frameworks,
            top_k=fetch_k
        )

        if not semantic_results:
            return []

        # BM25 re-ranking
        bm25_rankings = self.bm25_score(query, semantic_results)

        # RRF fusion
        fused = self.reciprocal_rank_fusion(
            semantic_results,
            bm25_rankings,
            semantic_weight,
            bm25_weight
        )

        return fused[:top_k]


class RAGEngine:
    """
    Main RAG orchestrator for Sovereign V5.

    Coordinates query classification, strategy selection,
    hybrid retrieval, and cross-encoder reranking for optimal
    compliance document search.
    """

    def __init__(
        self,
        retriever: Optional[RAGRetriever] = None,
        api_key: Optional[str] = None,
        use_reranker: bool = False  # Disabled to fit Render free tier memory limits
    ):
        """
        Initialize the RAG engine.

        Args:
            retriever: RAGRetriever instance.
            api_key: Anthropic API key for query classification.
            use_reranker: Whether to use cross-encoder reranking.
        """
        self.retriever = retriever or get_retriever()
        self.router = AdaptiveQueryRouter(api_key=api_key)
        self.hybrid_search = HybridSearch(self.retriever)
        self.use_reranker = use_reranker
        self.reranker = CrossEncoderReranker() if use_reranker else None
        logger.info(f"RAGEngine initialized (reranker: {use_reranker})")

    def retrieve(
        self,
        query: str,
        frameworks: List[str],
        top_k: int = 10,
        use_routing: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Main retrieval method with adaptive routing and optional reranking.

        Args:
            query: User's compliance query.
            frameworks: List of frameworks to search.
            top_k: Number of results to return.
            use_routing: Whether to use adaptive query routing.

        Returns:
            List of relevant document chunks (reranked if enabled).
        """
        if not query or not frameworks:
            return []

        if use_routing:
            # Get optimal strategy from router
            strategy = self.router.get_strategy(query)

            # Retrieve more candidates for reranking (3x top_k)
            fetch_k = (strategy.top_k if strategy.top_k < top_k else top_k) * 3 if self.use_reranker else (strategy.top_k if strategy.top_k < top_k else top_k)

            # Use strategy parameters
            results = self.hybrid_search.search(
                query=query,
                frameworks=frameworks,
                top_k=fetch_k,
                semantic_weight=strategy.semantic_weight,
                bm25_weight=strategy.bm25_weight
            )

            logger.info(
                f"Retrieved {len(results)} chunks using {strategy.query_type.value} strategy"
            )
        else:
            # Simple retrieval without routing
            fetch_k = top_k * 3 if self.use_reranker else top_k
            results = self.hybrid_search.search(
                query=query,
                frameworks=frameworks,
                top_k=fetch_k
            )

        # Apply cross-encoder reranking if enabled
        if self.use_reranker and self.reranker and results:
            results = self.reranker.rerank(
                query=query,
                documents=results,
                top_k=top_k
            )
            logger.info(f"Reranked to top {len(results)} results")

        return results[:top_k]

    def retrieve_for_evaluation(
        self,
        submission_text: str,
        frameworks: List[str],
        top_k: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context for compliance evaluation.

        Optimized for judge evaluation with broader context.

        Args:
            submission_text: Text to evaluate for compliance.
            frameworks: Frameworks to check against.
            top_k: Number of context chunks.

        Returns:
            Relevant regulatory chunks for evaluation.
        """
        # For evaluation, always use broader retrieval
        return self.hybrid_search.search(
            query=submission_text,
            frameworks=frameworks,
            top_k=top_k,
            semantic_weight=0.6,
            bm25_weight=0.4
        )


# Singleton instance
_default_engine: Optional[RAGEngine] = None


def get_engine() -> RAGEngine:
    """Get or create the default RAG engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = RAGEngine()
    return _default_engine
