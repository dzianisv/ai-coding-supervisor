"""
Integration tests for Engineering Manager with real LLM queries
"""

import asyncio
import json
import os
import pytest
import pytest_asyncio
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from rich.console import Console

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Agent imports
from agents.engineering_manager import EngineeringManager
from agents.agent_registry import AgentRegistry
from agents.claude_code_agent import ClaudeCodeAgent
from agents.base_agent import AgentStatus

# Test utilities
from tests.test_utils import (
    TempWorkspace,
    TestTaskBuilder,
    create_test_files,
    validate_task_result,
    get_test_models,
    skip_if_no_litellm_key,
)


@pytest.mark.integration
@pytest.mark.requires_api
class TestEngineeringManagerIntegration:
    """Integration tests for Engineering Manager using real LLM queries"""
    
    @pytest_asyncio.fixture
    async def manager_with_agents(self):
        """Create manager with coding agents"""
        skip_if_no_litellm_key()
        
        models = get_test_models()
        registry = AgentRegistry()
        
        # Create Engineering Manager with test model
        manager = EngineeringManager(
            agent_id="test_manager",
            production=False  # Ensures test model is used
        )
        registry.register_agent(manager)
        
        # Create coding agents
        with TempWorkspace() as workspace:
            claude_agent = ClaudeCodeAgent(
                agent_id="test_claude_coder",
                working_directory=str(workspace),
                model=models.get("claude")
            )
            registry.register_agent(claude_agent)
            manager.register_agent(claude_agent)
            
            yield manager, registry, workspace
        
        # Cleanup
        await registry.shutdown_all_agents()
    
    @pytest.mark.asyncio
    async def test_os_import_in_context(self):
        """Test that os module can be imported in the test class context"""
        import os
        import sys
        
        # Check if os module is in sys.modules
        assert 'os' in sys.modules, "os module not found in sys.modules"
        
        # Check if we can use os functions
        assert os.getenv('PATH') is not None, "os.getenv returned None"
        
        # Check if we can access environment variables
        assert 'PATH' in os.environ, "PATH not found in os.environ"
        
        print("os module is working correctly in test context")
    
    @pytest.mark.asyncio
    async def test_task_decomposition_real_llm(self, manager_with_agents):
        """Test task decomposition with real LLM"""
        print("\n=== Starting test_task_decomposition_real_llm ===")
        
        # Debug: Check if os is already in sys.modules
        import sys
        print(f"sys.modules has 'os': {'os' in sys.modules}")
        
        # Try different ways to import os
        try:
            import os
            print("Direct import of os succeeded")
        except ImportError as e:
            print(f"Direct import of os failed: {e}")
        
        try:
            import importlib
            os = importlib.import_module('os')
            print("importlib.import_module('os') succeeded")
        except ImportError as e:
            print(f"importlib.import_module('os') failed: {e}")
        
        # Get the manager and other fixtures
        manager, registry, workspace = manager_with_agents
        
        # Create test files
        create_test_files(workspace)
        
        # Test simple task decomposition
        task = TestTaskBuilder.simple_coding_task()
        
        # Get available agents info
        available_agents = [
            {
                "id": agent.agent_id,
                "name": agent.name,
                "capabilities": [cap.value for cap in agent.capabilities]
            }
            for agent in registry.get_all_agents()
            if agent.agent_id != manager.agent_id
        ]
        
        # Verify the real model is being used
        expected_model = os.getenv("TEST_MODEL", "gpt-4.1-nano")
        assert manager.model == expected_model, f"Expected model {expected_model}, but got {manager.model}"
        
        # Test decomposition
        subtasks = await manager.task_decomposer.decompose_task(
            task["description"], 
            available_agents
        )
        
        # Validate decomposition
        assert isinstance(subtasks, list)
        assert len(subtasks) > 0
        
        # Verify model was actually used (check that we got real LLM response)
        assert all("subtask_id" in subtask for subtask in subtasks), "Real LLM should generate proper subtask structure"
        
        # Check subtask structure
        for subtask in subtasks:
            assert "subtask_id" in subtask
            assert "title" in subtask
            assert "description" in subtask
            assert "required_capabilities" in subtask
            assert isinstance(subtask["required_capabilities"], list)
    
    @pytest.mark.asyncio
    async def test_work_review_real_llm(self, manager_with_agents):
        """Test work review with real LLM"""
        # Use importlib to ensure the os module is properly imported
        import importlib
        os = importlib.import_module('os')
        manager, registry, workspace = manager_with_agents
        
        # Create a mock task result
        from agents.base_agent import TaskResult
        
        subtask = {
            "subtask_id": "test_subtask_001",
            "title": "Create factorial function",
            "description": "Create a Python function that calculates factorial",
            "deliverables": ["factorial function", "test cases"]
        }
        
        mock_result = TaskResult(
            task_id="test_subtask_001",
            agent_id="test_claude_coder",
            status=AgentStatus.COMPLETED,
            output={
                "response_type": "claude_code",
                "success": True,
                "summary": "Created factorial function with tests",
                "files_modified": ["factorial.py", "test_factorial.py"]
            },
            artifacts=["factorial.py", "test_factorial.py"],
            execution_time=45.2
        )
        
        # Verify the real model is being used
        expected_model = os.getenv("TEST_MODEL", "gpt-4.1-nano")
        assert manager.model == expected_model, f"Expected model {expected_model}, but got {manager.model}"
        assert manager.work_reviewer.model == expected_model, f"Work reviewer should use {expected_model}, but got {manager.work_reviewer.model}"
        
        # Test work review
        review = await manager.work_reviewer.review_work(subtask, mock_result)
        
        # Validate review structure
        assert isinstance(review, dict)
        assert "quality_score" in review
        assert "completion_status" in review
        assert "feedback" in review
        assert "approval" in review
        
        # Validate review content
        assert isinstance(review["quality_score"], (int, float))
        assert 1 <= review["quality_score"] <= 10
        assert review["completion_status"] in ["complete", "needs_revision", "failed"]
        assert isinstance(review["approval"], bool)
    
    @pytest.mark.asyncio
    async def test_simple_task_execution_real_llm(self, manager_with_agents):
        """Test simple task execution end-to-end with real LLM"""
        # Use importlib to ensure the os module is properly imported
        import importlib
        os = importlib.import_module('os')
        manager, registry, workspace = manager_with_agents
        
        # Create test files
        create_test_files(workspace)
        
        # Execute simple task
        task = TestTaskBuilder.simple_coding_task()
        
        # This will use real LLM calls
        result = await manager.execute_task(task)
        
        # Validate result
        assert validate_task_result(result)
        assert result.agent_id == manager.agent_id
        assert result.task_id == task["id"]
        
        # Check output structure
        assert "subtasks_completed" in result.output
        assert "total_subtasks" in result.output
        assert result.output["subtasks_completed"] >= 0
        assert result.output["total_subtasks"] >= 1
        
        # Verify execution time is reasonable
        assert result.execution_time > 0
        assert result.execution_time < 300  # Should complete within 5 minutes
    
    @pytest.mark.asyncio
    async def test_team_status_and_coordination(self, manager_with_agents):
        """Test team status and coordination functionality"""
        # Use importlib to ensure the os module is properly imported
        import importlib
        os = importlib.import_module('os')
        manager, registry, workspace = manager_with_agents
        
        # Check initial team status
        team_status = manager.get_team_status()
        
        assert "team_status" in team_status
        assert "active_subtasks" in team_status
        assert "completed_subtasks" in team_status
        
        # Verify all agents are registered
        assert len(team_status["team_status"]) >= 1  # At least the claude agent
        
        # Check registry status
        registry_status = registry.get_registry_status()
        assert registry_status["total_agents"] >= 2  # Manager + at least 1 coding agent
        
        # Verify capabilities are properly distributed
        capability_dist = registry_status["capability_distribution"]
        assert capability_dist["code_generation"] >= 1
        assert capability_dist["task_management"] >= 1


