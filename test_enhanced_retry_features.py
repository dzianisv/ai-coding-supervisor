#!/usr/bin/env python3
"""
Test script to verify the enhanced retry functionality works correctly.
Tests new features like dynamic delay adjustment and improved error pattern matching.
"""

import tempfile
import os
from vibeteam_tasks import RetryConfig, RetryManager

def test_enhanced_error_patterns():
    """Test the enhanced error pattern matching."""
    print("🧪 Testing enhanced error pattern matching...")
    
    config = RetryConfig()
    manager = RetryManager(config)
    
    # Test Claude/Anthropic specific errors
    claude_errors = [
        "Credit limit exceeded for your account",
        "Anthropic usage quota reached", 
        "Model currently overloaded, please retry",
        "Request queued due to high demand",
        "Claude API rate limit exceeded"
    ]
    
    for error in claude_errors:
        should_retry, pattern = manager.should_retry_error(error)
        assert should_retry, f"Should retry Claude error: {error}"
        print(f"   ✅ Claude error matched: '{pattern}'")
    
    # Test OpenAI specific errors
    openai_errors = [
        "OpenAI usage limit exceeded",
        "Tokens per minute limit reached",
        "Requests per minute exceeded",
        "Model currently overloaded with other requests"
    ]
    
    for error in openai_errors:
        should_retry, pattern = manager.should_retry_error(error)
        assert should_retry, f"Should retry OpenAI error: {error}"
        print(f"   ✅ OpenAI error matched: '{pattern}'")
    
    # Test network/timeout errors
    network_errors = [
        "Connection timeout occurred",
        "SSL error during handshake",
        "Network error: connection refused",
        "Read timeout after 30 seconds"
    ]
    
    for error in network_errors:
        should_retry, pattern = manager.should_retry_error(error)
        assert should_retry, f"Should retry network error: {error}"
        print(f"   ✅ Network error matched: '{pattern}'")
    
    # Test non-retryable errors
    non_retryable_errors = [
        "Syntax error in Python code",
        "File not found",
        "Permission denied",
        "Invalid API key provided"
    ]
    
    for error in non_retryable_errors:
        should_retry, pattern = manager.should_retry_error(error)
        assert not should_retry, f"Should NOT retry error: {error}"
        print(f"   ✅ Non-retryable error correctly ignored: {error}")
    
    print("✅ Enhanced error pattern matching works correctly")


def test_dynamic_delay_adjustment():
    """Test dynamic delay adjustment based on error type."""
    print("\n🧪 Testing dynamic delay adjustment...")
    
    config = RetryConfig(base_delay=60.0, exponential_base=2.0, jitter=False)
    manager = RetryManager(config)
    
    # Test quota/limit errors (should have longer delays)
    quota_delay = manager.calculate_delay(1, "quota exceeded")
    normal_delay = manager.calculate_delay(1, "")
    
    assert quota_delay > normal_delay, "Quota errors should have longer delays"
    print(f"   ✅ Quota error delay: {manager.format_duration(quota_delay)} vs normal: {manager.format_duration(normal_delay)}")
    
    # Test overloaded errors (should have shorter delays)
    overload_delay = manager.calculate_delay(1, "model overloaded")
    
    assert overload_delay < normal_delay, "Overload errors should have shorter delays"
    print(f"   ✅ Overload error delay: {manager.format_duration(overload_delay)} vs normal: {manager.format_duration(normal_delay)}")
    
    print("✅ Dynamic delay adjustment works correctly")


