"""
Agent Registry - Manages registration and discovery of agents
"""

from typing import Dict, List, Optional, Set
from .base_agent import BaseAgent, AgentCapability, AgentStatus


class AgentRegistry:
    """Central registry for managing agents in the system"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.capability_index: Dict[AgentCapability, Set[str]] = {}
        
        # Initialize capability index
        for capability in AgentCapability:
            self.capability_index[capability] = set()
    
    def register_agent(self, agent: BaseAgent) -> bool:
        """Register an agent with the registry"""
        if agent.agent_id in self.agents:
            return False
        
        self.agents[agent.agent_id] = agent
        
        # Update capability index
        for capability in agent.capabilities:
            self.capability_index[capability].add(agent.agent_id)
        
        return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent"""
        if agent_id not in self.agents:
            return False
        
        agent = self.agents[agent_id]
        
        # Remove from capability index
        for capability in agent.capabilities:
            self.capability_index[capability].discard(agent_id)
        
        del self.agents[agent_id]
        return True
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def get_agents_by_capability(self, capability: AgentCapability) -> List[BaseAgent]:
        """Get all agents with a specific capability"""
        agent_ids = self.capability_index.get(capability, set())
        return [self.agents[agent_id] for agent_id in agent_ids if agent_id in self.agents]
    
    def get_available_agents(self, capabilities: List[AgentCapability] = None) -> List[BaseAgent]:
        """Get available (idle) agents, optionally filtered by capabilities"""
        available = []
        
        for agent in self.agents.values():
            if agent.status != AgentStatus.IDLE:
                continue
            
            if capabilities:
                # Check if agent has any of the required capabilities
                if not any(cap in agent.capabilities for cap in capabilities):
                    continue
            
            available.append(agent)
        
        return available
    
    def get_all_agents(self) -> List[BaseAgent]:
        """Get all registered agents"""
        return list(self.agents.values())
    
    def get_registry_status(self) -> Dict[str, any]:
        """Get registry status summary"""
        status_counts = {}
        for status in AgentStatus:
            status_counts[status.value] = 0
        
        for agent in self.agents.values():
            status_counts[agent.status.value] += 1
        
        capability_counts = {}
        for capability, agent_ids in self.capability_index.items():
            capability_counts[capability.value] = len(agent_ids)
        
        return {
            "total_agents": len(self.agents),
            "status_distribution": status_counts,
            "capability_distribution": capability_counts,
            "agents": {
                agent_id: {
                    "name": agent.name,
                    "status": agent.status.value,
                    "capabilities": [cap.value for cap in agent.capabilities]
                }
                for agent_id, agent in self.agents.items()
            }
        }
    
    async def broadcast_message(self, message, sender_id: str = None):
        """Broadcast message to all agents except sender"""
        for agent_id, agent in self.agents.items():
            if sender_id and agent_id == sender_id:
                continue
            await agent.receive_message(message)
    
    async def shutdown_all_agents(self):
        """Gracefully shutdown all agents"""
        for agent in self.agents.values():
            await agent.shutdown()
