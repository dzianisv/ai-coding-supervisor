"""
Interactive Team Interface for Multi-Agent Coding Tool
"""

import asyncio
from typing import Dict, Any, Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
import json

from agents import EngineeringManager, AgentRegistry
from agents.base_agent import AgentStatus


class TeamInterface:
    """Interactive interface for managing the multi-agent team"""
    
    def __init__(self, manager: EngineeringManager, registry: AgentRegistry, console: Console):
        self.manager = manager
        self.registry = registry
        self.console = console
        self.running = True
        
    async def run(self):
        """Main interface loop"""
        
        self.console.print(Panel.fit(
            "🤖 Multi-Agent Coding Team Ready!\n\n"
            "Commands:\n"
            "• task <description> - Execute a coding task\n"
            "• status - Show team status\n"
            "• agents - List all agents\n"
            "• history - Show recent task history\n"
            "• help - Show help\n"
            "• quit - Exit",
            title="Team Interface"
        ))
        
        while self.running:
            try:
                # Get user input
                command = Prompt.ask("\n[bold blue]Team>[/bold blue]", default="help")
                
                if command.lower() in ['quit', 'exit', 'q']:
                    break
                elif command.lower() == 'help':
                    await self._show_help()
                elif command.lower() == 'status':
                    await self._show_status()
                elif command.lower() == 'agents':
                    await self._show_agents()
                elif command.lower() == 'history':
                    await self._show_history()
                elif command.lower().startswith('task '):
                    task_description = command[5:].strip()
                    if task_description:
                        await self._execute_task(task_description)
                    else:
                        self.console.print("[red]Please provide a task description[/red]")
                else:
                    self.console.print(f"[red]Unknown command: {command}[/red]")
                    self.console.print("Type 'help' for available commands")
                    
            except KeyboardInterrupt:
                if Confirm.ask("\nAre you sure you want to quit?"):
                    break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
        
        self.console.print("[yellow]👋 Goodbye![/yellow]")
    
    async def _show_help(self):
        """Show help information"""
        help_table = Table(title="Available Commands")
        help_table.add_column("Command", style="cyan")
        help_table.add_column("Description", style="white")
        help_table.add_column("Example", style="dim")
        
        help_table.add_row("task <description>", "Execute a coding task", "task Create a REST API for user management")
        help_table.add_row("status", "Show current team status", "status")
        help_table.add_row("agents", "List all registered agents", "agents")
        help_table.add_row("history", "Show recent task history", "history")
        help_table.add_row("help", "Show this help message", "help")
        help_table.add_row("quit", "Exit the interface", "quit")
        
        self.console.print(help_table)
    
    async def _show_status(self):
        """Show team status"""
        status = self.registry.get_registry_status()
        team_status = self.manager.get_team_status()
        
        # Create status table
        status_table = Table(title="Team Status")
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="white")
        
        status_table.add_row("Total Agents", str(status['total_agents']))
        status_table.add_row("Active Subtasks", str(team_status['active_subtasks']))
        status_table.add_row("Completed Subtasks", str(team_status['completed_subtasks']))
        
        # Status distribution
        for status_type, count in status['status_distribution'].items():
            if count > 0:
                status_table.add_row(f"Agents {status_type.title()}", str(count))
        
        self.console.print(status_table)
        
        # Show active assignments
        if team_status['task_assignments']:
            assign_table = Table(title="Current Task Assignments")
            assign_table.add_column("Subtask ID", style="cyan")
            assign_table.add_column("Agent", style="white")
            
            for subtask_id, agent_id in team_status['task_assignments'].items():
                agent = self.registry.get_agent(agent_id)
                agent_name = agent.name if agent else agent_id
                assign_table.add_row(subtask_id, agent_name)
            
            self.console.print(assign_table)
    
    async def _show_agents(self):
        """Show all registered agents"""
        agents_table = Table(title="Registered Agents")
        agents_table.add_column("ID", style="cyan")
        agents_table.add_column("Name", style="white")
        agents_table.add_column("Status", style="green")
        agents_table.add_column("Capabilities", style="dim")
        
        for agent in self.registry.get_all_agents():
            capabilities = ", ".join([cap.value for cap in agent.capabilities])
            status_color = "green" if agent.status == AgentStatus.IDLE else "yellow"
            
            agents_table.add_row(
                agent.agent_id,
                agent.name,
                f"[{status_color}]{agent.status.value}[/{status_color}]",
                capabilities
            )
        
        self.console.print(agents_table)
    
    async def _show_history(self):
        """Show recent task history"""
        # Get history from manager
        manager_results = self.manager.get_results_summary()
        
        if not manager_results['recent_results']:
            self.console.print("[yellow]No recent task history[/yellow]")
            return
        
        history_table = Table(title="Recent Task History")
        history_table.add_column("Task ID", style="cyan")
        history_table.add_column("Status", style="white")
        history_table.add_column("Duration", style="dim")
        history_table.add_column("Errors", style="red")
        
        for result in manager_results['recent_results']:
            status_color = "green" if result.status == AgentStatus.COMPLETED else "red"
            error_count = len(result.errors) if result.errors else 0
            
            history_table.add_row(
                result.task_id,
                f"[{status_color}]{result.status.value}[/{status_color}]",
                f"{result.execution_time:.2f}s",
                str(error_count) if error_count > 0 else "-"
            )
        
        self.console.print(history_table)
    
    async def _execute_task(self, task_description: str):
        """Execute a task with progress tracking"""
        
        self.console.print(f"\n[bold blue]🎯 Executing Task:[/bold blue] {task_description}")
        
        # Confirm task execution
        if not Confirm.ask("Proceed with task execution?", default=True):
            return
        
        # Prepare task
        task = {
            "id": f"interactive_task_{int(asyncio.get_event_loop().time())}",
            "description": task_description
        }
        
        # Execute with progress tracking
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                
                task_progress = progress.add_task("Executing task...", total=None)
                
                # Run task
                result = await self.manager.execute_task(task)
                
                progress.update(task_progress, description="Task completed!")
            
            # Show results
            await self._show_task_results(result)
            
        except Exception as e:
            self.console.print(f"[red]❌ Task execution failed: {e}[/red]")
    
    async def _show_task_results(self, result):
        """Show task execution results"""
        
        # Create results panel
        if result.status == AgentStatus.COMPLETED:
            title = "[green]✅ Task Completed Successfully[/green]"
            style = "green"
        else:
            title = "[red]❌ Task Failed[/red]"
            style = "red"
        
        # Format output
        output_text = []
        
        if result.output:
            if 'subtasks_completed' in result.output:
                output_text.append(f"Subtasks completed: {result.output['subtasks_completed']}/{result.output['total_subtasks']}")
            
            if 'results' in result.output:
                output_text.append(f"Detailed results: {len(result.output['results'])} items")
        
        if result.artifacts:
            output_text.append(f"Files created/modified: {len(result.artifacts)}")
        
        if result.errors:
            output_text.append(f"Errors: {len(result.errors)}")
            for error in result.errors[:3]:  # Show first 3 errors
                output_text.append(f"  • {error}")
        
        output_text.append(f"Execution time: {result.execution_time:.2f}s")
        
        results_panel = Panel(
            "\n".join(output_text),
            title=title,
            border_style=style
        )
        
        self.console.print(results_panel)
        
        # Ask if user wants to see detailed results
        if result.output and 'results' in result.output and result.output['results']:
            if Confirm.ask("Show detailed subtask results?", default=False):
                await self._show_detailed_results(result.output['results'])
    
    async def _show_detailed_results(self, detailed_results: Dict[str, Any]):
        """Show detailed subtask results"""
        
        for subtask_id, subtask_result in detailed_results.items():
            subtask_info = subtask_result.get('subtask', {})
            result_info = subtask_result.get('result', {})
            review_info = subtask_result.get('review', {})
            
            # Create subtask panel
            content = []
            content.append(f"Title: {subtask_info.get('title', 'Unknown')}")
            content.append(f"Status: {result_info.get('status', 'Unknown')}")
            
            if review_info:
                content.append(f"Quality Score: {review_info.get('quality_score', 'N/A')}/10")
                content.append(f"Approval: {'✅' if review_info.get('approval') else '❌'}")
            
            if result_info.get('artifacts'):
                content.append(f"Artifacts: {', '.join(result_info['artifacts'])}")
            
            panel = Panel(
                "\n".join(content),
                title=f"Subtask: {subtask_id}",
                border_style="blue"
            )
            
            self.console.print(panel)
