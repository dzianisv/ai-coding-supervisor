"""
Engineering Manager Agent - Main orchestrator using LiteLLM
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import litellm
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.table import Table

from .base_agent import BaseAgent, AgentCapability, AgentStatus, AgentMessage, TaskResult


class TaskDecomposer:
    """Handles task decomposition using LiteLLM"""
    
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self.console = Console()
        
    async def decompose_task(self, task_description: str, available_agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Decompose a complex task into subtasks for different agents"""
        
        agent_capabilities = []
        for agent in available_agents:
            agent_capabilities.append({
                "id": agent["id"],
                "name": agent["name"], 
                "capabilities": agent["capabilities"]
            })
        
        decomposition_prompt = f"""
You are an Engineering Manager AI. Break down this coding task into specific subtasks that can be assigned to different coding agents.

TASK: {task_description}

AVAILABLE AGENTS:
{json.dumps(agent_capabilities, indent=2)}

Please decompose this task into subtasks. For each subtask, specify:
1. subtask_id: unique identifier
2. title: brief description
3. description: detailed requirements
4. required_capabilities: list of capabilities needed
5. dependencies: list of subtask_ids that must complete first
6. priority: 1-5 (5 = highest)
7. estimated_complexity: 1-10 (10 = most complex)
8. deliverables: expected outputs/artifacts

Return your response as a JSON array of subtasks.
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": decomposition_prompt}],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            # Try to extract JSON from the response
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            
            subtasks = json.loads(content)
            return subtasks
            
        except Exception as e:
            self.console.print(f"[red]Error decomposing task: {e}[/red]")
            # Fallback: create a single subtask
            return [{
                "subtask_id": "task_001",
                "title": "Complete Task",
                "description": task_description,
                "required_capabilities": ["code_generation"],
                "dependencies": [],
                "priority": 3,
                "estimated_complexity": 5,
                "deliverables": ["completed code"]
            }]


class WorkReviewer:
    """Handles work review using LiteLLM"""
    
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self.console = Console()
        
    async def review_work(self, subtask: Dict[str, Any], result: TaskResult) -> Dict[str, Any]:
        """Review completed work and provide feedback"""
        
        review_prompt = f"""
You are an Engineering Manager reviewing completed work. 

ORIGINAL SUBTASK:
{json.dumps(subtask, indent=2)}

AGENT RESULT:
- Status: {result.status.value}
- Output: {json.dumps(result.output, indent=2)}
- Errors: {result.errors}
- Warnings: {result.warnings}
- Artifacts: {result.artifacts}
- Execution Time: {result.execution_time}s

Please review this work and provide:
1. quality_score: 1-10 (10 = excellent)
2. completion_status: "complete", "needs_revision", "failed"
3. feedback: detailed feedback for the agent
4. revision_requests: specific changes needed (if any)
5. approval: true/false

Return your response as JSON.
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": review_prompt}],
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            
            review_result = json.loads(content)
            return review_result
            
        except Exception as e:
            self.console.print(f"[red]Error reviewing work: {e}[/red]")
            return {
                "quality_score": 5,
                "completion_status": "needs_revision",
                "feedback": f"Review failed due to error: {e}",
                "revision_requests": ["Please verify the work manually"],
                "approval": False
            }