@pytest.mark.integration
@pytest.mark.requires_api
class TestClaudeCodeAgentIntegration:
    """Integration tests for Claude Code Agent with real queries"""
    
    @pytest_asyncio.fixture
    async def claude_agent(self):
        """Create Claude coding agent"""
        skip_if_no_litellm_key()
        
        with TempWorkspace() as workspace:
            create_test_files(workspace)
            
            models = get_test_models()
            agent = ClaudeCodeAgent(
                agent_id="test_claude_integration",
                working_directory=str(workspace),
                model=models.get("claude")
            )
            
            yield agent, workspace
            
            await agent.shutdown()
    
    @pytest.mark.asyncio
    async def test_code_generation_real_claude(self, claude_agent):
        """Test code generation with real Claude queries"""
        agent, workspace = claude_agent
        
        task = {
            "subtask_id": "test_codegen_001",
            "title": "Create utility functions",
            "description": "Create a Python module with utility functions for string manipulation: reverse_string, count_vowels, and capitalize_words",
            "deliverables": ["utility module", "function implementations"],
            "estimated_complexity": 3
        }
        
        # Execute task with real Claude
        result = await agent.execute_task(task)
        
        # Validate result
        assert validate_task_result(result)
        assert result.agent_id == agent.agent_id
        assert result.task_id == task["subtask_id"]
        
        # Check output structure
        assert result.output["response_type"] == "claude_code"
        assert result.output["success"] is True
        assert len(result.output["messages"]) > 0
        
        # Verify execution metrics
        assert result.execution_time > 0
        assert result.execution_time < 180  # Should complete within 3 minutes
    
    @pytest.mark.asyncio
    async def test_code_review_real_claude(self, claude_agent):
        """Test code review with real Claude queries"""
        agent, workspace = claude_agent
        
        # Create some code to review
        code_file = workspace / "review_target.py"
        code_file.write_text('''
def calculate(x, y):
    return x + y

def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result

# Missing docstrings and error handling
def divide(a, b):
    return a / b
''')
        
        work_item = {
            "type": "code_review",
            "file_path": str(code_file),
            "code_content": code_file.read_text(),
            "review_focus": ["code quality", "documentation", "error handling"]
        }
        
        # Perform review with real Claude
        review_result = await agent.review_work(work_item)
        
        # Validate review
        assert "reviewer" in review_result
        assert review_result["reviewer"] == agent.agent_id
        assert "review_type" in review_result
        assert review_result["review_type"] == "code_review"
        assert "review_output" in review_result
        
        # Check review content
        review_output = review_result["review_output"]
        assert review_output["success"] is True
        assert len(review_output["messages"]) > 0


