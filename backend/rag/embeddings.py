"""
OpenAI Embeddings Client for Sovereign V5

Generates vector embeddings using OpenAI's text-embedding-3-small model
for semantic search and document retrieval.
"""

import os
import logging
from typing import List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
MAX_BATCH_SIZE = 2048  # OpenAI's limit per request


class EmbeddingsClient:
    """
    Client for generating text embeddings using OpenAI.

    Uses text-embedding-3-small (1536 dimensions) for optimal
    balance of performance and cost.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the embeddings client.

        Args:
            api_key: OpenAI API key. Defaults to OPENAI_API_KEY env var.

        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. "
                "Set it as an environment variable or pass it directly."
            )

        # Create OpenAI client with explicit proxy=None to avoid Render proxy issues
        import httpx
        http_client = httpx.Client(proxy=None)
        self._client = OpenAI(api_key=self.api_key, http_client=http_client)
        self.model = MODEL_NAME
        self.dimension = EMBEDDING_DIMENSION
        logger.info(f"Embeddings client initialized with model: {self.model}")

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            List of floats representing the embedding vector.

        Raises:
            ValueError: If text is empty.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        response = self._client.embeddings.create(
            model=self.model,
            input=text.strip()
        )

        embedding = response.data[0].embedding
        logger.debug(f"Generated embedding for text ({len(text)} chars)")
        return embedding

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = MAX_BATCH_SIZE
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            batch_size: Maximum texts per API call (default: 2048).

        Returns:
            List of embedding vectors in the same order as input texts.

        Raises:
            ValueError: If texts list is empty.
        """
        if not texts:
            raise ValueError("Cannot embed empty list of texts")

        # Filter and track empty texts
        cleaned_texts = []
        empty_indices = set()
        for i, text in enumerate(texts):
            if text and text.strip():
                cleaned_texts.append(text.strip())
            else:
                empty_indices.add(i)
                logger.warning(f"Skipping empty text at index {i}")

        if not cleaned_texts:
            raise ValueError("All texts are empty")

        # Process in batches
        all_embeddings = []
        for i in range(0, len(cleaned_texts), batch_size):
            batch = cleaned_texts[i:i + batch_size]

            response = self._client.embeddings.create(
                model=self.model,
                input=batch
            )

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            logger.debug(f"Processed batch {i // batch_size + 1}: {len(batch)} texts")

        # Reconstruct with zero vectors for empty texts
        if empty_indices:
            result = []
            embedding_idx = 0
            for i in range(len(texts)):
                if i in empty_indices:
                    result.append([0.0] * self.dimension)
                else:
                    result.append(all_embeddings[embedding_idx])
                    embedding_idx += 1
            return result

        return all_embeddings


# Singleton instance
_default_client: Optional[EmbeddingsClient] = None


def get_embeddings_client() -> EmbeddingsClient:
    """
    Get or create the default embeddings client.

    Returns:
        EmbeddingsClient instance.
    """
    global _default_client
    if _default_client is None:
        _default_client = EmbeddingsClient()
    return _default_client


def embed_text(text: str) -> List[float]:
    """
    Convenience function to embed a single text.

    Args:
        text: Text to embed.

    Returns:
        Embedding vector.
    """
    return get_embeddings_client().embed_text(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Convenience function to embed multiple texts.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embedding vectors.
    """
    return get_embeddings_client().embed_batch(texts)
