"""
Claude Code Agent - Wrapper around claude-code-sdk for the multi-agent system
Reuses components from claude_engineer.py
"""

import asyncio
import sys
import os
import time
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'claude-code-sdk-python', 'src'))

try:
    from claude_code_sdk import (
        query,
        ClaudeCodeOptions,
        AssistantMessage,
        UserMessage,
        SystemMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
        CLINotFoundError,
        ProcessError,
    )
except ImportError as e:
    print(f"Warning: Could not import claude-code-sdk: {e}")
    # Create mock classes for development
    class ClaudeCodeOptions:
        def __init__(self, **kwargs):
            pass
    
    async def query(*args, **kwargs):
        return None

from .base_agent import BaseAgent, AgentCapability, AgentStatus, TaskResult


class ClaudeCodeAgent(BaseAgent):
    """Claude Code Agent that wraps claude-code-sdk functionality"""
    
    def __init__(self, 
                 agent_id: str = "claude_coder",
                 working_directory: Optional[str] = None,
                 model: Optional[str] = None,
                 allowed_tools: Optional[List[str]] = None,
                 system_prompt: Optional[str] = None,
                 permission_mode: Optional[str] = None):
        
        super().__init__(
            agent_id=agent_id,
            name="Claude Code Agent",
            capabilities=[
                AgentCapability.CODE_GENERATION,
                AgentCapability.CODE_REVIEW,
                AgentCapability.DEBUGGING,
                AgentCapability.TESTING,
                AgentCapability.DOCUMENTATION
            ]
        )
        
        # Claude-specific configuration
        self.working_directory = working_directory or os.getcwd()
        self.model = model
        self.allowed_tools = allowed_tools or []
        self.system_prompt = system_prompt
        self.permission_mode = permission_mode
        
        # Session management
        self.session_id: Optional[str] = None
        self.message_history: List[Any] = []
        
        # Performance tracking
        self.total_queries = 0
        self.total_cost = 0.0
        
    async def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """Execute a coding task using Claude"""
        start_time = time.time()
        task_id = task.get('subtask_id', task.get('id', 'unknown'))
        
        try:
            self.status = AgentStatus.WORKING
            
            # Extract task information
            title = task.get('title', 'Coding Task')
            description = task.get('description', '')
            deliverables = task.get('deliverables', [])
            
            # Construct prompt for Claude
            prompt = self._construct_task_prompt(task)
            
            # Execute with Claude
            result = await self._execute_claude_query(prompt)
            
            if result:
                # Process Claude's response
                output = await self._process_claude_response(result)
                
                # Extract artifacts (files created/modified)
                artifacts = self._extract_artifacts(result)
                
                execution_time = time.time() - start_time
                self.status = AgentStatus.COMPLETED
                
                return TaskResult(
                    task_id=task_id,
                    agent_id=self.agent_id,
                    status=AgentStatus.COMPLETED,
                    output=output,
                    execution_time=execution_time,
                    artifacts=artifacts
                )
            else:
                raise Exception("Claude query returned no result")
                
        except Exception as e:
            execution_time = time.time() - start_time
            self.status = AgentStatus.ERROR
            
            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                status=AgentStatus.ERROR,
                errors=[str(e)],
                execution_time=execution_time
            )
    
    def _construct_task_prompt(self, task: Dict[str, Any]) -> str:
        """Construct a detailed prompt for Claude based on the task"""
        
        title = task.get('title', 'Coding Task')
        description = task.get('description', '')
        deliverables = task.get('deliverables', [])
        complexity = task.get('estimated_complexity', 5)
        
        prompt = f"""
I need you to complete this coding task:

TASK: {title}

DESCRIPTION:
{description}

EXPECTED DELIVERABLES:
{chr(10).join(f"- {deliverable}" for deliverable in deliverables)}

COMPLEXITY LEVEL: {complexity}/10

Please:
1. Analyze the requirements carefully
2. Plan your approach
3. Implement the solution step by step
4. Test your implementation
5. Provide clear documentation
6. Ensure all deliverables are met

Working directory: {self.working_directory}
"""
        
        # Add context from previous feedback if available
        if hasattr(self, '_last_feedback') and self._last_feedback:
            prompt += f"\n\nPREVIOUS FEEDBACK TO ADDRESS:\n{self._last_feedback}"
        
        return prompt
    
    async def _execute_claude_query(self, prompt: str) -> Optional[Any]:
        """Execute query with Claude using the SDK"""
        try:
            # Prepare options
            options = ClaudeCodeOptions()
            
            if self.working_directory:
                options.working_directory = self.working_directory
            if self.model:
                options.model = self.model
            if self.allowed_tools:
                options.allowed_tools = self.allowed_tools
            if self.system_prompt:
                options.system_prompt = self.system_prompt
            if self.permission_mode:
                options.permission_mode = self.permission_mode
            
            # Execute query
            messages = [UserMessage(content=prompt)]
            
            result = await query(
                messages=messages,
                options=options,
                session_id=self.session_id
            )
            
            self.total_queries += 1
            
            # Store session ID for continuation
            if hasattr(result, 'session_id'):
                self.session_id = result.session_id
            
            return result
            
        except Exception as e:
            print(f"Claude query failed: {e}")
            return None
    
    async def _process_claude_response(self, result: Any) -> Dict[str, Any]:
        """Process Claude's response and extract meaningful output"""
        output = {
            "response_type": "claude_code",
            "success": True,
            "messages": [],
            "tool_uses": [],
            "files_modified": [],
            "tests_run": [],
            "summary": ""
        }
        
        try:
            if hasattr(result, 'messages'):
                for message in result.messages:
                    if isinstance(message, AssistantMessage):
                        # Extract text content
                        text_content = self._extract_text_from_message(message)
                        if text_content:
                            output["messages"].append({
                                "type": "assistant",
                                "content": text_content
                            })
                        
                        # Extract tool uses
                        for block in message.content:
                            if isinstance(block, ToolUseBlock):
                                output["tool_uses"].append({
                                    "tool": block.name,
                                    "input": block.input
                                })
                    
                    elif isinstance(message, ResultMessage):
                        # Process tool results
                        for block in message.content:
                            if isinstance(block, ToolResultBlock):
                                # Track file modifications, test results, etc.
                                self._process_tool_result(block, output)
            
            # Generate summary
            output["summary"] = self._generate_response_summary(output)
            
        except Exception as e:
            output["success"] = False
            output["error"] = str(e)
        
        return output
    
    def _extract_text_from_message(self, message: AssistantMessage) -> str:
        """Extract text content from Claude message"""
        text_parts = []
        for block in message.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
        return "\n".join(text_parts)
    
    def _process_tool_result(self, tool_result: ToolResultBlock, output: Dict[str, Any]):
        """Process tool result and update output tracking"""
        if tool_result.tool_use_id:
            # Track different types of tool results
            if "file" in str(tool_result.content).lower():
                # Likely a file operation
                output["files_modified"].append(str(tool_result.content))
            elif "test" in str(tool_result.content).lower():
                # Likely a test result
                output["tests_run"].append(str(tool_result.content))
    
    def _extract_artifacts(self, result: Any) -> List[str]:
        """Extract file artifacts from Claude's response"""
        artifacts = []
        
        try:
            if hasattr(result, 'messages'):
                for message in result.messages:
                    if isinstance(message, ResultMessage):
                        for block in message.content:
                            if isinstance(block, ToolResultBlock):
                                content_str = str(block.content)
                                # Look for file paths in tool results
                                if any(ext in content_str for ext in ['.py', '.js', '.html', '.css', '.json', '.md']):
                                    # Extract potential file paths
                                    import re
                                    file_patterns = re.findall(r'[^\s]+\.(py|js|html|css|json|md|txt|yml|yaml)', content_str)
                                    artifacts.extend(file_patterns)
        except Exception as e:
            print(f"Error extracting artifacts: {e}")
        
        return list(set(artifacts))  # Remove duplicates
    
    def _generate_response_summary(self, output: Dict[str, Any]) -> str:
        """Generate a summary of Claude's response"""
        summary_parts = []
        
        if output["messages"]:
            summary_parts.append(f"Generated {len(output['messages'])} response messages")
        
        if output["tool_uses"]:
            tools_used = set(tool["tool"] for tool in output["tool_uses"])
            summary_parts.append(f"Used tools: {', '.join(tools_used)}")
        
        if output["files_modified"]:
            summary_parts.append(f"Modified {len(output['files_modified'])} files")
        
        if output["tests_run"]:
            summary_parts.append(f"Ran {len(output['tests_run'])} tests")
        
        return "; ".join(summary_parts) if summary_parts else "Completed task execution"
    
    async def review_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Review work from another agent or provide code review"""
        
        review_prompt = f"""
Please review this work:

WORK ITEM:
{json.dumps(work_item, indent=2)}

Provide a detailed code review including:
1. Code quality assessment
2. Potential bugs or issues
3. Suggestions for improvement
4. Compliance with best practices
5. Overall rating (1-10)

Focus on technical accuracy and maintainability.
"""
        
        try:
            result = await self._execute_claude_query(review_prompt)
            if result:
                review_output = await self._process_claude_response(result)
                return {
                    "reviewer": self.agent_id,
                    "review_type": "code_review",
                    "review_output": review_output,
                    "timestamp": time.time()
                }
        except Exception as e:
            return {
                "reviewer": self.agent_id,
                "review_type": "code_review",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def _handle_feedback(self, feedback: Dict[str, Any]):
        """Handle feedback from manager"""
        self._last_feedback = feedback.get('feedback', '')
        revision_requests = feedback.get('revision_requests', [])
        
        if revision_requests:
            # Store revision requests for next task execution
            self._revision_requests = revision_requests
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        return {
            "total_queries": self.total_queries,
            "total_cost": self.total_cost,
            "session_id": self.session_id,
            "working_directory": self.working_directory,
            "model": self.model
        }
