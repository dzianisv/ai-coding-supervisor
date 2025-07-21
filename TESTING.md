# Testing Guide - Multi-Agent Coding Tool

This document provides comprehensive information about testing the multi-agent coding tool, including both unit tests and integration tests with real LLM queries.

## Overview

The testing suite includes:
- **Unit Tests**: Fast tests that don't require API keys
- **Integration Tests**: Real LLM query tests that validate end-to-end functionality
- **Performance Tests**: Tests that measure execution time and resource usage
- **CLI Tests**: Tests for command-line interface functionality

## Test Structure

```
tests/
├── __init__.py
├── test_base_agent.py           # Unit tests for base agent
├── test_utils.py                # Testing utilities and helpers
├── test_integration_manager.py  # Integration tests for Engineering Manager
├── test_integration_cli.py      # Integration tests for CLI interface
└── test_integration_performance.py  # Performance and stress tests
```

## Prerequisites

### Dependencies
Install testing dependencies:
```bash
pip install -r requirements.txt
```

Required packages:
- `pytest>=7.0.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `psutil>=5.9.0` - System resource monitoring

### API Keys (for Integration Tests)
Integration tests require real LLM API access. Set one or both:

```bash
# For OpenAI models (GPT-3.5, GPT-4)
export OPENAI_API_KEY="your-openai-api-key"

# For Anthropic models (Claude)
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

⚠️ **Cost Warning**: Integration tests make real API calls and will incur costs!

## Running Tests

### Quick Test Commands

#### Unit Tests Only (No API Keys Required)
```bash
# Run fast unit tests
python -m pytest tests/test_base_agent.py -v

# Run all unit tests
python -m pytest -m "unit" -v
```

#### Integration Tests (Requires API Keys)
```bash
# Check API key status and run integration tests
python run_integration_tests.py

# Run specific integration test categories
python run_integration_tests.py --fast      # Fast integration tests only
python run_integration_tests.py --cli       # CLI tests only
python run_integration_tests.py --performance  # Performance tests only

# Auto-confirm execution (for CI/CD)
python run_integration_tests.py --yes
```

#### All Tests
```bash
# Run everything (unit + integration)
python -m pytest -v
```

### Advanced Test Options

#### Test Selection by Markers
```bash
# Integration tests only
python -m pytest -m "integration" -v

# Tests that require API keys
python -m pytest -m "requires_api" -v

# Slow tests (performance, stress tests)
python -m pytest -m "slow" -v

# Fast tests only
python -m pytest -m "not slow" -v
```

#### Specific Test Classes
```bash
# Engineering Manager integration tests
python -m pytest tests/test_integration_manager.py::TestEngineeringManagerIntegration -v

# CLI integration tests
python -m pytest tests/test_integration_cli.py::TestCLIIntegration -v

# Performance tests
python -m pytest tests/test_integration_performance.py::TestPerformanceIntegration -v
```

#### Test Configuration Options
```bash
# Stop on first failure
python -m pytest -x

# Maximum number of failures before stopping
python -m pytest --maxfail=3

# Verbose output with full tracebacks
python -m pytest -v --tb=long

# Run tests in parallel (if pytest-xdist installed)
python -m pytest -n auto
```

## Test Categories

### Unit Tests
- **Location**: `tests/test_base_agent.py`
- **Purpose**: Test individual components without external dependencies
- **Speed**: Fast (< 5 seconds)
- **Requirements**: None (no API keys needed)

**Example**:
```bash
python -m pytest tests/test_base_agent.py::test_agent_initialization -v
```

### Integration Tests - Engineering Manager
- **Location**: `tests/test_integration_manager.py`
- **Purpose**: Test Engineering Manager with real LLM queries
- **Speed**: Medium (30-180 seconds per test)
- **Requirements**: API keys

**Key Tests**:
- `test_task_decomposition_real_llm`: Tests task breakdown with real LLM
- `test_work_review_real_llm`: Tests code review functionality
- `test_simple_task_execution_real_llm`: End-to-end task execution
- `test_team_status_and_coordination`: Team management functionality

### Integration Tests - CLI Interface
- **Location**: `tests/test_integration_cli.py`
- **Purpose**: Test command-line interface with real scenarios
- **Speed**: Medium to Slow (60-300 seconds per test)
- **Requirements**: API keys

**Key Tests**:
- `test_cli_execute_simple_task`: CLI task execution
- `test_project_enhancement_workflow`: Real project enhancement
- `test_code_review_workflow`: CLI-driven code review
- `test_multi_agent_coordination_via_cli`: Multi-agent CLI coordination

### Performance Tests
- **Location**: `tests/test_integration_performance.py`
- **Purpose**: Measure performance, timing, and resource usage
- **Speed**: Slow (120-600 seconds per test)
- **Requirements**: API keys

**Key Tests**:
- `test_task_execution_timing`: Execution time measurement
- `test_multiple_agents_coordination_performance`: Multi-agent performance
- `test_concurrent_task_handling`: Stress testing
- `test_memory_usage_during_execution`: Resource usage monitoring

## Test Utilities

### `test_utils.py` Helper Functions

#### API Key Management
```python
from tests.test_utils import check_api_keys, skip_if_no_api_keys

# Check available API keys
keys = check_api_keys()
print(f"OpenAI: {keys['openai']}, Anthropic: {keys['anthropic']}")

# Skip test if no API keys
@pytest.mark.integration
def test_with_llm():
    skip_if_no_api_keys()  # Will skip if no keys available
    # ... test code
```

