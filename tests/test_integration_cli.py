"""
Integration tests for CLI interface with real LLM queries
"""

import asyncio
import pytest
import os
import sys
import tempfile
import subprocess
import json
from pathlib import Path
from click.testing import CliRunner

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.main_cli import main_cli
from tests.test_utils import (
    skip_if_no_litellm_key,
    TempWorkspace,
    create_test_files,
    get_test_models
)


@pytest.mark.integration
@pytest.mark.requires_api
class TestCLIIntegration:
    """Integration tests for CLI with real LLM queries"""
    
    @pytest.fixture
    def cli_runner(self):
        """Create CLI runner"""
        return CliRunner()
    
    @pytest.fixture
    def temp_config(self):
        """Create temporary config file"""
        skip_if_no_litellm_key()
        
        models = get_test_models()
        config = {
            "test_model": models.get("manager", "gpt-4.1-nano"),
            "prod_model": models.get("prod_manager", "gpt-4o-2024-05-13"),
            "claude_model": models.get("claude"),
            "default_agents": 1,
            "max_task_time": 300,  # 5 minutes for testing
            "retry_attempts": 2,
            "log_level": "INFO",
            "production_mode": False  # Test mode by default
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f, indent=2)
            config_path = f.name
        
        yield config_path
        
        # Cleanup
        os.unlink(config_path)
    
    def test_cli_help_commands(self, cli_runner):
        """Test CLI help commands work"""
        # Test main help
        result = cli_runner.invoke(main_cli, ['--help'])
        assert result.exit_code == 0
        assert "Multi-Agent Coding Tool" in result.output
        
        # Test subcommand help
        result = cli_runner.invoke(main_cli, ['execute', '--help'])
        assert result.exit_code == 0
        assert "Execute a single task" in result.output
        
        result = cli_runner.invoke(main_cli, ['start', '--help'])
        assert result.exit_code == 0
        assert "Start the multi-agent coding team" in result.output
    
    def test_cli_configure_command(self, cli_runner, temp_config):
        """Test CLI configure command"""
        # Test configure help
        result = cli_runner.invoke(main_cli, ['configure', '--help'])
        assert result.exit_code == 0
        
        # Test configure with non-interactive mode
        result = cli_runner.invoke(main_cli, [
            'configure',
            '--config-file', temp_config,
            '--non-interactive',
            '--default-model', 'gpt-3.5-turbo',
            '--claude-model', 'claude-3-haiku-20240307',
            '--default-agents', '2',
            '--working-dir', os.getcwd()
        ])
        
        # Should complete without error
        assert result.exit_code == 0
        
        # Verify the config file was created with expected content
        import json
        with open(temp_config, 'r') as f:
            config = json.load(f)
            assert config['default_model'] == 'gpt-3.5-turbo'
            assert config['claude_model'] == 'claude-3-haiku-20240307'
            assert config['default_agents'] == 2
    
    def test_cli_execute_simple_task(self, cli_runner, temp_config, monkeypatch):
        """Test CLI execute command with simple task"""
        skip_if_no_litellm_key()
        
        # Mock the asyncio.run call to avoid event loop issues in tests
        original_run = asyncio.run
        
        def mock_asyncio_run(coro):
            # Create a new event loop for the test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        
        # Apply the mock
        monkeypatch.setattr(asyncio, 'run', mock_asyncio_run)
        
        with TempWorkspace() as workspace:
            create_test_files(workspace)
            
            # Create output file for results
            output_file = workspace / "results.json"
            
            try:
                # Execute simple task via CLI
                result = cli_runner.invoke(main_cli, [
                    'execute',
                    'Create a simple Python function that returns the square of a number',
                    '--working-dir', str(workspace),
                    '--agents', '1',
                    '--output', str(output_file)
                ])
                
                # Check command completed
                assert result.exit_code == 0, f"Command failed with error: {result.output}"
                
                # Check output file was created
                assert output_file.exists(), f"Output file {output_file} was not created"
                
                # Check output file has valid JSON
                import json
                with open(output_file, 'r') as f:
                    result_data = json.load(f)
                    
                # Check result structure
                assert 'status' in result_data, "Result data is missing 'status' field"
                assert 'result' in result_data, "Result data is missing 'result' field"
                assert 'artifacts' in result_data, "Result data is missing 'artifacts' field"
                
            finally:
                # Clean up - restore original asyncio.run
                monkeypatch.setattr(asyncio, 'run', original_run)
    
    def test_cli_execute_with_different_models(self, cli_runner):
        """Test CLI execute with different model configurations"""
        skip_if_no_litellm_key()
        
        models = get_test_models()
        
        with TempWorkspace() as workspace:
            create_test_files(workspace)
            
            # Test with specific model
            result = cli_runner.invoke(main_cli, [
                'execute',
                'Add a comment to the existing Python file explaining what it does',
                '--working-dir', str(workspace),
                '--model', models.get("manager", "gpt-3.5-turbo"),
                '--agents', '1'
            ])
            
            # Should complete successfully
            assert result.exit_code == 0
            assert "Task completed" in result.output or "Task failed" in result.output


