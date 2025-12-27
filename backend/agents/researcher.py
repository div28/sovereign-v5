"""
Researcher Agent for Sovereign V5 Multi-Agent System

Wraps the existing RAGEngine to provide an agentic interface for
fetching regulatory context on demand. Can be called by the Orchestrator
at the start of analysis or by Validators when they need more context.
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional

from .base_agent import Agent, AgentPlan, AgentResult, Reflection
from .shared_memory import SharedMemory

logger = logging.getLogger(__name__)


class ResearcherAgent(Agent):
    """
    Researcher Agent that fetches regulatory context from RAG.

    Responsibilities:
        - Fetch relevant regulatory documents from Pinecone
        - Search for specific articles or enforcement cases
        - Provide additional context when validators flag low confidence
        - Log all retrievals to SharedMemory for transparency

    Tools:
        - search_pinecone: Semantic + BM25 hybrid search
        - fetch_regulatory_doc: Get specific article text
        - search_enforcement_cases: Find relevant precedents
    """

    TOOLS = [
        "search_pinecone",
        "fetch_regulatory_doc",
        "search_enforcement_cases"
    ]

    def __init__(
        self,
        scratchpad: Optional[SharedMemory] = None,
        confidence_threshold: Optional[float] = None
    ):
        """
        Initialize the Researcher Agent.

        Args:
            scratchpad: SharedMemory for inter-agent communication.
            confidence_threshold: Minimum confidence for acceptance.
        """
        super().__init__(
            name="researcher",
            tools=self.TOOLS,
            scratchpad=scratchpad,
            confidence_threshold=confidence_threshold,
            max_iterations=1  # Researcher typically doesn't need iteration
        )

        # Lazy-loaded RAG engine
        self._rag_engine = None

        logger.info("ResearcherAgent initialized")

    def _get_rag_engine(self):
        """Lazy load RAG engine."""
        if self._rag_engine is None:
            from backend.rag.rag_engine import RAGEngine
            self._rag_engine = RAGEngine()
        return self._rag_engine

    async def plan(self, goal: str, context: Dict[str, Any]) -> AgentPlan:
        """
        Plan the research strategy based on the goal.

        For initial context gathering, retrieves broad regulatory context.
        For targeted queries (e.g., from low-confidence validators),
        focuses on specific articles or topics.
        """
        query = context.get("query", goal)
        frameworks = context.get("frameworks", ["gdpr", "sox", "euai"])
        focus_areas = context.get("focus_areas", [])
        is_retry = context.get("is_retry", False)

        # Determine search strategy
        if is_retry:
            # Targeted search for specific gaps
            steps = [
                f"Search for specific context: {', '.join(focus_areas[:3])}",
                "Retrieve enforcement cases if available",
                "Log findings to scratchpad"
            ]
            complexity = "low"
        else:
            # Broad initial context gathering
            steps = [
                f"Retrieve regulatory context for {', '.join(frameworks)}",
                "Apply hybrid search (semantic + BM25)",
                "Log findings to scratchpad"
            ]
            complexity = "medium"

        return AgentPlan(
            agent_name=self.name,
            goal=goal,
            steps=steps,
            tools_to_use=["search_pinecone"],
            estimated_complexity=complexity,
            context_needed=focus_areas,
            metadata={
                "query": query,
                "frameworks": frameworks,
                "is_retry": is_retry,
                "focus_areas": focus_areas
            }
        )

    async def act(self, plan: AgentPlan) -> AgentResult:
        """
        Execute the research plan by querying RAG.
        """
        start_time = time.time()
        metadata = plan.metadata
        query = metadata.get("query", "")
        frameworks = metadata.get("frameworks", ["gdpr", "sox", "euai"])
        is_retry = metadata.get("is_retry", False)
        focus_areas = metadata.get("focus_areas", [])

        try:
            rag = self._get_rag_engine()

            # Determine top_k based on whether this is initial or retry
            top_k = 10 if is_retry else 15

            # If retry with focus areas, enhance the query
            if is_retry and focus_areas:
                enhanced_query = f"{query} {' '.join(focus_areas)}"
            else:
                enhanced_query = query

            # Perform retrieval
            chunks = rag.retrieve(
                query=enhanced_query,
                frameworks=frameworks,
                top_k=top_k,
                use_routing=True
            )

            execution_time = (time.time() - start_time) * 1000

            # Log to scratchpad
            if self.scratchpad:
                self.scratchpad.append_finding(self.name, {
                    "query": query[:500],
                    "enhanced_query": enhanced_query[:500] if enhanced_query != query else None,
                    "frameworks": frameworks,
                    "chunks_retrieved": len(chunks),
                    "is_retry": is_retry,
                    "focus_areas": focus_areas,
                    "top_articles": self._extract_top_articles(chunks),
                    "execution_time_ms": execution_time
                })

            # Calculate confidence based on retrieval quality
            confidence = self._assess_retrieval_confidence(chunks, focus_areas)

            logger.info(
                f"Researcher retrieved {len(chunks)} chunks in {execution_time:.0f}ms, "
                f"confidence: {confidence:.2f}"
            )

            return AgentResult(
                agent_name=self.name,
                success=True,
                data={
                    "chunks": chunks,
                    "chunks_count": len(chunks),
                    "frameworks": frameworks,
                    "top_articles": self._extract_top_articles(chunks)
                },
                confidence=confidence,
                execution_time_ms=execution_time,
                tools_used=["search_pinecone"]
            )

        except Exception as e:
            logger.error(f"Researcher action failed: {e}")
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={"chunks": [], "chunks_count": 0},
                confidence=0.0,
                execution_time_ms=(time.time() - start_time) * 1000,
                errors=[str(e)]
            )

    async def reflect(self, result: AgentResult) -> Reflection:
        """
        Reflect on retrieval quality.

        Checks if enough relevant context was found.
        """
        chunks_count = result.data.get("chunks_count", 0)
        confidence = result.confidence

        # Simple reflection for researcher
        if chunks_count == 0:
            return Reflection(
                agent_name=self.name,
                confidence=0.0,
                needs_retry=False,  # Can't retry if no results
                reasoning="No regulatory context found. May need to adjust query.",
                gaps_identified=["No matching documents in knowledge base"]
            )

        if confidence < self.confidence_threshold:
            return Reflection(
                agent_name=self.name,
                confidence=confidence,
                needs_retry=False,  # Researcher doesn't retry itself
                reasoning=f"Retrieved {chunks_count} chunks but relevance is low",
                gaps_identified=["Retrieved context may not fully address query"]
            )

        return Reflection(
            agent_name=self.name,
            confidence=confidence,
            needs_retry=False,
            reasoning=f"Successfully retrieved {chunks_count} relevant regulatory chunks"
        )

    def _extract_top_articles(self, chunks: List[Dict[str, Any]], limit: int = 5) -> List[str]:
        """Extract unique article references from chunks."""
        articles = []
        seen = set()

        for chunk in chunks[:limit * 2]:  # Check more chunks to find unique articles
            metadata = chunk.get("metadata", {})
            article = metadata.get("article", "")
            if article and article not in seen:
                seen.add(article)
                articles.append(article)
                if len(articles) >= limit:
                    break

        return articles

    def _assess_retrieval_confidence(
        self,
        chunks: List[Dict[str, Any]],
        focus_areas: List[str]
    ) -> float:
        """
        Assess confidence in retrieval quality.

        Factors:
        - Number of chunks retrieved
        - Relevance scores (if available)
        - Coverage of focus areas
        """
        if not chunks:
            return 0.0

        # Base confidence from chunk count
        count_score = min(len(chunks) / 10, 1.0) * 0.5

        # Score from relevance (RRF or semantic scores)
        relevance_scores = []
        for chunk in chunks[:5]:
            score = chunk.get("rrf_score") or chunk.get("score") or 0.5
            relevance_scores.append(min(score, 1.0))

        relevance_score = (sum(relevance_scores) / len(relevance_scores)) * 0.3 if relevance_scores else 0.15

        # Coverage of focus areas
        if focus_areas:
            chunk_text = " ".join(c.get("text", "").lower() for c in chunks[:10])
            covered = sum(1 for area in focus_areas if area.lower() in chunk_text)
            coverage_score = (covered / len(focus_areas)) * 0.2
        else:
            coverage_score = 0.15  # Default if no focus areas specified

        total_confidence = count_score + relevance_score + coverage_score
        return min(total_confidence, 1.0)

    # =========================================================================
    # CONVENIENCE METHODS (can be called directly without full agent loop)
    # =========================================================================

    async def search(
        self,
        query: str,
        frameworks: List[str],
        top_k: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Direct search method for use by other agents.

        Args:
            query: Search query.
            frameworks: Frameworks to search.
            top_k: Number of results.

        Returns:
            List of retrieved chunks.
        """
        context = {
            "query": query,
            "frameworks": frameworks,
            "is_retry": False
        }

        result = await self.run(f"Search for: {query}", context)
        return result.data.get("chunks", [])

    async def search_for_context(
        self,
        focus_areas: List[str],
        frameworks: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Targeted search for specific context (used during reflection/retry).

        Args:
            focus_areas: Specific topics or articles to find.
            frameworks: Frameworks to search.

        Returns:
            List of retrieved chunks.
        """
        query = " ".join(focus_areas)
        context = {
            "query": query,
            "frameworks": frameworks,
            "focus_areas": focus_areas,
            "is_retry": True
        }

        result = await self.run(f"Find context for: {query}", context)
        return result.data.get("chunks", [])
