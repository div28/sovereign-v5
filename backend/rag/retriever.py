"""
RAG Retriever for Sovereign V5

Combines embedding generation and vector search to retrieve
relevant regulatory document chunks for compliance analysis.
"""

import logging
from typing import Dict, List, Optional, Any

from .pinecone_client import PineconeClient, get_client
from .embeddings import EmbeddingsClient, get_embeddings_client

logger = logging.getLogger(__name__)


class RAGRetriever:
    """
    Retriever that combines embeddings and vector search.

    Generates query embeddings and retrieves relevant document
    chunks from framework-specific Pinecone indexes.
    """

    def __init__(
        self,
        pinecone_client: Optional[PineconeClient] = None,
        embeddings_client: Optional[EmbeddingsClient] = None
    ):
        """
        Initialize the retriever.

        Args:
            pinecone_client: Pinecone client instance. Uses default if not provided.
            embeddings_client: Embeddings client instance. Uses default if not provided.
        """
        self.pinecone = pinecone_client or get_client()
        self.embeddings = embeddings_client or get_embeddings_client()
        logger.info("RAGRetriever initialized")

    def retrieve(
        self,
        query_text: str,
        frameworks: List[str],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query across specified frameworks.

        Args:
            query_text: The query text to search for.
            frameworks: List of framework identifiers (e.g., ["gdpr", "sox"]).
            top_k: Number of results to return per framework.
            filter: Optional metadata filter for Pinecone query.

        Returns:
            List of chunk dictionaries containing text, metadata, and score.
            Results are sorted by score (highest first).
        """
        if not query_text or not query_text.strip():
            logger.warning("Empty query text provided")
            return []

        if not frameworks:
            logger.warning("No frameworks specified")
            return []

        # Generate query embedding
        try:
            query_vector = self.embeddings.embed_text(query_text)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise

        # Query each framework index
        all_results = []
        for framework in frameworks:
            try:
                results = self.pinecone.query(
                    framework=framework,
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True,
                    filter=filter
                )
                formatted = self._format_results(results, framework)
                all_results.extend(formatted)
            except Exception as e:
                logger.error(f"Failed to query {framework}: {e}")
                continue

        # Sort by score descending
        all_results.sort(key=lambda x: x["score"], reverse=True)

        logger.info(
            f"Retrieved {len(all_results)} chunks for query across "
            f"{len(frameworks)} frameworks"
        )
        return all_results

    def retrieve_single_framework(
        self,
        query_text: str,
        framework: str,
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks from a single framework.

        Args:
            query_text: The query text to search for.
            framework: Single framework identifier.
            top_k: Number of results to return.
            filter: Optional metadata filter.

        Returns:
            List of chunk dictionaries sorted by score.
        """
        return self.retrieve(
            query_text=query_text,
            frameworks=[framework],
            top_k=top_k,
            filter=filter
        )

    def _format_results(
        self,
        raw_results: Dict[str, Any],
        framework: str
    ) -> List[Dict[str, Any]]:
        """
        Format raw Pinecone results into standardized chunk dictionaries.

        Args:
            raw_results: Raw results from Pinecone query.
            framework: Framework the results came from.

        Returns:
            List of formatted chunk dictionaries.
        """
        formatted = []
        matches = raw_results.get("matches", [])

        for match in matches:
            metadata = match.get("metadata", {})

            chunk = {
                "id": match.get("id", ""),
                "score": float(match.get("score", 0.0)),
                "framework": framework,
                "text": metadata.get("text", metadata.get("content", "")),
                "metadata": {
                    "article": metadata.get("article", ""),
                    "section": metadata.get("section", ""),
                    "title": metadata.get("title", ""),
                    "source": metadata.get("source", ""),
                    "page": metadata.get("page", ""),
                    "chunk_index": metadata.get("chunk_index", ""),
                },
            }

            # Include any additional metadata fields
            for key, value in metadata.items():
                if key not in ["text", "content"] and key not in chunk["metadata"]:
                    chunk["metadata"][key] = value

            formatted.append(chunk)

        return formatted


# Singleton instance
_default_retriever: Optional[RAGRetriever] = None


def get_retriever() -> RAGRetriever:
    """
    Get or create the default retriever.

    Returns:
        RAGRetriever instance.
    """
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = RAGRetriever()
    return _default_retriever