@pytest.mark.integration
@pytest.mark.requires_api
class TestCLIEndToEnd:
    """End-to-end CLI integration tests"""
    
    @pytest.fixture
    def isolated_workspace(self):
        """Create isolated workspace for testing"""
        with TempWorkspace() as workspace:
            # Create a more complex project structure
            (workspace / "src").mkdir()
            (workspace / "tests").mkdir()
            (workspace / "docs").mkdir()
            
            # Create main module
            main_file = workspace / "src" / "calculator.py"
            main_file.write_text('''
"""Simple calculator module"""

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
''')
            
            # Create test file
            test_file = workspace / "tests" / "test_calculator.py"
            test_file.write_text('''
"""Tests for calculator module"""
import sys
sys.path.append('../src')

from calculator import add, subtract

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2
''')
            
            # Create project README
            readme = workspace / "README.md"
            readme.write_text('''# Calculator Project

A simple calculator implementation.

## Features
- Addition
- Subtraction

## Usage
```python
from calculator import add, subtract
result = add(5, 3)
```
''')
            
            yield workspace
    
    def test_project_enhancement_workflow(self, isolated_workspace):
        """Test enhancing an existing project via CLI"""
        skip_if_no_litellm_key()
        
        runner = CliRunner()
        
        # Task: Enhance the calculator project
        task_description = (
            "Enhance the calculator project by adding multiplication and division functions "
            "to the calculator.py module, update the tests to include these new functions, "
            "and update the README to document the new features."
        )
        
        result = runner.invoke(main_cli, [
            'execute',
            task_description,
            '--working-dir', str(isolated_workspace),
            '--agents', '1'
        ])
        
        # Verify command completed
        assert result.exit_code == 0
        
        # Check that the workflow executed
        assert "Executing task" in result.output or "Task" in result.output
    
    def test_code_review_workflow(self, isolated_workspace):
        """Test code review workflow via CLI"""
        skip_if_no_litellm_key()
        
        runner = CliRunner()
        
        # Task: Review existing code
        task_description = (
            "Review the existing calculator code for code quality, documentation, "
            "and suggest improvements. Focus on error handling, type hints, and docstrings."
        )
        
        result = runner.invoke(main_cli, [
            'execute',
            task_description,
            '--working-dir', str(isolated_workspace),
            '--agents', '1'
        ])
        
        # Verify command completed
        assert result.exit_code == 0
    
    @pytest.mark.slow
    def test_multi_agent_coordination_via_cli(self, isolated_workspace):
        """Test multi-agent coordination through CLI"""
        skip_if_no_litellm_key()
        
        runner = CliRunner()
        
        # Complex task that should require multiple subtasks
        task_description = (
            "Create a comprehensive web API for the calculator project using Flask. "
            "Include endpoints for all mathematical operations, proper error handling, "
            "input validation, API documentation, and a simple HTML interface for testing. "
            "Also create unit tests for the API endpoints."
        )
        
        result = runner.invoke(main_cli, [
            'execute',
            task_description,
            '--working-dir', str(isolated_workspace),
            '--agents', '2',  # Use multiple agents
            '--model', get_test_models().get("manager", "gpt-3.5-turbo")
        ])
        
        # Verify command completed (may succeed or fail, but should not crash)
        assert result.exit_code in [0, 1]  # Allow for task failure but not system crash


@pytest.mark.integration
@pytest.mark.requires_api 
class TestCLIErrorHandling:
    """Test CLI error handling with real scenarios"""
    
    def test_cli_with_invalid_working_directory(self):
        """Test CLI behavior with invalid working directory"""
        runner = CliRunner()
        
        result = runner.invoke(main_cli, [
            'execute',
            'Simple task',
            '--working-dir', '/nonexistent/directory'
        ])
        
        # Should handle error gracefully
        assert result.exit_code != 0
        assert "does not exist" in result.output
    
    def test_cli_with_no_api_keys(self, monkeypatch):
        """Test CLI behavior when no API keys are available"""
        # Temporarily remove API keys
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        runner = CliRunner()
        
        with TempWorkspace() as workspace:
            result = runner.invoke(main_cli, [
                'execute',
                'Simple task',
                '--working-dir', str(workspace)
            ])
            
            # Should handle missing API keys gracefully
            # (May succeed with mock responses or fail gracefully)
            assert result.exit_code in [0, 1]
    
    def test_cli_status_command(self):
        """Test CLI status command"""
        runner = CliRunner()
        
        result = runner.invoke(main_cli, ['status'])
        
        # Should complete without error
        assert result.exit_code == 0
        assert "not yet implemented" in result.output or "Status" in result.output
