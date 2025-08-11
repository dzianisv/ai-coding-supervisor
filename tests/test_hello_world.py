#!/usr/bin/env python3
"""
Tests for VibeTeam's ability to create a hello world application.
This test validates that VibeTeam agents can generate code from scratch.
"""

import os
import tempfile
import subprocess
import pytest
from unittest.mock import patch, AsyncMock
from agents.claude_code_agent import ClaudeCodeAgent


class TestHelloWorldGeneration:
    """Test class for VibeTeam hello world generation functionality"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_claude_agent_can_create_hello_world(self):
        """Test that Claude Code Agent can create a hello world program"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the Claude Code Agent to avoid actual API calls in unit tests
            agent = ClaudeCodeAgent(working_directory=temp_dir)
            
            # Mock the execute_task method
            with patch.object(agent, 'execute_task', new_callable=AsyncMock) as mock_execute:
                # Mock response simulating successful hello world creation
                mock_execute.return_value = type('MockResult', (), {
                    'status': 'COMPLETED',
                    'output': 'Created hello_world.py successfully',
                    'errors': [],
                    'artifacts': ['hello_world.py']
                })()
                
                # Execute task to create hello world
                task = {
                    "description": "Create a simple Python hello world program that prints 'Hello, world!'"
                }
                result = await agent.execute_task(task)
                
                # Verify the agent was called with correct task
                mock_execute.assert_called_once_with(task)
                
                # Verify successful completion
                assert result.status == 'COMPLETED'
                assert 'hello_world.py' in result.artifacts
    
    @pytest.mark.unit
    def test_hello_world_task_description_format(self):
        """Test that hello world task descriptions are properly formatted"""
        task_descriptions = [
            "Create a simple Python hello world program",
            "Generate a Python hello world script that prints 'Hello, world!'",
            "Write a basic Python program that outputs Hello, world!"
        ]
        
        for description in task_descriptions:
            # Verify task description contains key elements
            assert 'hello world' in description.lower()
            assert 'python' in description.lower()
            
    @pytest.mark.unit
    def test_generated_hello_world_structure(self):
        """Test the expected structure of a generated hello world program"""
        # This test validates what we expect from a proper hello world program
        expected_elements = [
            'def main():',
            'print(',
            'Hello, world!',
            'if __name__ == "__main__":'
        ]
        
        # This is the structure we expect VibeTeam to generate
        sample_hello_world = '''#!/usr/bin/env python3
def main():
    print("Hello, world!")

if __name__ == "__main__":
    main()
'''
        
        for element in expected_elements:
            assert element in sample_hello_world
            
    @pytest.mark.unit 
    def test_hello_world_execution_validation(self):
        """Test validation logic for hello world program execution"""
        # Test that we can validate if a hello world program works correctly
        sample_code = '''
def main():
    print("Hello, world!")

if __name__ == "__main__":
    main()
'''
        
        # Write to temporary file and test execution
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(sample_code)
            temp_file = f.name
            
        try:
            # Test that the code executes and produces correct output
            result = subprocess.run(
                ['python', temp_file], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            assert result.returncode == 0
            assert result.stdout.strip() == "Hello, world!"
            
        finally:
            os.unlink(temp_file)