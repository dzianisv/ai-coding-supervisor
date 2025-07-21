"""
Base Agent Class - Foundation for all agents in the multi-agent system
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
import uuid


class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


class AgentCapability(Enum):
    """Agent capabilities"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DEBUGGING = "debugging"
    DOCUMENTATION = "documentation"
    TASK_MANAGEMENT = "task_management"
    PROJECT_PLANNING = "project_planning"


@dataclass
class AgentMessage:
    """Message structure for inter-agent communication"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    recipient_id: str = ""
    message_type: str = "task"  # task, result, feedback, status
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1=low, 5=high


@dataclass
class TaskResult:
    """Result of task execution"""
    task_id: str
    agent_id: str
    status: AgentStatus
    output: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    artifacts: List[str] = field(default_factory=list)  # Files created/modified


class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(self, agent_id: str, name: str, capabilities: List[AgentCapability]):
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities
        self.status = AgentStatus.IDLE
        self.current_task: Optional[Dict[str, Any]] = None
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.results_history: List[TaskResult] = []
        self.config: Dict[str, Any] = {}
        
    @abstractmethod
    async def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """Execute a task and return results"""
        pass
    
    @abstractmethod
    async def review_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Review work from another agent"""
        pass
    
    async def send_message(self, message: AgentMessage, recipient_agent: 'BaseAgent'):
        """Send message to another agent"""
        await recipient_agent.receive_message(message)
    
    async def receive_message(self, message: AgentMessage):
        """Receive message from another agent"""
        await self.message_queue.put(message)
    
    async def process_messages(self):
        """Process incoming messages"""
        while not self.message_queue.empty():
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._handle_message(message)
            except asyncio.TimeoutError:
                break
    
    async def _handle_message(self, message: AgentMessage):
        """Handle incoming message based on type"""
        if message.message_type == "task":
            self.current_task = message.content
            self.status = AgentStatus.WORKING
        elif message.message_type == "feedback":
            await self._handle_feedback(message.content)
        elif message.message_type == "status":
            await self._handle_status_request(message)
    
    async def _handle_feedback(self, feedback: Dict[str, Any]):
        """Handle feedback from manager or other agents"""
        # Default implementation - can be overridden
        pass
    
    async def _handle_status_request(self, message: AgentMessage):
        """Handle status request"""
        status_response = AgentMessage(
            sender_id=self.agent_id,
            recipient_id=message.sender_id,
            message_type="status_response",
            content={
                "status": self.status.value,
                "current_task": self.current_task,
                "capabilities": [cap.value for cap in self.capabilities]
            }
        )
        # Would need agent registry to send back
    
    def get_capabilities(self) -> List[AgentCapability]:
        """Get agent capabilities"""
        return self.capabilities
    
    def get_status(self) -> AgentStatus:
        """Get current status"""
        return self.status
    
    def get_results_summary(self) -> Dict[str, Any]:
        """Get summary of recent results"""
        return {
            "total_tasks": len(self.results_history),
            "successful_tasks": len([r for r in self.results_history if r.status == AgentStatus.COMPLETED]),
            "failed_tasks": len([r for r in self.results_history if r.status == AgentStatus.ERROR]),
            "recent_results": self.results_history[-5:] if self.results_history else []
        }
    
    def configure(self, config: Dict[str, Any]):
        """Configure agent with settings"""
        self.config.update(config)
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.status = AgentStatus.IDLE
        self.current_task = None
        # Clear message queue
        while not self.message_queue.empty():
            try:
                await asyncio.wait_for(self.message_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                break
