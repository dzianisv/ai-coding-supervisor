"""
VibeTeam MCP Server - Exposes VibeTeam agents via Model Context Protocol.

This server provides access to VibeTeam's AI agents (Claude Code Agent and
Engineering Manager) through the MCP protocol, allowing integration with
various AI assistants and tools.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.stdio_server import StdioMCPServer
from mcp.stdio_server_sync import SyncStdioMCPServer
from agents.claude_code_agent import ClaudeCodeAgent
from agents.engineering_manager import EngineeringManager

logger = logging.getLogger(__name__)


class VibeTeamMCPServer:
    """VibeTeam MCP Server implementation."""
    
    def __init__(self, working_directory: Optional[str] = None):
        """Initialize the VibeTeam MCP server.
        
        Args:
            working_directory: Working directory for agents (defaults to current)
        """
        self.working_directory = working_directory or os.getcwd()
        self.server = StdioMCPServer(name="vibeteam", version="1.0.0")
        self.claude_agent = None
        self.eng_manager = None
        
        # Register tools
        self._register_tools()
        
        # Register resources
        self._register_resources()
        
    def _register_tools(self) -> None:
        """Register all available tools."""
        # Execute task tool
        self.server.add_tool(
            name="execute_task",
            description="Execute a software engineering task using Claude Code Agent",
            parameters={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the task to execute"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for the task (optional)"
                    }
                },
                "required": ["description"]
            },
            handler=self._handle_execute_task
        )
        
        # Code review tool
        self.server.add_tool(
            name="review_code",
            description="Review code for quality, bugs, and improvements",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to review"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language (e.g., python, javascript)"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about the code (optional)"
                    }
                },
                "required": ["code", "language"]
            },
            handler=self._handle_review_code
        )
        
        # Generate code tool
        self.server.add_tool(
            name="generate_code",
            description="Generate code based on specifications",
            parameters={
                "type": "object",
                "properties": {
                    "specification": {
                        "type": "string",
                        "description": "Detailed specification of what to generate"
                    },
                    "language": {
                        "type": "string",
                        "description": "Target programming language"
                    },
                    "style_guide": {
                        "type": "string",
                        "description": "Code style guidelines to follow (optional)"
                    }
                },
                "required": ["specification", "language"]
            },
            handler=self._handle_generate_code
        )
        
        # Fix code tool
        self.server.add_tool(
            name="fix_code",
            description="Fix bugs or issues in code",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code with issues"
                    },
                    "error_message": {
                        "type": "string",
                        "description": "Error message or description of the issue"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language"
                    }
                },
                "required": ["code", "error_message", "language"]
            },
            handler=self._handle_fix_code
        )
        
        # Write tests tool
        self.server.add_tool(
            name="write_tests",
            description="Write unit tests for code",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to write tests for"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language"
                    },
                    "test_framework": {
                        "type": "string",
                        "description": "Test framework to use (e.g., pytest, jest)"
                    }
                },
                "required": ["code", "language", "test_framework"]
            },
            handler=self._handle_write_tests
        )
        
        # Complete tasks from array
        self.server.add_tool(
            name="complete_tasks",
            description="Complete an array of tasks sequentially",
            parameters={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Array of task descriptions to complete"
                    },
                    "max_tasks": {
                        "type": "integer",
                        "description": "Maximum number of tasks to complete (optional, default: all)"
                    }
                },
                "required": ["tasks"]
            },
            handler=self._handle_complete_tasks
        )
        
        # VibeTeam task workflow (similar to vibeteam-task command)
        self.server.add_tool(
            name="vibeteam_task_workflow",
            description="Execute the full vibeteam-task workflow: get task, complete it, test, fix issues, commit",
            parameters={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Array of task descriptions in checkbox format (e.g., '[ ] Implement feature X')"
                    },
                    "auto_commit": {
                        "type": "boolean",
                        "description": "Automatically commit changes after completing each task (default: false)"
                    }
                },
                "required": ["tasks"]
            },
            handler=self._handle_vibeteam_task_workflow
        )
        
        # Manage project tool (Engineering Manager)
        self.server.add_tool(
            name="manage_project",
            description="Use Engineering Manager to coordinate multiple agents on a project",
            parameters={
                "type": "object",
                "properties": {
                    "project_description": {
                        "type": "string",
                        "description": "Description of the project to manage"
                    },
                    "team_size": {
                        "type": "integer",
                        "description": "Number of agents to coordinate (default: 2)"
                    }
                },
                "required": ["project_description"]
            },
            handler=self._handle_manage_project
        )
        
    def _register_resources(self) -> None:
        """Register available resources."""
        # Current working directory
        self.server.add_resource(
            uri="workspace:///",
            name="Current Workspace",
            description="Files in the current working directory",
            handler=self._handle_workspace_resource
        )
        
        # Tasks file
        self.server.add_resource(
            uri="workspace:///tasks.md",
            name="Tasks File",
            description="Current tasks.md file if it exists",
            handler=self._handle_tasks_resource
        )
        
        # Agent status
        self.server.add_resource(
            uri="agent:///status",
            name="Agent Status",
            description="Current status of VibeTeam agents",
            handler=self._handle_agent_status_resource
        )
        
    async def _ensure_claude_agent(self) -> ClaudeCodeAgent:
        """Ensure Claude agent is initialized."""
        if not self.claude_agent:
            self.claude_agent = ClaudeCodeAgent(
                working_directory=self.working_directory,
                permission_mode="bypassPermissions"
            )
        return self.claude_agent
        
    async def _ensure_eng_manager(self) -> EngineeringManager:
        """Ensure Engineering Manager is initialized."""
        if not self.eng_manager:
            self.eng_manager = EngineeringManager(
                "vibeteam-manager",
                production=False
            )
            # Register Claude agent
            claude = await self._ensure_claude_agent()
            self.eng_manager.register_agent(claude)
        return self.eng_manager
        
    async def _handle_execute_task(self, description: str, 
                                  working_directory: Optional[str] = None) -> Dict[str, Any]:
        """Handle execute_task tool."""
        try:
            # Use provided directory or default
            work_dir = working_directory or self.working_directory
            
            # Change to working directory
            original_dir = os.getcwd()
            if work_dir != original_dir:
                os.chdir(work_dir)
                
            try:
                agent = await self._ensure_claude_agent()
                result = await agent.execute_task({
                    "description": description
                })
                
                return {
                    "status": "success",
                    "result": result,
                    "working_directory": work_dir
                }
            finally:
                # Restore original directory
                if work_dir != original_dir:
                    os.chdir(original_dir)
                    
        except Exception as e:
            logger.error(f"Error executing task: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _handle_review_code(self, code: str, language: str,
                                 context: Optional[str] = None) -> Dict[str, Any]:
        """Handle review_code tool."""
        try:
            agent = await self._ensure_claude_agent()
            
            task = {
                "type": "review_code",
                "code": code,
                "language": language
            }
            if context:
                task["context"] = context
                
            result = await agent.review_work(task)
            
            return {
                "status": "success",
                "review": result
            }
        except Exception as e:
            logger.error(f"Error reviewing code: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _handle_generate_code(self, specification: str, language: str,
                                   style_guide: Optional[str] = None) -> Dict[str, Any]:
        """Handle generate_code tool."""
        try:
            agent = await self._ensure_claude_agent()
            
            prompt = f"Generate {language} code for: {specification}"
            if style_guide:
                prompt += f"\n\nFollow this style guide: {style_guide}"
                
            result = await agent.execute_task({
                "type": "generate_code",
                "description": prompt,
                "language": language
            })
            
            return {
                "status": "success",
                "code": result
            }
        except Exception as e:
            logger.error(f"Error generating code: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _handle_fix_code(self, code: str, error_message: str,
                              language: str) -> Dict[str, Any]:
        """Handle fix_code tool."""
        try:
            agent = await self._ensure_claude_agent()
            
            result = await agent.execute_task({
                "type": "debug_code",
                "code": code,
                "error_message": error_message,
                "language": language
            })
            
            return {
                "status": "success",
                "fixed_code": result
            }
        except Exception as e:
            logger.error(f"Error fixing code: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _handle_write_tests(self, code: str, language: str,
                                 test_framework: str) -> Dict[str, Any]:
        """Handle write_tests tool."""
        try:
            agent = await self._ensure_claude_agent()
            
            result = await agent.execute_task({
                "type": "write_tests",
                "code": code,
                "language": language,
                "test_framework": test_framework
            })
            
            return {
                "status": "success",
                "tests": result
            }
        except Exception as e:
            logger.error(f"Error writing tests: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _handle_complete_tasks(self, tasks: List[str],
                                   max_tasks: Optional[int] = None) -> Dict[str, Any]:
        """Handle complete_tasks tool."""
        try:
            if not tasks:
                return {
                    "status": "error",
                    "error": "No tasks provided"
                }
                
            # Limit tasks if max_tasks is specified
            tasks_to_complete = tasks[:max_tasks] if max_tasks else tasks
            
            agent = await self._ensure_claude_agent()
            results = []
            completed_count = 0
            
            # Process each task
            for i, task in enumerate(tasks_to_complete):
                try:
                    logger.info(f"Processing task {i+1}/{len(tasks_to_complete)}: {task}")
                    
                    # Execute the task
                    result = await agent.execute_task({
                        "description": task
                    })
                    
                    results.append({
                        "task": task,
                        "status": "completed",
                        "result": result
                    })
                    completed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing task '{task}': {e}")
                    results.append({
                        "task": task,
                        "status": "failed",
                        "error": str(e)
                    })
                    
            return {
                "status": "success",
                "total_tasks": len(tasks),
                "processed_tasks": len(tasks_to_complete),
                "completed_tasks": completed_count,
                "failed_tasks": len(tasks_to_complete) - completed_count,
                "results": results
            }
                
        except Exception as e:
            logger.error(f"Error completing tasks: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _handle_vibeteam_task_workflow(self, tasks: List[str],
                                           auto_commit: bool = False) -> Dict[str, Any]:
        """Handle vibeteam_task_workflow tool - full workflow like vibeteam-task command."""
        try:
            if not tasks:
                return {
                    "status": "error",
                    "error": "No tasks provided"
                }
                
            agent = await self._ensure_claude_agent()
            results = []
            
            # The full prompt from vibeteam-task
            base_prompt = "You are a software Engineer. Your task is to get a task from the following list. Complete it. Cover with test. Run test. Fix any related issues if any. Re-run test. Reflect. Review git diff. Reflect. Fix if any issues."
            if auto_commit:
                base_prompt += " Commit"
                
            # Process tasks that are not completed (start with [ ])
            uncompleted_tasks = [t for t in tasks if t.strip().startswith("[ ]")]
            
            for i, task in enumerate(uncompleted_tasks):
                try:
                    # Extract task description (remove checkbox prefix)
                    task_desc = task.strip()[3:].strip() if task.strip().startswith("[ ]") else task.strip()
                    
                    logger.info(f"Processing task {i+1}/{len(uncompleted_tasks)}: {task_desc}")
                    
                    # Create full prompt with specific task
                    full_prompt = f"{base_prompt}\n\nTask to complete: {task_desc}"
                    
                    # Execute the full workflow
                    result = await agent.execute_task({
                        "description": full_prompt
                    })
                    
                    results.append({
                        "task": task_desc,
                        "status": "completed",
                        "result": result,
                        "committed": auto_commit
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing task '{task}': {e}")
                    results.append({
                        "task": task,
                        "status": "failed",
                        "error": str(e)
                    })
                    
            completed_count = sum(1 for r in results if r["status"] == "completed")
            
            return {
                "status": "success",
                "total_tasks": len(tasks),
                "uncompleted_tasks": len(uncompleted_tasks),
                "processed_tasks": len(results),
                "completed_tasks": completed_count,
                "failed_tasks": len(results) - completed_count,
                "results": results
            }
                
        except Exception as e:
            logger.error(f"Error in vibeteam task workflow: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _handle_manage_project(self, project_description: str,
                                   team_size: int = 2) -> Dict[str, Any]:
        """Handle manage_project tool."""
        try:
            manager = await self._ensure_eng_manager()
            
            # Create project task
            result = await manager.coordinate_task({
                "description": project_description,
                "team_size": team_size
            })
            
            return {
                "status": "success",
                "project_result": result
            }
        except Exception as e:
            logger.error(f"Error managing project: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _handle_workspace_resource(self) -> str:
        """Handle workspace resource read."""
        try:
            files = []
            for root, dirs, filenames in os.walk(self.working_directory):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                rel_root = os.path.relpath(root, self.working_directory)
                if rel_root == ".":
                    rel_root = ""
                    
                for filename in filenames:
                    if not filename.startswith('.'):
                        filepath = os.path.join(rel_root, filename) if rel_root else filename
                        files.append(filepath)
                        
            return f"Files in workspace:\n" + "\n".join(sorted(files))
        except Exception as e:
            return f"Error reading workspace: {str(e)}"
            
    async def _handle_tasks_resource(self) -> str:
        """Handle tasks.md resource read."""
        try:
            task_path = os.path.join(self.working_directory, "tasks.md")
            if os.path.exists(task_path):
                with open(task_path, 'r') as f:
                    return f.read()
            else:
                return "No tasks.md file found in the current directory"
        except Exception as e:
            return f"Error reading tasks.md: {str(e)}"
            
    async def _handle_agent_status_resource(self) -> str:
        """Handle agent status resource read."""
        status = []
        status.append(f"Working Directory: {self.working_directory}")
        status.append("")
        
        if self.claude_agent:
            status.append("Claude Code Agent: Active")
        else:
            status.append("Claude Code Agent: Not initialized")
            
        if self.eng_manager:
            status.append("Engineering Manager: Active")
            agent_count = len(self.eng_manager._agents) if hasattr(self.eng_manager, '_agents') else 0
            status.append(f"  Registered agents: {agent_count}")
        else:
            status.append("Engineering Manager: Not initialized")
            
        return "\n".join(status)
        
    async def run(self) -> None:
        """Run the MCP server."""
        try:
            await self.server.start()
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            raise
        finally:
            await self.server.stop()
            
    def run_sync(self) -> None:
        """Run the MCP server in synchronous mode (better for subprocesses)."""
        sync_server = SyncStdioMCPServer(self.server)
        try:
            sync_server.start()
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            raise


async def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('vibeteam-mcp.log'),
            logging.StreamHandler() if os.getenv('MCP_DEBUG') else logging.NullHandler()
        ]
    )
    
    # Get working directory from environment or use current
    working_dir = os.getenv('VIBETEAM_WORKING_DIR', os.getcwd())
    
    # Create and run server
    server = VibeTeamMCPServer(working_directory=working_dir)
    await server.run()


def main_console():
    """Console entry point for vibeteam-mcp command."""
    # Use synchronous mode for better subprocess compatibility
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('vibeteam-mcp.log'),
            logging.StreamHandler() if os.getenv('MCP_DEBUG') else logging.NullHandler()
        ]
    )
    
    # Get working directory from environment or use current
    working_dir = os.getenv('VIBETEAM_WORKING_DIR', os.getcwd())
    
    # Create and run server in sync mode
    server = VibeTeamMCPServer(working_directory=working_dir)
    server.run_sync()


if __name__ == "__main__":
    main_console()