def test_retry_statistics():
    """Test retry statistics tracking."""
    print("\n🧪 Testing retry statistics tracking...")
    
    config = RetryConfig()
    manager = RetryManager(config)
    
    # Simulate some retry attempts
    manager.should_retry_error("Usage limit reached")
    manager.should_retry_error("Rate limit exceeded") 
    manager.should_retry_error("Usage limit reached")  # Same pattern again
    manager.should_retry_error("Invalid request")  # Non-retryable
    
    stats = manager.get_retry_stats()
    
    # Check statistics
    assert stats["error_patterns"]["usage limit"] == 2, "Should track usage limit pattern twice"
    assert stats["error_patterns"]["rate limit"] == 1, "Should track rate limit pattern once"
    assert "Invalid request" not in stats["error_patterns"], "Should not track non-retryable patterns"
    
    print(f"   ✅ Pattern tracking: {stats['error_patterns']}")
    
    # Test success/failure logging
    manager.log_retry_success()
    manager.log_retry_failure("Final error")
    
    updated_stats = manager.get_retry_stats()
    assert updated_stats["successful_retries"] == 1, "Should track successful retry"
    assert updated_stats["failed_retries"] == 1, "Should track failed retry"
    
    print(f"   ✅ Success/failure tracking: {updated_stats['successful_retries']} success, {updated_stats['failed_retries']} failure")
    print("✅ Retry statistics tracking works correctly")


def test_comprehensive_error_coverage():
    """Test comprehensive coverage of various API error scenarios."""
    print("\n🧪 Testing comprehensive error coverage...")
    
    config = RetryConfig()
    manager = RetryManager(config)
    
    # Test various real-world error scenarios
    test_cases = [
        # HTTP status code errors
        ("HTTP 429: Too Many Requests", True, "429"),
        ("502 Bad Gateway error", True, "502"),
        ("Service returned 503 unavailable", True, "503"),
        ("Gateway timeout 504", True, "504"),
        ("Cloudflare error 524", True, "524"),
        
        # API-specific quota/limit errors
        ("Monthly usage limit exceeded", True, "usage limit"),
        ("Daily limit exceeded for API", True, "daily limit exceeded"),
        ("Rate_limit_error from API", True, "rate_limit_error"),
        ("Too many requests in short period", True, "too many requests"),
        
        # Server/service errors
        ("Internal server error occurred", True, "internal server error"),
        ("Bad gateway response", True, "bad gateway"),
        ("Service temporarily unavailable", True, "service temporarily unavailable"),
        
        # Implementation errors (should NOT retry)
        ("TypeError: expected string", False, ""),
        ("KeyError: missing required field", False, ""),
        ("ValueError: invalid input", False, ""),
        ("Import error: module not found", False, ""),
    ]
    
    retryable_count = 0
    non_retryable_count = 0
    
    for error_msg, should_be_retryable, expected_pattern in test_cases:
        should_retry, actual_pattern = manager.should_retry_error(error_msg)
        
        if should_be_retryable:
            assert should_retry, f"Should retry: {error_msg}"
            # Note: We don't require exact pattern match since multiple patterns might match
            retryable_count += 1
            print(f"   ✅ Retryable: {error_msg} → {actual_pattern}")
        else:
            assert not should_retry, f"Should NOT retry: {error_msg}"
            non_retryable_count += 1
            print(f"   ✅ Non-retryable: {error_msg}")
    
    print(f"✅ Comprehensive coverage test: {retryable_count} retryable, {non_retryable_count} non-retryable")


def main():
    """Run all enhanced tests."""
    print("🚀 VibeTeam Enhanced Retry Functionality Test Suite")
    print("=" * 60)
    
    try:
        test_enhanced_error_patterns()
        test_dynamic_delay_adjustment()
        test_retry_statistics()
        test_comprehensive_error_coverage()
        
        print("\n" + "=" * 60)
        print("🎉 All enhanced tests passed! Advanced retry functionality is working correctly.")
        print("\n📝 New features tested:")
        print("   ✅ Enhanced error pattern matching (Claude, OpenAI, network errors)")
        print("   ✅ Dynamic delay adjustment based on error type")
        print("   ✅ Retry statistics tracking and reporting")
        print("   ✅ Comprehensive real-world error scenario coverage")
        print("\n🔧 Enhanced retry CLI usage:")
        print("   vibeteam-task --retry --debug                    # See detailed retry logs")
        print("   vibeteam-task --retry --base-delay 120           # 2min delays for quota issues")
        print("   vibeteam-task --retry --max-attempts 5           # More attempts for critical tasks")
        
    except Exception as e:
        print(f"\n❌ Enhanced test failed: {e}")
        raise


if __name__ == "__main__":
    main()