#!/usr/bin/env python3
"""
Demo script for Multi-Agent Coding Tool
Shows basic functionality without requiring API keys
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agents import EngineeringManager, AgentRegistry
from agents.claude_code_agent import ClaudeCodeAgent
from rich.console import Console


async def demo_basic_functionality():
    """Demonstrate basic multi-agent functionality"""
    console = Console()
    
    console.print("[bold blue]🚀 Multi-Agent Coding Tool Demo[/bold blue]\n")
    
    # Initialize components
    console.print("1. Initializing agent registry...")
    registry = AgentRegistry()
    
    # Create Engineering Manager (mock mode for demo)
    console.print("2. Creating Engineering Manager...")
    manager = EngineeringManager(model="mock-gpt-4")
    registry.register_agent(manager)
    
    # Create coding agents
    console.print("3. Creating coding agents...")
    for i in range(2):
        agent_id = f"claude_coder_{i+1}"
        claude_agent = ClaudeCodeAgent(
            agent_id=agent_id,
            working_directory=str(Path.cwd()),
            model="mock-claude"
        )
        registry.register_agent(claude_agent)
        manager.register_agent(claude_agent)
    
    # Show team status
    console.print("\n4. Team Status:")
    status = registry.get_registry_status()
    
    console.print(f"   • Total agents: {status['total_agents']}")
    console.print(f"   • Agent distribution:")
    for agent_id, agent_info in status['agents'].items():
        console.print(f"     - {agent_info['name']} ({agent_id}): {agent_info['status']}")
    
    # Show capabilities
    console.print("\n5. Team Capabilities:")
    for capability, count in status['capability_distribution'].items():
        if count > 0:
            console.print(f"   • {capability}: {count} agents")
    
    # Demo task structure (without actual execution)
    console.print("\n6. Sample Task Structure:")
    sample_task = {
        "id": "demo_task",
        "description": "Create a simple Python web API with user authentication",
        "complexity": 7,
        "estimated_time": "2-3 hours"
    }
    
    console.print(f"   Task: {sample_task['description']}")
    console.print(f"   Complexity: {sample_task['complexity']}/10")
    console.print(f"   Estimated time: {sample_task['estimated_time']}")
    
    console.print("\n7. Workflow Overview:")
    workflow_steps = [
        "Engineering Manager receives task",
        "Task is decomposed into subtasks",
        "Subtasks are assigned to coding agents",
        "Agents execute their assigned work",
        "Manager reviews completed work",
        "Feedback is provided if revisions needed",
        "Final results are compiled and delivered"
    ]
    
    for i, step in enumerate(workflow_steps, 1):
        console.print(f"   {i}. {step}")
    
    console.print(f"\n[green]✅ Demo completed! The multi-agent system is ready.[/green]")
    console.print(f"[yellow]💡 To run with real AI models, set up API keys and use:[/yellow]")
    console.print(f"   python team_coding_tool.py start")
    
    # Cleanup
    await registry.shutdown_all_agents()


if __name__ == "__main__":
    asyncio.run(demo_basic_functionality())
