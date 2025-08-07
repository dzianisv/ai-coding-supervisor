"""
VibeTeam MCP Server - Exposes VibeTeam agents via Model Context Protocol.

This server provides access to VibeTeam's AI agents (Claude Code Agent and
Engineering Manager) through the MCP protocol, allowing integration with
various AI assistants and tools.
"""
import argparse
import asyncio
import logging
import os
import re
import subprocess
import sys
import threading
import time
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


class CloudflareTunnel:
    """Manages Cloudflare tunnel for MCP server."""
    
    def __init__(self, port: int = 8080):
        """Initialize tunnel manager.
        
        Args:
            port: Local port to tunnel
        """
        self.port = port
        self.process = None
        self.tunnel_url = None
        self.logger = logging.getLogger(f"{__name__}.CloudflareTunnel")
    
    def find_cloudflared(self) -> Optional[str]:
        """Find cloudflared binary in common locations."""
        cloudflared_paths = [
            "./cloudflared",
            "/usr/local/bin/cloudflared", 
            "/opt/homebrew/bin/cloudflared",
            "cloudflared"  # In PATH
        ]
        
        for path in cloudflared_paths:
            try:
                result = subprocess.run([path, "--version"], capture_output=True)
                if result.returncode == 0:
                    return path
            except:
                continue
        return None
    
    def start(self) -> Optional[str]:
        """Start Cloudflare tunnel and return the URL.
        
        Returns:
            Public tunnel URL if successful, None otherwise
        """
        cloudflared_path = self.find_cloudflared()
        if not cloudflared_path:
            self.logger.error("cloudflared binary not found. Install it from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
            return None
        
        self.logger.info(f"Starting Cloudflare tunnel for port {self.port}...")
        
        self.process = subprocess.Popen(
            [cloudflared_path, 'tunnel', '--url', f'http://localhost:{self.port}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Wait for tunnel URL in a separate thread
        def get_tunnel_url():
            start_time = time.time()
            while time.time() - start_time < 30:
                if self.process.poll() is not None:
                    self.logger.error("Cloudflare tunnel process exited unexpectedly")
                    return
                
                line = self.process.stderr.readline()
                if line and 'trycloudflare.com' in line:
                    match = re.search(r'https://[\w\-]+\.trycloudflare\.com', line)
                    if match:
                        self.tunnel_url = match.group(0)
                        self.logger.info(f"🌐 Cloudflare tunnel active: {self.tunnel_url}")
                        return
            
            self.logger.error("Failed to get tunnel URL within 30 seconds")
        
        tunnel_thread = threading.Thread(target=get_tunnel_url)
        tunnel_thread.daemon = True
        tunnel_thread.start()
        tunnel_thread.join(timeout=35)
        
        return self.tunnel_url
    
    def stop(self):
        """Stop the Cloudflare tunnel."""
        if self.process:
            self.logger.info("Stopping Cloudflare tunnel...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            self.tunnel_url = None


class VibeTeamMCPServer:
    """VibeTeam MCP Server implementation."""
    
    def __init__(self, working_directory: Optional[str] = None, tunnel_mode: bool = False, http_port: int = 8080):
        """Initialize the VibeTeam MCP server.
        
        Args:
            working_directory: Working directory for agents (defaults to current)
            tunnel_mode: Enable Cloudflare tunnel mode
            http_port: Port for HTTP server when in tunnel mode
        """
        self.working_directory = working_directory or os.getcwd()
        self.tunnel_mode = tunnel_mode
        self.http_port = http_port
        self.tunnel = None
        self.http_server_process = None
        
        if tunnel_mode:
            # In tunnel mode, we need HTTP server + tunnel
            self.server = None  # Will create HTTP server instead
            self.tunnel = CloudflareTunnel(port=http_port)
        else:
            # Standard stdio mode
            self.server = StdioMCPServer(name="vibeteam", version="1.0.0")
        
        self.claude_agent = None
        self.eng_manager = None
        
        if not tunnel_mode:
            # Register tools for stdio mode
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
        
    def _start_http_server(self) -> None:
        """Start HTTP server for tunnel mode."""
        from flask import Flask, request, jsonify
        import json
        
        app = Flask(__name__)
        
        @app.route('/', methods=['POST'])
        def handle_mcp_request():
            """Handle MCP requests over HTTP."""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No JSON data provided"}), 400
                
                # Process MCP request directly
                response = self._process_mcp_request(data)
                return jsonify(response)
                
            except Exception as e:
                logger.error(f"Error processing HTTP request: {e}")
                return jsonify({"error": str(e)}), 500
        
        @app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint."""
            return jsonify({"status": "healthy", "service": "vibeteam-mcp"})
        
        # Start server in background thread
        def run_http_server():
            app.run(host='0.0.0.0', port=self.http_port, debug=False, threaded=True)
        
        import threading
        server_thread = threading.Thread(target=run_http_server)
        server_thread.daemon = True
        server_thread.start()
        
        logger.info(f"HTTP server started on port {self.http_port}")
    
    def _process_mcp_request(self, data: Dict) -> Dict:
        """Process MCP request directly without stdio server."""
        try:
            method = data.get('method')
            message_id = data.get('id')
            params = data.get('params', {})
            
            if method == 'initialize':
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "protocolVersion": "2025-01-21",
                        "capabilities": {
                            "tools": {"listChanged": True},
                            "resources": {"listChanged": True}
                        },
                        "serverInfo": {
                            "name": "vibeteam",
                            "version": "1.0.0"
                        }
                    }
                }
            
            elif method == 'tools/list':
                tools = [
                    {
                        "name": "execute_task",
                        "description": "Execute a coding task using Claude Code Agent",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string", "description": "Task description"}
                            },
                            "required": ["description"]
                        }
                    },
                    {
                        "name": "review_code", 
                        "description": "Review code for quality and improvements",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Code to review"},
                                "language": {"type": "string", "description": "Programming language"}
                            },
                            "required": ["code"]
                        }
                    }
                ]
                
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {"tools": tools}
                }
            
            elif method == 'tools/call':
                tool_name = params.get('name')
                arguments = params.get('arguments', {})
                
                # Execute tool
                if tool_name == 'execute_task':
                    result = self._execute_task_sync(arguments.get('description', ''))
                elif tool_name == 'review_code':
                    result = self._review_code_sync(arguments.get('code', ''), arguments.get('language', 'python'))
                else:
                    raise ValueError(f"Unknown tool: {tool_name}")
                
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "status": "completed",
                        "output": result
                    }
                }
            
            else:
                raise ValueError(f"Unknown method: {method}")
                
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": data.get('id'),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    def _execute_task_sync(self, description: str) -> str:
        """Execute task synchronously for HTTP mode."""
        # Initialize agent if needed
        if not self.claude_agent:
            self.claude_agent = ClaudeCodeAgent(
                working_directory=self.working_directory,
                permission_mode="bypassPermissions"
            )
        
        # Run async task in sync context
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                self.claude_agent.execute_task({"description": description})
            )
            return str(result)
        except Exception as e:
            return f"Task execution failed: {str(e)}"
    
    def _review_code_sync(self, code: str, language: str) -> str:
        """Review code synchronously for HTTP mode.""" 
        # Initialize agent if needed
        if not self.claude_agent:
            self.claude_agent = ClaudeCodeAgent(
                working_directory=self.working_directory,
                permission_mode="bypassPermissions"
            )
        
        # Run async task in sync context
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                self.claude_agent.review_work({"code": code, "language": language})
            )
            return str(result)
        except Exception as e:
            return f"Code review failed: {str(e)}"

    async def run(self) -> None:
        """Run the MCP server."""
        if self.tunnel_mode:
            await self.run_tunnel_mode()
        else:
            try:
                await self.server.start()
            except KeyboardInterrupt:
                logger.info("Server interrupted by user")
            except Exception as e:
                logger.error(f"Server error: {e}", exc_info=True)
                raise
            finally:
                await self.server.stop()
    
    async def run_tunnel_mode(self) -> None:
        """Run server in tunnel mode with HTTP server and Cloudflare tunnel."""
        try:
            # Start HTTP server
            logger.info("🚀 Starting VibeTeam MCP server in tunnel mode...")
            self._start_http_server()
            
            # Wait for HTTP server to be ready
            import time
            time.sleep(2)
            
            # Start Cloudflare tunnel
            tunnel_url = self.tunnel.start()
            if tunnel_url:
                logger.info(f"🌍 VibeTeam MCP server is publicly accessible at: {tunnel_url}")
                logger.info("📋 Use this URL in your MCP client configuration")
            else:
                logger.warning("⚠️ Cloudflare tunnel failed to start, server only available locally")
                logger.info(f"🏠 Local server running at: http://localhost:{self.http_port}")
            
            # Keep server running
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Server interrupted by user")
                
        except Exception as e:
            logger.error(f"Tunnel mode error: {e}", exc_info=True)
            raise
        finally:
            if self.tunnel:
                self.tunnel.stop()
            
    def run_sync(self) -> None:
        """Run the MCP server in synchronous mode (better for subprocesses)."""
        if self.tunnel_mode:
            # For tunnel mode, run in async context
            import asyncio
            try:
                asyncio.run(self.run_tunnel_mode())
            except KeyboardInterrupt:
                logger.info("Server interrupted by user")
            except Exception as e:
                logger.error(f"Server error: {e}", exc_info=True)
                raise
        else:
            # Standard stdio mode
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
    parser = argparse.ArgumentParser(
        description="VibeTeam MCP Server - AI coding agents via Model Context Protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vibeteam-mcp                        # Default: Cloudflare tunnel mode
  vibeteam-mcp --no-tunnel            # Standard MCP protocol (stdio)
  vibeteam-mcp --port 9000            # Custom HTTP port with tunnel
  vibeteam-mcp --dir /path/to/project # Custom working directory

Default tunnel mode automatically:
- Starts HTTP server on specified port (default: 8080)
- Launches Cloudflare tunnel for public access
- Provides public URL for MCP client integration

Use --no-tunnel for stdio protocol for direct local integration.
        """
    )
    parser.add_argument(
        "--no-tunnel",
        action="store_true",
        help="Disable Cloudflare tunnel mode (use stdio protocol instead)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        metavar="PORT",
        help="HTTP port for tunnel mode (default: 8080)"
    )
    parser.add_argument(
        "--dir", "-d",
        metavar="PATH",
        help="Working directory (default: current directory)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to console"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="vibeteam-mcp 1.0.0"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    handlers = [logging.FileHandler('vibeteam-mcp.log')]
    
    if args.debug or os.getenv('MCP_DEBUG'):
        handlers.append(logging.StreamHandler())
    else:
        handlers.append(logging.NullHandler())
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # Get working directory from args or environment or use current
    working_dir = args.dir or os.getenv('VIBETEAM_WORKING_DIR', os.getcwd())
    
    # Create and run server (tunnel mode is now default)
    if args.no_tunnel:
        logger.info("📡 Starting VibeTeam MCP server in standard mode (stdio)")
        logger.info(f"📁 Working directory: {working_dir}")
        server = VibeTeamMCPServer(working_directory=working_dir)
    else:
        logger.info(f"🌐 Starting VibeTeam MCP server in tunnel mode (default)")
        logger.info(f"📁 Working directory: {working_dir}")
        logger.info(f"🔌 HTTP port: {args.port}")
        server = VibeTeamMCPServer(
            working_directory=working_dir,
            tunnel_mode=True,
            http_port=args.port
        )
    
    server.run_sync()


if __name__ == "__main__":
    main_console()