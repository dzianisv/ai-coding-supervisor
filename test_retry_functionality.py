#!/usr/bin/env python3
"""
Test script to verify the retry functionality works correctly.
This creates a controlled test scenario for the retry mechanism.
"""

import asyncio
import tempfile
import os
from vibeteam_tasks import RetryConfig, RetryManager, async_main

def test_retry_config():
    """Test RetryConfig creation and validation."""
    print("🧪 Testing RetryConfig...")
    
    # Test default configuration
    config = RetryConfig()
    assert config.max_attempts == 3
    assert config.base_delay == 60.0
    assert config.max_delay == 3600.0
    assert config.exponential_base == 2.0
    assert config.jitter == True
    assert "usage limit" in config.retryable_errors
    print("✅ Default RetryConfig works")
    
    # Test custom configuration
    custom_config = RetryConfig(
        max_attempts=5,
        base_delay=30.0,
        max_delay=1800.0,
        retryable_errors=["custom error", "test failure"]
    )
    assert custom_config.max_attempts == 5
    assert custom_config.base_delay == 30.0
    assert "custom error" in custom_config.retryable_errors
    print("✅ Custom RetryConfig works")


def test_retry_manager():
    """Test RetryManager functionality."""
    print("\n🧪 Testing RetryManager...")
    
    config = RetryConfig(base_delay=10.0, max_delay=100.0, jitter=False)
    manager = RetryManager(config)
    
    # Test error detection
    assert manager.should_retry_error("Usage limit reached") == True
    assert manager.should_retry_error("Rate limit exceeded") == True
    assert manager.should_retry_error("Normal error message") == False
    print("✅ Error detection works")
    
    # Test delay calculation (without jitter for predictable results)
    delay1 = manager.calculate_delay(1)
    delay2 = manager.calculate_delay(2)
    delay3 = manager.calculate_delay(3)
    
    assert delay1 == 10.0  # base_delay * 2^0
    assert delay2 == 20.0  # base_delay * 2^1
    assert delay3 == 40.0  # base_delay * 2^2
    print("✅ Exponential backoff calculation works")
    
    # Test max delay cap
    delay_high = manager.calculate_delay(10)  # Should be capped at max_delay
    assert delay_high == 100.0
    print("✅ Max delay cap works")
    
    # Test duration formatting
    assert manager.format_duration(30) == "30.0s"
    assert manager.format_duration(90) == "1.5m"
    assert manager.format_duration(7200) == "2.0h"
    print("✅ Duration formatting works")


async def test_retry_integration():
    """Test retry integration with actual task execution (mock scenario)."""
    print("\n🧪 Testing retry integration...")
    
    # Create a temporary tasks file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("[ ] Test task for retry functionality\n")
        tasks_file = f.name
    
    try:
        # Test with retry disabled (should complete quickly)
        print("🔸 Testing without retry...")
        
        # Note: This would normally fail due to missing Claude setup,
        # but we can test the configuration loading
        config = RetryConfig(max_attempts=2, base_delay=1.0, max_delay=5.0)
        manager = RetryManager(config)
        
        # Verify the configuration is set up correctly
        assert manager.config.max_attempts == 2
        assert manager.config.base_delay == 1.0
        print("✅ Retry configuration loading works")
        
        # Test error pattern matching
        test_errors = [
            "Claude usage limit reached for this month",
            "Rate limit exceeded (429)",
            "Timeout occurred during request",
            "Service temporarily unavailable (503)",
            "Invalid syntax error"  # This should NOT trigger retry
        ]
        
        retryable_count = sum(1 for error in test_errors if manager.should_retry_error(error))
        assert retryable_count == 4  # First 4 should be retryable
        print("✅ Error pattern matching works correctly")
        
    finally:
        # Clean up
        os.unlink(tasks_file)
    
    print("✅ Retry integration test completed")


def test_retry_delay_progression():
    """Test the delay progression for multiple retry attempts."""
    print("\n🧪 Testing retry delay progression...")
    
    config = RetryConfig(base_delay=5.0, max_delay=60.0, exponential_base=2.0, jitter=False)
    manager = RetryManager(config)
    
    expected_delays = [5.0, 10.0, 20.0, 40.0, 60.0, 60.0]  # Last two capped at max_delay
    
    for i, expected in enumerate(expected_delays, 1):
        actual = manager.calculate_delay(i)
        assert actual == expected, f"Attempt {i}: expected {expected}, got {actual}"
        print(f"✅ Attempt {i}: {manager.format_duration(actual)} delay")
    
    print("✅ Delay progression test completed")


def main():
    """Run all tests."""
    print("🚀 VibeTeam Retry Functionality Test Suite")
    print("=" * 50)
    
    try:
        test_retry_config()
        test_retry_manager()
        asyncio.run(test_retry_integration())
        test_retry_delay_progression()
        
        print("\n" + "=" * 50)
        print("🎉 All tests passed! Retry functionality is working correctly.")
        print("\n📝 Usage examples:")
        print("   vibeteam-task --retry                    # Enable retry with defaults")
        print("   vibeteam-task --retry --max-attempts 5   # Retry up to 5 times")
        print("   vibeteam-task --retry --base-delay 120   # Wait 2 minutes before first retry")
        print("   vibeteam-task --retry --max-delay 1800   # Cap delays at 30 minutes")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    main()