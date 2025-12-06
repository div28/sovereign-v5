"""
Pinecone Multi-Index Client for Sovereign V5

Manages connections to existing Pinecone indexes for regulatory frameworks.
Each framework has its own dedicated index for optimal retrieval performance.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from pinecone import Pinecone

logger = logging.getLogger(__name__)


@dataclass
class IndexConfig:
    """Configuration for a Pinecone index."""
    name: str
    dimension: int = 1536  # OpenAI text-embedding-3-small
    metric: str = "cosine"


class PineconeClient:
    """
    Client for managing Pinecone vector database connections.

    Connects to existing indexes for regulatory framework documents:
    - GDPR (General Data Protection Regulation)
    - SOX (Sarbanes-Oxley Act)
    - EU-AI (EU Artificial Intelligence Act)
    """

    # Existing Pinecone index names
    INDEX_REGISTRY: Dict[str, IndexConfig] = {
        "gdpr": IndexConfig(name="sovereign-gdpr-regulation"),
        "sox": IndexConfig(name="sovereign-sox-regulation"),
        "euai": IndexConfig(name="sovereign-euai-regulation"),
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Pinecone client.

        Args:
            api_key: Pinecone API key. Defaults to PINECONE_API_KEY env var.

        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "PINECONE_API_KEY not found. "
                "Set it as an environment variable or pass it directly."
            )

        self._client = Pinecone(api_key=self.api_key)
        self._index_cache: Dict[str, Any] = {}
        logger.info("Pinecone client initialized successfully")

    @property
    def available_frameworks(self) -> List[str]:
        """List of available regulatory frameworks."""
        return list(self.INDEX_REGISTRY.keys())

    def get_index(self, framework: str) -> Any:
        """
        Get a Pinecone index for the specified framework.

        Args:
            framework: Framework identifier (gdpr, sox, euai).

        Returns:
            Pinecone Index object for querying.

        Raises:
            ValueError: If the framework is not recognized.
        """
        framework_key = framework.lower().replace("-", "").replace("_", "")

        if framework_key not in self.INDEX_REGISTRY:
            raise ValueError(
                f"Unknown framework: '{framework}'. "
                f"Available frameworks: {self.available_frameworks}"
            )

        # Return cached index if available
        if framework_key in self._index_cache:
            return self._index_cache[framework_key]

        # Connect to index and cache it
        config = self.INDEX_REGISTRY[framework_key]
        index = self._client.Index(config.name)
        self._index_cache[framework_key] = index

        logger.debug(f"Connected to index: {config.name}")
        return index

    def query(
        self,
        framework: str,
        vector: List[float],
        top_k: int = 10,
        include_metadata: bool = True,
        filter: Optional[Dict[str, Any]] = None,
        namespace: str = ""
    ) -> Dict[str, Any]:
        """
        Query a framework index for similar vectors.

        Args:
            framework: Framework identifier (gdpr, sox, euai).
            vector: Query embedding vector.
            top_k: Number of results to return.
            include_metadata: Whether to include metadata in results.
            filter: Optional metadata filter.
            namespace: Optional namespace within the index.

        Returns:
            Query results with matches and scores.
        """
        index = self.get_index(framework)

        results = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=include_metadata,
            filter=filter,
            namespace=namespace
        )

        logger.debug(
            f"Query to {framework}: returned {len(results.get('matches', []))} results"
        )
        return results

    def query_multiple(
        self,
        frameworks: List[str],
        vector: List[float],
        top_k: int = 10,
        include_metadata: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Query multiple framework indexes simultaneously.

        Args:
            frameworks: List of framework identifiers.
            vector: Query embedding vector.
            top_k: Number of results per framework.
            include_metadata: Whether to include metadata.

        Returns:
            Dict mapping framework to query results.
        """
        results = {}
        for framework in frameworks:
            try:
                results[framework] = self.query(
                    framework=framework,
                    vector=vector,
                    top_k=top_k,
                    include_metadata=include_metadata
                )
            except Exception as e:
                logger.error(f"Error querying {framework}: {e}")
                results[framework] = {"error": str(e), "matches": []}

        return results

    def get_stats(self, framework: str) -> Dict[str, Any]:
        """
        Get statistics for a framework's index.

        Args:
            framework: Framework identifier.

        Returns:
            Dict containing index statistics.
        """
        index = self.get_index(framework)
        stats = index.describe_index_stats()

        config = self.INDEX_REGISTRY[framework.lower()]
        return {
            "framework": framework,
            "index_name": config.name,
            "total_vectors": stats.total_vector_count,
            "dimension": stats.dimension,
            "namespaces": dict(stats.namespaces) if stats.namespaces else {}
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all framework indexes.

        Returns:
            Dict mapping framework to index statistics.
        """
        all_stats = {}
        for framework in self.available_frameworks:
            try:
                all_stats[framework] = self.get_stats(framework)
            except Exception as e:
                logger.error(f"Error getting stats for {framework}: {e}")
                all_stats[framework] = {"error": str(e)}

        return all_stats

    def health_check(self) -> Dict[str, Any]:
        """
        Check connectivity to all framework indexes.

        Returns:
            Dict with health status for each framework.
        """
        health = {"status": "healthy", "frameworks": {}}

        for framework in self.available_frameworks:
            try:
                stats = self.get_stats(framework)
                health["frameworks"][framework] = {
                    "status": "connected",
                    "vectors": stats["total_vectors"]
                }
            except Exception as e:
                health["status"] = "degraded"
                health["frameworks"][framework] = {
                    "status": "error",
                    "error": str(e)
                }

        return health

    def close(self) -> None:
        """Clear cached connections."""
        self._index_cache.clear()
        logger.info("Pinecone client connections cleared")


# Singleton instance for convenience
_default_client: Optional[PineconeClient] = None


def get_client() -> PineconeClient:
    """
    Get or create the default Pinecone client.

    Returns:
        PineconeClient instance.
    """
    global _default_client
    if _default_client is None:
        _default_client = PineconeClient()
    return _default_client