@pytest.mark.integration
@pytest.mark.requires_api
class TestEndToEndWorkflow:
    """End-to-end workflow integration tests"""
    
    @pytest_asyncio.fixture
    async def full_team_setup(self):
        """Set up complete team for end-to-end testing"""
        skip_if_no_litellm_key()
        
        models = get_test_models()
        registry = AgentRegistry()
        
        with TempWorkspace() as workspace:
            create_test_files(workspace)
            
            # Create Engineering Manager
            manager = EngineeringManager(
                agent_id="e2e_manager",
                model=models.get("manager", "gpt-3.5-turbo")
            )
            registry.register_agent(manager)
            
            # Create multiple coding agents
            for i in range(2):
                agent_id = f"e2e_claude_coder_{i+1}"
                claude_agent = ClaudeCodeAgent(
                    agent_id=agent_id,
                    working_directory=str(workspace),
                    model=models.get("claude")
                )
                registry.register_agent(claude_agent)
                manager.register_agent(claude_agent)
            
            yield manager, registry, workspace
        
        # Cleanup
        await registry.shutdown_all_agents()
    
    @pytest.mark.asyncio
    async def test_complete_workflow_simple_task(self, full_team_setup):
        """Test complete workflow with a simple task"""
        manager, registry, workspace = full_team_setup
        
        task = TestTaskBuilder.simple_coding_task()
        
        # Execute complete workflow
        result = await manager.execute_task(task)
        
        # Validate successful completion
        assert validate_task_result(result, "completed")
        assert result.output["subtasks_completed"] > 0
        assert result.output["total_subtasks"] > 0
        
        # Check that some work was actually done
        assert result.execution_time > 10  # Should take some time for real work
        
        # Verify team coordination worked
        team_status = manager.get_team_status()
        assert team_status["completed_subtasks"] > 0
    
    @pytest.mark.asyncio
    async def test_complete_workflow_file_modification(self, full_team_setup):
        """Test complete workflow with file modification task"""
        manager, registry, workspace = full_team_setup
        
        task = TestTaskBuilder.file_modification_task()
        
        # Execute workflow
        result = await manager.execute_task(task)
        
        # Validate completion
        assert validate_task_result(result)
        
        # Check if files were potentially modified
        # (We can't guarantee specific file changes without mocking, 
        # but we can verify the workflow completed)
        assert result.execution_time > 0
        assert result.output["subtasks_completed"] >= 0
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complex_task_workflow(self, full_team_setup):
        """Test workflow with a more complex task (marked as slow)"""
        manager, registry, workspace = full_team_setup
        
        task = TestTaskBuilder.complex_task()
        
        # Execute complex workflow
        result = await manager.execute_task(task)
        
        # Validate result
        assert validate_task_result(result)
        
        # Complex tasks should create multiple subtasks
        assert result.output["total_subtasks"] >= 2
        
        # Should take reasonable time but not too long
        assert result.execution_time > 30  # Complex task should take some time
        assert result.execution_time < 600  # But not more than 10 minutes
        
        # Verify multiple agents were potentially used
        team_status = manager.get_team_status()
        assert len(team_status["team_status"]) >= 2  # Manager + coding agents