#### Temporary Workspace
```python
from tests.test_utils import TempWorkspace, create_test_files

def test_with_workspace():
    with TempWorkspace() as workspace:
        files = create_test_files(workspace)  # Creates sample files
        # ... test code using workspace
        # Workspace is automatically cleaned up
```

#### Task Builders
```python
from tests.test_utils import TestTaskBuilder

# Pre-built test tasks
simple_task = TestTaskBuilder.simple_coding_task()
complex_task = TestTaskBuilder.complex_task()
review_task = TestTaskBuilder.review_task()
```

## Test Configuration

### pytest.ini Configuration
```ini
[tool:pytest]
testpaths = tests
asyncio_mode = auto
markers =
    integration: integration tests (may be slow)
    unit: unit tests (fast)
    requires_api: tests requiring API keys
    slow: slow tests (performance, stress)
addopts = -v --tb=short
```

### Environment Variables
```bash
# Test-specific model configuration
export TEAM_DEFAULT_MODEL="gpt-3.5-turbo"  # Cheaper for testing
export TEAM_CLAUDE_MODEL="claude-3-haiku-20240307"  # Cheaper Claude model

# Test timeouts
export TEAM_MAX_TASK_TIME="300"  # 5 minutes max per task
export TEAM_RETRY_ATTEMPTS="2"   # Fewer retries for faster tests
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Integration Tests
on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: python -m pytest tests/test_base_agent.py -v
      - name: Run fast integration tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: python run_integration_tests.py --fast --yes
        if: env.OPENAI_API_KEY != ''
```

## Troubleshooting

### Common Issues

#### 1. API Key Not Found
```
❌ No API keys found!
```
**Solution**: Set environment variables:
```bash
export OPENAI_API_KEY="your-key"
# or
export ANTHROPIC_API_KEY="your-key"
```

#### 2. Import Errors
```
ModuleNotFoundError: No module named 'agents'
```
**Solution**: Run tests from project root directory:
```bash
cd /path/to/ai-coding-supervisor
python -m pytest tests/
```

#### 3. Async Test Warnings
```
PytestDeprecationWarning: asyncio_default_fixture_loop_scope is unset
```
**Solution**: This is a warning, not an error. Tests will still run correctly.

#### 4. Test Timeouts
```
Test timed out after 300 seconds
```
**Solution**: 
- Check API key validity
- Increase timeout in test configuration
- Use cheaper/faster models for testing

#### 5. Rate Limiting
```
RateLimitError: Too many requests
```
**Solution**:
- Add delays between tests
- Use different API keys for parallel testing
- Run tests sequentially: `python -m pytest --maxfail=1`

### Debug Mode
Enable verbose logging for debugging:
```bash
# Enable debug logging
export TEAM_LOG_LEVEL="DEBUG"

# Run single test with full output
python -m pytest tests/test_integration_manager.py::TestEngineeringManagerIntegration::test_task_decomposition_real_llm -v -s --tb=long
```

### Performance Monitoring
Monitor test performance:
```bash
# Run with timing information
python -m pytest --durations=10

# Memory usage monitoring (requires pytest-monitor)
python -m pytest --monitor
```

## Best Practices

### Writing Integration Tests
1. **Use real API calls** - Don't mock LLM responses
2. **Handle failures gracefully** - LLM responses can be unpredictable
3. **Set reasonable timeouts** - Allow enough time for real processing
4. **Use cheaper models** - GPT-3.5-turbo, Claude Haiku for cost efficiency
5. **Clean up resources** - Use fixtures for proper cleanup

### Test Organization
1. **Mark tests appropriately** - Use `@pytest.mark.integration`, `@pytest.mark.slow`
2. **Group related tests** - Use test classes for logical grouping
3. **Use descriptive names** - Test names should explain what they validate
4. **Document complex tests** - Add docstrings explaining test scenarios

### Cost Management
1. **Use test runner** - `run_integration_tests.py` provides cost warnings
2. **Select test subsets** - Use `--fast` for quick validation
3. **Monitor usage** - Track API costs during test development
4. **Use cheaper models** - Configure test-specific model preferences

## Example Test Run

```bash
$ python run_integration_tests.py --fast

🧪 Multi-Agent Coding Tool - Integration Test Runner
============================================================
API Key Status:
  OpenAI: ✅
  Anthropic: ❌

🚀 Running integration tests with real LLM queries...
⚠️  Note: These tests will make actual API calls and may incur costs.

Proceed with integration tests? (y/N): y

Running fast integration tests...
Command: python -m pytest -v -m integration and not slow tests/test_integration_manager.py::TestEngineeringManagerIntegration::test_task_decomposition_real_llm tests/test_integration_manager.py::TestEngineeringManagerIntegration::test_work_review_real_llm tests/test_integration_cli.py::TestCLIIntegration::test_cli_help_commands
------------------------------------------------------------

========================= test session starts =========================
collected 3 items

tests/test_integration_manager.py::TestEngineeringManagerIntegration::test_task_decomposition_real_llm PASSED [33%]
tests/test_integration_manager.py::TestEngineeringManagerIntegration::test_work_review_real_llm PASSED [66%]
tests/test_integration_cli.py::TestCLIIntegration::test_cli_help_commands PASSED [100%]

========================= 3 passed in 45.23s =========================

✅ Integration tests completed successfully!
```
