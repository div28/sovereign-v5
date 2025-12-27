"""
Sovereign V5 Multi-Agent System

Implements an Anthropic-style multi-agent architecture for compliance analysis.
"""

from .base_agent import Agent, AgentPlan, AgentResult, Reflection, CONFIDENCE_THRESHOLD
from .shared_memory import SharedMemory
from .orchestrator import OrchestratorAgent
from .researcher import ResearcherAgent
from .validator import ValidatorAgent, GDPRValidatorAgent, SOXValidatorAgent, EUAIValidatorAgent

__all__ = [
    # Base classes
    "Agent",
    "AgentPlan",
    "AgentResult",
    "Reflection",
    "CONFIDENCE_THRESHOLD",
    # Memory
    "SharedMemory",
    # Agents
    "OrchestratorAgent",
    "ResearcherAgent",
    "ValidatorAgent",
    "GDPRValidatorAgent",
    "SOXValidatorAgent",
    "EUAIValidatorAgent",
]
