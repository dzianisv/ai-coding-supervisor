"""
Performance and stress integration tests with real LLM queries
"""

import asyncio
import pytest
import pytest_asyncio
import time
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import EngineeringManager, AgentRegistry
from agents.claude_code_agent import ClaudeCodeAgent
from tests.test_utils import (
    skip_if_no_litellm_key,
    TempWorkspace,
    create_test_files,
    get_test_models,
    TestTaskBuilder,
    validate_task_result
)


@pytest.mark.integration
@pytest.mark.requires_api
@pytest.mark.slow
class TestPerformanceIntegration:
    """Performance tests with real LLM queries"""
    
    @pytest_asyncio.fixture
    async def performance_team(self):
        """Set up team for performance testing"""
        skip_if_no_litellm_key()
        
        models = get_test_models()
        registry = AgentRegistry()
        
        with TempWorkspace() as workspace:
            create_test_files(workspace)
            
            # Create Engineering Manager
            manager = EngineeringManager(
                agent_id="perf_manager",
                model=models.get("manager", "gpt-3.5-turbo")
            )
            registry.register_agent(manager)
            
            # Create multiple coding agents for parallel testing
            for i in range(3):
                agent_id = f"perf_claude_coder_{i+1}"
                claude_agent = ClaudeCodeAgent(
                    agent_id=agent_id,
                    working_directory=str(workspace),
                    model=models.get("claude")
                )
                registry.register_agent(claude_agent)
                manager.register_agent(claude_agent)
            
            yield manager, registry, workspace
        
        await registry.shutdown_all_agents()
    
    @pytest.mark.asyncio
    async def test_task_execution_timing(self, performance_team):
        """Test task execution timing with real LLM"""
        manager, registry, workspace = performance_team
        
        task = TestTaskBuilder.simple_coding_task()
        
        # Measure execution time
        start_time = time.time()
        result = await manager.execute_task(task)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Validate result
        assert validate_task_result(result)
        
        # Performance assertions
        assert execution_time < 180  # Should complete within 3 minutes
        assert execution_time > 5    # Should take at least 5 seconds for real work
        
        # Check that reported execution time is reasonable
        assert abs(result.execution_time - execution_time) < 10  # Within 10 seconds
    
    @pytest.mark.asyncio
    async def test_multiple_agents_coordination_performance(self, performance_team):
        """Test performance with multiple agents working together"""
        manager, registry, workspace = performance_team
        
        # Complex task that should utilize multiple agents
        task = {
            "id": "perf_complex_task",
            "description": "Create a Python package with multiple modules: a data processor, a file handler, a logger utility, and a main CLI interface. Include proper documentation and tests for each module.",
            "complexity": 8
        }
        
        start_time = time.time()
        result = await manager.execute_task(task)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Validate result
        assert validate_task_result(result)
        
        # Performance expectations for complex task
        assert execution_time < 300  # Should complete within 5 minutes
        assert result.output["total_subtasks"] >= 3  # Should create multiple subtasks
        
        # Verify multiple agents were potentially coordinated
        team_status = manager.get_team_status()
        assert len(team_status["team_status"]) >= 3  # Manager + multiple coding agents
    
    @pytest.mark.asyncio
    async def test_concurrent_task_handling(self, performance_team):
        """Test handling multiple tasks concurrently (stress test)"""
        manager, registry, workspace = performance_team
        
        # Create multiple simple tasks
        tasks = [
            TestTaskBuilder.simple_coding_task(),
            TestTaskBuilder.file_modification_task(),
            {
                "id": "concurrent_task_3",
                "description": "Create a simple data validation function",
                "complexity": 2
            }
        ]
        
        # Execute tasks concurrently
        start_time = time.time()
        
        # Note: In real implementation, we'd need to modify the manager
        # to handle concurrent tasks. For now, we'll run them sequentially
        # but measure the total time
        results = []
        for task in tasks:
            result = await manager.execute_task(task)
            results.append(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Validate all results
        for result in results:
            assert validate_task_result(result)
        
        # Performance assertion - should be reasonable for sequential execution
        assert total_time < 600  # Should complete all within 10 minutes
        assert len(results) == len(tasks)
    
    @pytest.mark.asyncio
    async def test_memory_usage_during_execution(self, performance_team):
        """Test memory usage during task execution"""
        import psutil
        import os
        
        manager, registry, workspace = performance_team
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Execute task
        task = TestTaskBuilder.complex_task()
        result = await manager.execute_task(task)
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Validate result
        assert validate_task_result(result)
        
        # Memory usage should be reasonable (less than 500MB increase)
        assert memory_increase < 500
        
        # Memory increase should be positive (some memory usage expected)
        assert memory_increase > 0


@pytest.mark.integration
@pytest.mark.requires_api
class TestRobustnessIntegration:
    """Robustness tests with real LLM queries"""
    
    @pytest_asyncio.fixture
    async def robust_team(self):
        """Set up team for robustness testing"""
        skip_if_no_litellm_key()
        
        models = get_test_models()
        registry = AgentRegistry()
        
        with TempWorkspace() as workspace:
            create_test_files(workspace)
            
            manager = EngineeringManager(
                agent_id="robust_manager",
                model=models.get("manager", "gpt-3.5-turbo")
            )
            registry.register_agent(manager)
            
            claude_agent = ClaudeCodeAgent(
                agent_id="robust_claude_coder",
                working_directory=str(workspace),
                model=models.get("claude")
            )
            registry.register_agent(claude_agent)
            manager.register_agent(claude_agent)
            
            yield manager, registry, workspace
        
        await registry.shutdown_all_agents()
    
    @pytest.mark.asyncio
    async def test_malformed_task_handling(self, robust_team):
        """Test handling of malformed or problematic tasks"""
        manager, registry, workspace = robust_team
        
        # Test with minimal task information
        minimal_task = {
            "id": "minimal_task",
            "description": "Do something"
        }
        
        result = await manager.execute_task(minimal_task)
        
        # Should handle gracefully (may succeed or fail, but shouldn't crash)
        assert hasattr(result, 'status')
        assert hasattr(result, 'task_id')
        assert result.task_id == minimal_task["id"]
    
    @pytest.mark.asyncio
    async def test_empty_workspace_handling(self, robust_team):
        """Test handling tasks in empty workspace"""
        manager, registry, workspace = robust_team
        
        # Clear the workspace
        for item in workspace.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                import shutil
                shutil.rmtree(item)
        
        # Execute task in empty workspace
        task = TestTaskBuilder.simple_coding_task()
        result = await manager.execute_task(task)
        
        # Should handle empty workspace gracefully
        assert hasattr(result, 'status')
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_very_simple_task_handling(self, robust_team):
        """Test handling of very simple tasks"""
        manager, registry, workspace = robust_team
        
        simple_task = {
            "id": "very_simple_task",
            "description": "Print hello world",
            "complexity": 1
        }
        
        result = await manager.execute_task(simple_task)
        
        # Should handle simple tasks efficiently
        assert validate_task_result(result)
        assert result.execution_time < 60  # Should be quick for simple tasks
    
    @pytest.mark.asyncio
    async def test_task_with_special_characters(self, robust_team):
        """Test handling tasks with special characters and formatting"""
        manager, registry, workspace = robust_team
        
        special_task = {
            "id": "special_chars_task",
            "description": "Create a function that handles special characters: àáâãäå, émoji 🚀, and symbols like @#$%^&*()",
            "complexity": 3
        }
        
        result = await manager.execute_task(special_task)
        
        # Should handle special characters gracefully
        assert validate_task_result(result)
        assert result.task_id == special_task["id"]


@pytest.mark.integration
@pytest.mark.requires_api
class TestRealWorldScenarios:
    """Real-world scenario integration tests"""
    
    @pytest_asyncio.fixture
    async def scenario_team(self):
        """Set up team for real-world scenario testing"""
        skip_if_no_litellm_key()
        
        models = get_test_models()
        registry = AgentRegistry()
        
        with TempWorkspace() as workspace:
            # Create a realistic project structure
            (workspace / "src").mkdir()
            (workspace / "tests").mkdir()
            (workspace / "docs").mkdir()
            (workspace / "config").mkdir()
            
            # Add some existing files
            (workspace / "requirements.txt").write_text("flask>=2.0.0\nrequests>=2.25.0\n")
            (workspace / "README.md").write_text("# My Project\n\nA sample project.")
            (workspace / ".gitignore").write_text("__pycache__/\n*.pyc\n.env\n")
            
            manager = EngineeringManager(
                agent_id="scenario_manager",
                model=models.get("manager", "gpt-3.5-turbo")
            )
            registry.register_agent(manager)
            
            for i in range(2):
                agent_id = f"scenario_claude_coder_{i+1}"
                claude_agent = ClaudeCodeAgent(
                    agent_id=agent_id,
                    working_directory=str(workspace),
                    model=models.get("claude")
                )
                registry.register_agent(claude_agent)
                manager.register_agent(claude_agent)
            
            yield manager, registry, workspace
        
        await registry.shutdown_all_agents()
    
    @pytest.mark.asyncio
    async def test_web_api_development_scenario(self, scenario_team):
        """Test realistic web API development scenario"""
        manager, registry, workspace = scenario_team
        
        task = {
            "id": "web_api_scenario",
            "description": "Create a simple REST API using Flask with endpoints for managing a todo list. Include GET /todos, POST /todos, PUT /todos/<id>, and DELETE /todos/<id>. Add basic error handling and JSON responses.",
            "complexity": 7
        }
        
        result = await manager.execute_task(task)
        
        # Validate realistic development task
        assert validate_task_result(result)
        assert result.output["total_subtasks"] >= 2  # Should break into multiple parts
        assert result.execution_time > 20  # Realistic development takes time
        assert result.execution_time < 400  # But should complete reasonably
    
    @pytest.mark.asyncio
    async def test_code_refactoring_scenario(self, scenario_team):
        """Test code refactoring scenario"""
        manager, registry, workspace = scenario_team
        
        # Create some legacy code to refactor
        legacy_code = workspace / "src" / "legacy.py"
        legacy_code.write_text('''
# Legacy code that needs refactoring
def process_data(data):
    result = []
    for i in range(len(data)):
        if data[i] > 0:
            result.append(data[i] * 2)
        else:
            result.append(0)
    return result

def calculate_total(items):
    total = 0
    for item in items:
        total = total + item
    return total
''')
        
        task = {
            "id": "refactoring_scenario",
            "description": "Refactor the legacy.py file to use modern Python best practices: list comprehensions, type hints, proper docstrings, and error handling. Also add unit tests.",
            "complexity": 5
        }
        
        result = await manager.execute_task(task)
        
        # Validate refactoring task
        assert validate_task_result(result)
        assert result.execution_time > 15  # Refactoring takes analysis time
    
    @pytest.mark.asyncio
    async def test_documentation_generation_scenario(self, scenario_team):
        """Test documentation generation scenario"""
        manager, registry, workspace = scenario_team
        
        # Create some code that needs documentation
        code_file = workspace / "src" / "utils.py"
        code_file.write_text('''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def is_prime(num):
    if num < 2:
        return False
    for i in range(2, int(num**0.5) + 1):
        if num % i == 0:
            return False
    return True

class Calculator:
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
''')
        
        task = {
            "id": "documentation_scenario",
            "description": "Generate comprehensive documentation for the utils.py file including docstrings, type hints, usage examples, and a markdown documentation file explaining the module.",
            "complexity": 4
        }
        
        result = await manager.execute_task(task)
        
        # Validate documentation task
        assert validate_task_result(result)
        assert result.execution_time > 10  # Documentation requires analysis
