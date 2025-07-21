#!/usr/bin/env python3
"""
Integration test runner with API key validation and selective test execution
"""

import os
import sys
import subprocess
from pathlib import Path


def check_api_keys():
    """Check which API keys are available"""
    keys = {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY"))
    }
    return keys


def main():
    """Run integration tests with appropriate configuration"""
    print("🧪 Multi-Agent Coding Tool - Integration Test Runner")
    print("=" * 60)
    
    # Check API keys
    keys = check_api_keys()
    print(f"API Key Status:")
    print(f"  OpenAI: {'✅' if keys['openai'] else '❌'}")
    print(f"  Anthropic: {'✅' if keys['anthropic'] else '❌'}")
    
    if not any(keys.values()):
        print("\n❌ No API keys found!")
        print("Please set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variables.")
        print("\nExample:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        return 1
    
    print(f"\n🚀 Running integration tests with real LLM queries...")
    print("⚠️  Note: These tests will make actual API calls and may incur costs.")
    
    # Confirm execution
    if len(sys.argv) > 1 and sys.argv[1] == "--yes":
        proceed = True
    else:
        response = input("\nProceed with integration tests? (y/N): ")
        proceed = response.lower().startswith('y')
    
    if not proceed:
        print("Integration tests cancelled.")
        return 0
    
    # Determine test selection based on arguments
    test_args = ["python", "-m", "pytest", "-v"]
    
    if "--fast" in sys.argv:
        # Run only fast integration tests
        test_args.extend([
            "-m", "integration and not slow",
            "tests/test_integration_manager.py::TestEngineeringManagerIntegration::test_task_decomposition_real_llm",
            "tests/test_integration_manager.py::TestEngineeringManagerIntegration::test_work_review_real_llm",
            "tests/test_integration_cli.py::TestCLIIntegration::test_cli_help_commands"
        ])
        print("Running fast integration tests...")
    elif "--performance" in sys.argv:
        # Run performance tests
        test_args.extend([
            "-m", "slow",
            "tests/test_integration_performance.py"
        ])
        print("Running performance tests...")
    elif "--cli" in sys.argv:
        # Run CLI tests only
        test_args.extend([
            "tests/test_integration_cli.py"
        ])
        print("Running CLI integration tests...")
    else:
        # Run all integration tests
        test_args.extend([
            "-m", "integration",
            "tests/test_integration_manager.py",
            "tests/test_integration_cli.py"
        ])
        print("Running all integration tests...")
    
    # Add common pytest options
    test_args.extend([
        "--tb=short",
        "--maxfail=3",  # Stop after 3 failures
        "-x" if "--stop-on-fail" in sys.argv else "--continue-on-collection-errors"
    ])
    
    print(f"Command: {' '.join(test_args)}")
    print("-" * 60)
    
    # Run tests
    try:
        result = subprocess.run(test_args, cwd=Path(__file__).parent)
        return result.returncode
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    
    if exit_code == 0:
        print("\n✅ Integration tests completed successfully!")
    else:
        print(f"\n❌ Integration tests failed with exit code {exit_code}")
    
    sys.exit(exit_code)
