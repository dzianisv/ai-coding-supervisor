"""
Test utilities for integration tests
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional


def check_api_keys() -> Dict[str, bool]:
    """Check which API keys are available"""
    return {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "litellm": bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
    }


def skip_if_no_api_keys():
    """Skip test if no API keys are available"""
    keys = check_api_keys()
    if not any(keys.values()):
        pytest.skip("No API keys available for integration testing")


def skip_if_no_litellm_key():
    """Skip test if no LiteLLM compatible API key is available"""
    if not check_api_keys()["litellm"]:
        pytest.skip("No LiteLLM compatible API key available")


class TempWorkspace:
    """Context manager for temporary workspace"""
    
    def __init__(self, prefix: str = "test_workspace_"):
        self.prefix = prefix
        self.temp_dir: Optional[Path] = None
        
    def __enter__(self) -> Path:
        self.temp_dir = Path(tempfile.mkdtemp(prefix=self.prefix))
        return self.temp_dir
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


def create_test_files(workspace: Path) -> Dict[str, Path]:
    """Create test files in workspace for testing"""
    files = {}
    
    # Create a simple Python file
    python_file = workspace / "test_module.py"
    python_file.write_text('''
def hello_world():
    """Simple hello world function"""
    return "Hello, World!"

def add_numbers(a, b):
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    print(hello_world())
''')
    files["python"] = python_file
    
    # Create a requirements file
    req_file = workspace / "requirements.txt"
    req_file.write_text("requests>=2.25.0\nflask>=2.0.0\n")
    files["requirements"] = req_file
    
    # Create a README
    readme_file = workspace / "README.md"
    readme_file.write_text('''# Test Project

This is a test project for integration testing.

## Features
- Simple Python module
- Basic functionality

## Usage
```python
from test_module import hello_world
print(hello_world())
```
''')
    files["readme"] = readme_file
    
    return files


def validate_task_result(result, expected_status: str = "completed") -> bool:
    """Validate task result structure"""
    if not hasattr(result, 'status'):
        return False
    
    if result.status.value != expected_status:
        return False
        
    if not hasattr(result, 'output'):
        return False
        
    return True


def get_test_models() -> Dict[str, str]:
    """Get test models based on available API keys"""
    keys = check_api_keys()
    models = {}
    
    if keys["openai"]:
        models["manager"] = "gpt-3.5-turbo"  # Use cheaper model for testing
        models["claude"] = None
    elif keys["anthropic"]:
        models["manager"] = "claude-3-haiku-20240307"  # Use cheaper Claude model
        models["claude"] = "claude-3-haiku-20240307"
    
    return models


class TestTaskBuilder:
    """Helper to build test tasks"""
    
    @staticmethod
    def simple_coding_task() -> Dict[str, Any]:
        """Create a simple coding task"""
        return {
            "id": "test_simple_task",
            "description": "Create a Python function that calculates the factorial of a number and write a simple test for it",
            "complexity": 3,
            "expected_deliverables": ["factorial function", "test function"]
        }
    
    @staticmethod
    def file_modification_task() -> Dict[str, Any]:
        """Create a task that modifies existing files"""
        return {
            "id": "test_file_mod_task", 
            "description": "Add a new function to test_module.py that multiplies two numbers and update the README to document it",
            "complexity": 2,
            "expected_deliverables": ["multiply function", "updated README"]
        }
    
    @staticmethod
    def complex_task() -> Dict[str, Any]:
        """Create a more complex task"""
        return {
            "id": "test_complex_task",
            "description": "Create a simple Flask web application with two endpoints: /hello that returns a greeting and /calculate that accepts two numbers and returns their sum. Include error handling and basic tests.",
            "complexity": 6,
            "expected_deliverables": ["Flask app", "endpoints", "error handling", "tests"]
        }
    
    @staticmethod
    def review_task() -> Dict[str, Any]:
        """Create a code review task"""
        return {
            "id": "test_review_task",
            "description": "Review the existing code in test_module.py and suggest improvements for code quality, documentation, and best practices",
            "complexity": 4,
            "expected_deliverables": ["code review", "improvement suggestions"]
        }
