"""
Sovereign V5 Multi-Agent System

Implements an Anthropic-style multi-agent architecture for compliance analysis.
"""

from .base_agent import Agent, AgentPlan, AgentResult, Reflection
from .shared_memory import SharedMemory
from .orchestrator import OrchestratorAgent

__all__ = [
    "Agent",
    "AgentPlan",
    "AgentResult",
    "Reflection",
    "SharedMemory",
    "OrchestratorAgent",
]
