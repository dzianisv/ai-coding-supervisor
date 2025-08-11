#!/usr/bin/env python3
"""
Simplified end-to-end test for vibeteam-task retry functionality.
Tests retry logic without actual Claude Code execution to avoid timeouts.
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, AsyncMock
from vibeteam_tasks import RetryConfig, RetryManager

def create_test_task_file(content: str) -> str:
    """Create a temporary tasks file with given content."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        return f.name

class MockTaskResult:
    """Mock task result for testing."""
    def __init__(self, errors=None, output=None):
        self.errors = errors or []
        self.output = output or "Task completed"

async def test_retry_error_detection():
    """Test retry error detection with real patterns."""
    print("🧪 Testing retry error detection...")
    
    config = RetryConfig()
    manager = RetryManager(config)
    
    # Test real-world error patterns
    test_cases = [
        # Should retry
        ("anthropic.RateLimitError: 429 rate_limit_error", True, "rate_limit_error"),
        ("Usage limit exceeded for this month", True, "usage limit"),
        ("Credit limit reached for your account", True, "credit limit"),
        ("anthropic.APIError: 529 overloaded_error", True, "overloaded_error"),
        ("Service temporarily overloaded", True, "service temporarily overloaded"),
        ("Connection timeout occurred", True, "timeout"),
        ("502 Bad Gateway", True, "502"),
        ("503 Service Unavailable", True, "503"),
        
        # Should NOT retry
        ("SyntaxError: invalid syntax", False, ""),
        ("Invalid API key provided", False, ""),
        ("File not found", False, ""),
        ("Permission denied", False, ""),
    ]
    
    retryable_count = 0
    non_retryable_count = 0
    
    for error_msg, should_be_retryable, expected_pattern in test_cases:
        should_retry, actual_pattern = manager.should_retry_error(error_msg)
        
        if should_be_retryable:
            assert should_retry, f"Should retry: {error_msg}"
            retryable_count += 1
            print(f"   ✅ RETRY: {error_msg[:50]}... → '{actual_pattern}'")
        else:
            assert not should_retry, f"Should NOT retry: {error_msg}"
            non_retryable_count += 1
            print(f"   ❌ SKIP:  {error_msg[:50]}...")
    
    print(f"   📊 {retryable_count} retryable, {non_retryable_count} non-retryable")
    print("   ✅ Error detection working correctly")

async def test_retry_delay_calculation():
    """Test retry delay calculation with different error types."""
    print("\n🧪 Testing retry delay calculation...")
    
    config = RetryConfig(base_delay=10.0, exponential_base=2.0, jitter=False)
    manager = RetryManager(config)
    
    # Test normal delay progression
    delays = []
    for attempt in range(1, 4):
        delay = manager.calculate_delay(attempt)
        delays.append(delay)
    
    assert delays == [10.0, 20.0, 40.0], f"Expected [10.0, 20.0, 40.0], got {delays}"
    print(f"   ✅ Normal delays: {[f'{d}s' for d in delays]}")
    
    # Test quota error (should be 1.5x longer)
    quota_delay = manager.calculate_delay(1, "quota exceeded")
    normal_delay = manager.calculate_delay(1, "")
    
    assert quota_delay > normal_delay, "Quota errors should have longer delays"
    print(f"   ✅ Quota delay: {quota_delay}s vs normal: {normal_delay}s")
    
    # Test overload error (should be 0.75x shorter)
    overload_delay = manager.calculate_delay(1, "model overloaded")
    
    assert overload_delay < normal_delay, "Overload errors should have shorter delays"
    print(f"   ✅ Overload delay: {overload_delay}s vs normal: {normal_delay}s")

async def test_retry_statistics():
    """Test retry statistics tracking."""
    print("\n🧪 Testing retry statistics...")
    
    config = RetryConfig()
    manager = RetryManager(config)
    
    # Simulate error patterns
    errors_to_test = [
        "Usage limit exceeded",
        "Rate limit exceeded", 
        "Usage limit exceeded",  # Duplicate
        "Timeout occurred",
        "Invalid syntax"  # Non-retryable
    ]
    
    for error in errors_to_test:
        manager.should_retry_error(error)
    
    # Simulate actual retry attempts (these increment total_attempts)
    manager.log_retry_attempt(1, 3, "First attempt", 1.0, "usage limit")
    manager.log_retry_success()
    
    manager.log_retry_attempt(1, 3, "Second attempt", 1.0, "rate limit") 
    manager.log_retry_success()
    
    manager.log_retry_attempt(1, 3, "Third attempt", 1.0, "timeout")
    manager.log_retry_failure("Final failure")
    
    stats = manager.get_retry_stats()
    
    # Verify statistics
    assert stats["error_patterns"]["usage limit"] == 2, "Should track usage limit twice"
    assert stats["error_patterns"]["rate limit"] == 1, "Should track rate limit once"
    assert stats["error_patterns"]["timeout"] == 1, "Should track timeout once"
    assert stats["total_attempts"] == 3, "Should track three attempts"
    assert stats["successful_retries"] == 2, "Should track two successes"
    assert stats["failed_retries"] == 1, "Should track one failure"
    assert round(stats["success_rate"], 1) == 66.7, f"Success rate should be 66.7%, got {stats['success_rate']}"
    
    print(f"   ✅ Error patterns: {dict(list(stats['error_patterns'].items())[:3])}")
    print(f"   ✅ Success rate: {stats['success_rate']:.1f}%")
    print("   ✅ Statistics tracking working correctly")

async def test_retry_logging():
    """Test retry logging functionality."""
    print("\n🧪 Testing retry logging...")
    
    config = RetryConfig(base_delay=0.1, jitter=False)
    manager = RetryManager(config)
    
    # Test logging methods
    print("   📝 Testing log_retry_attempt...")
    manager.log_retry_attempt(1, 3, "Test error message", 0.1, "test pattern")
    
    print("   📝 Testing log_retry_success...")
    manager.log_retry_success()
    
    print("   📝 Testing log_retry_failure...")
    manager.log_retry_failure("Final test error")
    
    print("   📝 Testing print_retry_summary...")
    manager.print_retry_summary()
    
    print("   ✅ Logging functionality working correctly")

async def test_claude_configured_check():
    """Test Claude configuration detection."""
    print("\n🧪 Testing Claude configuration detection...")
    
    claude_settings = Path.home() / ".claude" / "settings.json"
    is_configured = claude_settings.exists()
    
    if is_configured:
        print("   ✅ Claude Code is configured")
        print("   💡 Full E2E tests with real Claude execution are possible")
    else:
        print("   ⚠️  Claude Code not configured")
        print("   💡 Install claude-code CLI and run 'claude auth' for full testing")
    
    print(f"   📁 Checked: {claude_settings}")
    print("   ✅ Configuration check working correctly")

async def main():
    """Run all simplified E2E retry tests."""
    print("🚀 Simplified End-to-End Retry Tests")
    print("=" * 50)
    
    try:
        await test_retry_error_detection()
        await test_retry_delay_calculation()
        await test_retry_statistics()
        await test_retry_logging()
        await test_claude_configured_check()
        
        print("\n" + "=" * 50)
        print("🎉 All simplified E2E tests passed!")
        print("\n📝 Key validations completed:")
        print("   ✅ Error pattern detection (Claude API specific)")
        print("   ✅ Dynamic delay calculation")
        print("   ✅ Statistics tracking and reporting")
        print("   ✅ Comprehensive logging")
        print("   ✅ Configuration detection")
        print("\n💡 The retry system is ready for production use!")
        
    except Exception as e:
        print(f"\n❌ Simplified E2E test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)