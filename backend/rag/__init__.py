"""RAG (Retrieval-Augmented Generation) module for Sovereign V5."""

from .pinecone_client import PineconeClient, get_client
from .embeddings import EmbeddingsClient, get_embeddings_client, embed_text, embed_batch

__all__ = [
    "PineconeClient",
    "get_client",
    "EmbeddingsClient",
    "get_embeddings_client",
    "embed_text",
    "embed_batch",
]