class EngineeringManager(BaseAgent):
    """Engineering Manager agent that orchestrates other agents"""
    
    def __init__(self, agent_id: str = "eng_manager", model: str = "gpt-4"):
        super().__init__(
            agent_id=agent_id,
            name="Engineering Manager",
            capabilities=[
                AgentCapability.TASK_MANAGEMENT,
                AgentCapability.PROJECT_PLANNING,
                AgentCapability.CODE_REVIEW
            ]
        )
        
        self.model = model
        self.console = Console()
        self.task_decomposer = TaskDecomposer(model)
        self.work_reviewer = WorkReviewer(model)
        
        # Team management
        self.available_agents: Dict[str, BaseAgent] = {}
        self.active_subtasks: Dict[str, Dict[str, Any]] = {}
        self.completed_subtasks: Dict[str, Dict[str, Any]] = {}
        self.task_assignments: Dict[str, str] = {}  # subtask_id -> agent_id
        
        # Progress tracking
        self.progress: Optional[Progress] = None
        self.progress_tasks: Dict[str, TaskID] = {}
        
    def register_agent(self, agent: BaseAgent):
        """Register a coding agent with the manager"""
        self.available_agents[agent.agent_id] = agent
        self.console.print(f"[green]Registered agent: {agent.name} ({agent.agent_id})[/green]")
        
    async def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """Execute a high-level task by decomposing and delegating"""
        start_time = time.time()
        task_description = task.get("description", "")
        
        self.console.print(f"[bold blue]🎯 Starting task: {task_description}[/bold blue]")
        
        try:
            # Step 1: Decompose task
            self.console.print("[yellow]📋 Decomposing task...[/yellow]")
            available_agent_info = [
                {
                    "id": agent.agent_id,
                    "name": agent.name,
                    "capabilities": [cap.value for cap in agent.capabilities]
                }
                for agent in self.available_agents.values()
            ]
            
            subtasks = await self.task_decomposer.decompose_task(task_description, available_agent_info)
            self.console.print(f"[green]✅ Created {len(subtasks)} subtasks[/green]")
            
            # Step 2: Assign and execute subtasks
            await self._execute_subtasks(subtasks)
            
            # Step 3: Compile final results
            execution_time = time.time() - start_time
            
            result = TaskResult(
                task_id=task.get("id", "main_task"),
                agent_id=self.agent_id,
                status=AgentStatus.COMPLETED,
                output={
                    "subtasks_completed": len(self.completed_subtasks),
                    "total_subtasks": len(subtasks),
                    "results": self.completed_subtasks
                },
                execution_time=execution_time
            )
            
            self.console.print(f"[bold green]🎉 Task completed in {execution_time:.2f}s[/bold green]")
            return result
            
        except Exception as e:
            self.console.print(f"[red]❌ Task failed: {e}[/red]")
            return TaskResult(
                task_id=task.get("id", "main_task"),
                agent_id=self.agent_id,
                status=AgentStatus.ERROR,
                errors=[str(e)],
                execution_time=time.time() - start_time
            )
    
    async def _execute_subtasks(self, subtasks: List[Dict[str, Any]]):
        """Execute subtasks with dependency management"""
        
        # Initialize progress tracking
        with Progress() as progress:
            self.progress = progress
            
            # Create progress tasks
            for subtask in subtasks:
                task_id = progress.add_task(
                    f"[cyan]{subtask['title']}[/cyan]",
                    total=100
                )
                self.progress_tasks[subtask['subtask_id']] = task_id
            
            # Execute subtasks respecting dependencies
            remaining_subtasks = subtasks.copy()
            
            while remaining_subtasks:
                # Find subtasks with satisfied dependencies
                ready_subtasks = []
                for subtask in remaining_subtasks:
                    dependencies = subtask.get('dependencies', [])
                    if all(dep in self.completed_subtasks for dep in dependencies):
                        ready_subtasks.append(subtask)
                
                if not ready_subtasks:
                    # Check for circular dependencies or other issues
                    self.console.print("[red]⚠️  No ready subtasks found - possible circular dependency[/red]")
                    break
                
                # Execute ready subtasks concurrently
                tasks = []
                for subtask in ready_subtasks:
                    task = asyncio.create_task(self._execute_single_subtask(subtask))
                    tasks.append(task)
                    remaining_subtasks.remove(subtask)
                
                # Wait for completion
                await asyncio.gather(*tasks)
    
    async def _execute_single_subtask(self, subtask: Dict[str, Any]):
        """Execute a single subtask"""
        subtask_id = subtask['subtask_id']
        
        try:
            # Find best agent for this subtask
            assigned_agent = await self._assign_agent(subtask)
            if not assigned_agent:
                raise Exception(f"No suitable agent found for subtask: {subtask['title']}")
            
            self.task_assignments[subtask_id] = assigned_agent.agent_id
            self.active_subtasks[subtask_id] = subtask
            
            # Update progress
            if self.progress and subtask_id in self.progress_tasks:
                self.progress.update(self.progress_tasks[subtask_id], completed=25)
            
            # Execute subtask
            self.console.print(f"[blue]🔄 Executing: {subtask['title']} -> {assigned_agent.name}[/blue]")
            result = await assigned_agent.execute_task(subtask)
            
            # Update progress
            if self.progress and subtask_id in self.progress_tasks:
                self.progress.update(self.progress_tasks[subtask_id], completed=75)
            
            # Review work
            review = await self.work_reviewer.review_work(subtask, result)
            
            # Handle review results
            if review.get('approval', False):
                self.completed_subtasks[subtask_id] = {
                    'subtask': subtask,
                    'result': result,
                    'review': review
                }
                self.console.print(f"[green]✅ Completed: {subtask['title']}[/green]")
                
                # Update progress to complete
                if self.progress and subtask_id in self.progress_tasks:
                    self.progress.update(self.progress_tasks[subtask_id], completed=100)
                    
            else:
                # Handle revision request
                await self._handle_revision_request(subtask, result, review, assigned_agent)
            
            # Clean up
            if subtask_id in self.active_subtasks:
                del self.active_subtasks[subtask_id]
                
        except Exception as e:
            self.console.print(f"[red]❌ Failed subtask {subtask['title']}: {e}[/red]")
            if subtask_id in self.active_subtasks:
                del self.active_subtasks[subtask_id]
    
    async def _assign_agent(self, subtask: Dict[str, Any]) -> Optional[BaseAgent]:
        """Find the best agent for a subtask"""
        required_caps = subtask.get('required_capabilities', [])
        
        # Score agents based on capability match
        best_agent = None
        best_score = 0
        
        for agent in self.available_agents.values():
            if agent.status != AgentStatus.IDLE:
                continue
                
            agent_caps = [cap.value for cap in agent.capabilities]
            score = len(set(required_caps) & set(agent_caps))
            
            if score > best_score:
                best_score = score
                best_agent = agent
        
        return best_agent
    
    async def _handle_revision_request(self, subtask: Dict[str, Any], result: TaskResult, 
                                     review: Dict[str, Any], agent: BaseAgent):
        """Handle revision requests"""
        revision_requests = review.get('revision_requests', [])
        feedback = review.get('feedback', '')
        
        self.console.print(f"[yellow]🔄 Revision needed for: {subtask['title']}[/yellow]")
        self.console.print(f"[yellow]Feedback: {feedback}[/yellow]")
        
        # Send feedback to agent
        feedback_message = AgentMessage(
            sender_id=self.agent_id,
            recipient_id=agent.agent_id,
            message_type="feedback",
            content={
                "original_subtask": subtask,
                "feedback": feedback,
                "revision_requests": revision_requests,
                "previous_result": result
            }
        )
        
        await agent.receive_message(feedback_message)
        
        # Re-execute with feedback (simplified - could be more sophisticated)
        revised_result = await agent.execute_task(subtask)
        revised_review = await self.work_reviewer.review_work(subtask, revised_result)
        
        if revised_review.get('approval', False):
            subtask_id = subtask['subtask_id']
            self.completed_subtasks[subtask_id] = {
                'subtask': subtask,
                'result': revised_result,
                'review': revised_review,
                'revision_count': 1
            }
            self.console.print(f"[green]✅ Revision approved: {subtask['title']}[/green]")
        else:
            self.console.print(f"[red]❌ Revision still not approved: {subtask['title']}[/red]")
    
    async def review_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Review work (delegated to work reviewer)"""
        # This would be called if another manager asks this manager to review work
        return {"status": "reviewed", "feedback": "Engineering Manager review"}
    
    def get_team_status(self) -> Dict[str, Any]:
        """Get status of all managed agents"""
        team_status = {}
        for agent_id, agent in self.available_agents.items():
            team_status[agent_id] = {
                "name": agent.name,
                "status": agent.status.value,
                "current_task": agent.current_task,
                "capabilities": [cap.value for cap in agent.capabilities]
            }
        
        return {
            "team_status": team_status,
            "active_subtasks": len(self.active_subtasks),
            "completed_subtasks": len(self.completed_subtasks),
            "task_assignments": self.task_assignments
        }
