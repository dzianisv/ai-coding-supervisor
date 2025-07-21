"""
Tests for BaseAgent class
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent, AgentCapability, AgentStatus, AgentMessage, TaskResult


class TestAgent(BaseAgent):
    """Test implementation of BaseAgent"""
    
    def __init__(self):
        super().__init__(
            agent_id="test_agent",
            name="Test Agent", 
            capabilities=[AgentCapability.CODE_GENERATION]
        )
    
    async def execute_task(self, task):
        return TaskResult(
            task_id=task.get("id", "test"),
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output={"result": "test completed"}
        )
    
    async def review_work(self, work_item):
        return {"status": "reviewed", "feedback": "looks good"}


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent initialization"""
    agent = TestAgent()
    
    assert agent.agent_id == "test_agent"
    assert agent.name == "Test Agent"
    assert AgentCapability.CODE_GENERATION in agent.capabilities
    assert agent.status == AgentStatus.IDLE


@pytest.mark.asyncio
async def test_message_handling():
    """Test message sending and receiving"""
    agent1 = TestAgent()
    agent2 = TestAgent()
    
    message = AgentMessage(
        sender_id=agent1.agent_id,
        recipient_id=agent2.agent_id,
        message_type="task",
        content={"description": "test task"}
    )
    
    await agent1.send_message(message, agent2)
    
    # Check message was received
    assert not agent2.message_queue.empty()
    
    # Process messages
    await agent2.process_messages()
    
    # Check task was set
    assert agent2.current_task is not None
    assert agent2.status == AgentStatus.WORKING


@pytest.mark.asyncio
async def test_task_execution():
    """Test task execution"""
    agent = TestAgent()
    
    task = {"id": "test_task", "description": "test description"}
    result = await agent.execute_task(task)
    
    assert result.task_id == "test_task"
    assert result.agent_id == "test_agent"
    assert result.status == AgentStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__])
