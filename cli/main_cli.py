"""
Main CLI Interface for Multi-Agent Coding Tool
"""

import asyncio
import click
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import EngineeringManager, AgentRegistry
from agents.claude_code_agent import ClaudeCodeAgent
from .interface import TeamInterface


@click.group()
@click.version_option(version="1.0.0")
def main_cli():
    """Multi-Agent Coding Tool - A team of AI agents for complex coding tasks"""
    pass


@main_cli.command()
@click.option('--working-dir', '-w', default=None, help='Working directory for the project')
@click.option('--model', '-m', default='gpt-4', help='Model for Engineering Manager (default: gpt-4)')
@click.option('--claude-model', default=None, help='Model for Claude coding agents')
@click.option('--agents', '-a', default=1, help='Number of Claude coding agents to spawn (default: 1)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def start(working_dir, model, claude_model, agents, verbose):
    """Start the multi-agent coding team"""
    
    console = Console()
    
    # Set working directory
    if working_dir:
        working_dir = os.path.abspath(working_dir)
        if not os.path.exists(working_dir):
            console.print(f"[red]Error: Working directory {working_dir} does not exist[/red]")
            return
    else:
        working_dir = os.getcwd()
    
    console.print(Panel.fit(
        f"🚀 Starting Multi-Agent Coding Team\n"
        f"Working Directory: {working_dir}\n"
        f"Manager Model: {model}\n"
        f"Claude Agents: {agents}",
        title="Initialization"
    ))
    
    # Run the async interface
    asyncio.run(_run_team_interface(working_dir, model, claude_model, agents, verbose))


async def _run_team_interface(working_dir: str, model: str, claude_model: str, num_agents: int, verbose: bool):
    """Run the team interface"""
    
    console = Console()
    
    try:
        # Initialize components
        registry = AgentRegistry()
        
        # Create Engineering Manager
        manager = EngineeringManager(model=model)
        registry.register_agent(manager)
        
        # Create Claude coding agents
        for i in range(num_agents):
            agent_id = f"claude_coder_{i+1}"
            claude_agent = ClaudeCodeAgent(
                agent_id=agent_id,
                working_directory=working_dir,
                model=claude_model
            )
            registry.register_agent(claude_agent)
            manager.register_agent(claude_agent)
        
        console.print(f"[green]✅ Initialized team with {num_agents + 1} agents[/green]")
        
        # Create and run interface
        interface = TeamInterface(manager, registry, console)
        await interface.run()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Shutting down gracefully...[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
    finally:
        # Cleanup
        if 'registry' in locals():
            await registry.shutdown_all_agents()


@main_cli.command()
@click.argument('task_description')
@click.option('--working-dir', '-w', default=None, help='Working directory for the project')
@click.option('--model', '-m', default='gpt-4', help='Model for Engineering Manager')
@click.option('--agents', '-a', default=1, help='Number of coding agents')
@click.option('--output', '-o', help='Output file for results')
def execute(task_description, working_dir, model, agents, output):
    """Execute a single task and exit"""
    
    console = Console()
    
    # Set working directory
    if working_dir:
        working_dir = os.path.abspath(working_dir)
    else:
        working_dir = os.getcwd()
    
    console.print(f"[blue]🎯 Executing task: {task_description}[/blue]")
    
    # Run the task execution
    result = asyncio.run(_execute_single_task(task_description, working_dir, model, agents))
    
    if output:
        # Save results to file
        import json
        with open(output, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        console.print(f"[green]📄 Results saved to {output}[/green]")
    
    # Print summary
    if result.status.value == "completed":
        console.print("[green]✅ Task completed successfully![/green]")
    else:
        console.print(f"[red]❌ Task failed: {result.errors}[/red]")


async def _execute_single_task(task_description: str, working_dir: str, model: str, num_agents: int):
    """Execute a single task"""
    
    # Initialize components
    registry = AgentRegistry()
    manager = EngineeringManager(model=model)
    registry.register_agent(manager)
    
    # Create coding agents
    for i in range(num_agents):
        agent_id = f"claude_coder_{i+1}"
        claude_agent = ClaudeCodeAgent(
            agent_id=agent_id,
            working_directory=working_dir
        )
        registry.register_agent(claude_agent)
        manager.register_agent(claude_agent)
    
    # Execute task
    task = {
        "id": "cli_task",
        "description": task_description
    }
    
    try:
        result = await manager.execute_task(task)
        return result
    finally:
        await registry.shutdown_all_agents()


@main_cli.command()
def status():
    """Show status of running agents (if any)"""
    console = Console()
    console.print("[yellow]Status command not yet implemented for persistent agents[/yellow]")
    console.print("Use 'start' command to launch interactive session")


@main_cli.command()
@click.option('--config-file', default='team_config.json', help='Configuration file path')
def configure(config_file):
    """Configure the multi-agent team settings"""
    
    console = Console()
    
    # Interactive configuration
    config = {}
    
    console.print(Panel.fit("🔧 Team Configuration", title="Setup"))
    
    config['default_model'] = Prompt.ask("Engineering Manager model", default="gpt-4")
    config['claude_model'] = Prompt.ask("Claude coding agent model", default="claude-3-sonnet-20240229")
    config['default_agents'] = int(Prompt.ask("Default number of coding agents", default="2"))
    config['working_directory'] = Prompt.ask("Default working directory", default=os.getcwd())
    
    # Advanced settings
    if Prompt.ask("Configure advanced settings?", choices=["y", "n"], default="n") == "y":
        config['max_task_time'] = int(Prompt.ask("Max task execution time (seconds)", default="3600"))
        config['retry_attempts'] = int(Prompt.ask("Max retry attempts", default="3"))
        config['log_level'] = Prompt.ask("Log level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")
    
    # Save configuration
    import json
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    console.print(f"[green]✅ Configuration saved to {config_file}[/green]")


if __name__ == '__main__':
    main_cli()
