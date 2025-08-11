#!/usr/bin/env python3
"""
Test script to check what error messages Claude Code agent actually produces.
This will help verify our retry patterns match real-world error scenarios.
"""

import asyncio
import sys
from agents.claude_code_agent import ClaudeCodeAgent
from vibeteam_tasks import RetryConfig, RetryManager

async def test_claude_code_errors():
    """Test what errors Claude Code agent actually produces."""
    print("🧪 Testing actual Claude Code agent error patterns...")
    
    # Create retry manager to test against
    config = RetryConfig()
    manager = RetryManager(config)
    
    try:
        # Create Claude Code agent
        agent = ClaudeCodeAgent(
            working_directory=".",
            permission_mode="bypassPermissions",
            debug_mode=True
        )
        
        # Test with a task that might trigger rate limits
        # (if we have limited API quota)
        test_task = {
            "description": "Generate a simple hello world program in Python"
        }
        
        print("Executing test task to see error format...")
        result = await agent.execute_task(test_task)
        
        if result.errors:
            print(f"✅ Found errors from Claude Code agent:")
            for i, error in enumerate(result.errors, 1):
                print(f"   {i}. {error}")
                
                # Test if our retry patterns would catch this error
                should_retry, pattern = manager.should_retry_error(error)
                if should_retry:
                    print(f"      ✅ Would retry with pattern: '{pattern}'")
                else:
                    print(f"      ❌ Would NOT retry - consider adding pattern")
        else:
            print("✅ Task completed successfully, no errors to analyze")
            
    except Exception as e:
        error_str = str(e)
        print(f"✅ Found exception from Claude Code agent: {error_str}")
        
        # Test our patterns against this real error
        should_retry, pattern = manager.should_retry_error(error_str)
        if should_retry:
            print(f"   ✅ Would retry with pattern: '{pattern}'")
        else:
            print(f"   ❌ Would NOT retry - consider adding pattern")
            
        # Let's see what kind of error this is
        if "anthropic" in error_str.lower():
            print("   📋 This appears to be an Anthropic-related error")
        elif "claude" in error_str.lower():
            print("   📋 This appears to be a Claude-related error")
        elif "usage" in error_str.lower() or "limit" in error_str.lower():
            print("   📋 This appears to be a usage/limit error")
        elif "rate" in error_str.lower():
            print("   📋 This appears to be a rate limit error")
        elif "timeout" in error_str.lower():
            print("   📋 This appears to be a timeout error")
        else:
            print("   📋 Error type not immediately clear from message")

def test_common_error_patterns():
    """Test common error patterns we might encounter."""
    print("\n🧪 Testing common error patterns...")
    
    config = RetryConfig()
    manager = RetryManager(config)
    
    # Real-world error examples based on API documentation
    common_errors = [
        # Anthropic API errors
        "anthropic.RateLimitError: 429 rate_limit_error",
        "anthropic.APIError: 529 overloaded_error", 
        "anthropic.APIConnectionError: Connection timeout",
        "Usage limit exceeded for this month",
        "Credit limit reached for your account",
        
        # Generic API patterns
        "API rate limit exceeded",
        "Too many requests per minute",
        "Service temporarily overloaded",
        "Request timeout after 30 seconds",
        
        # Network/Infrastructure errors  
        "Connection reset by peer",
        "SSL handshake timeout",
        "HTTPSConnectionPool timeout",
        "502 Bad Gateway",
        "503 Service Unavailable",
        
        # Non-retryable errors (should NOT retry)
        "Invalid API key provided",
        "Authentication failed", 
        "File not found",
        "Syntax error in code",
        "Permission denied"
    ]
    
    retryable_count = 0
    non_retryable_count = 0
    
    for error in common_errors:
        should_retry, pattern = manager.should_retry_error(error)
        
        if should_retry:
            retryable_count += 1
            print(f"   ✅ RETRY: {error} → '{pattern}'")
        else:
            non_retryable_count += 1
            print(f"   ❌ SKIP:  {error}")
    
    print(f"\n📊 Results: {retryable_count} retryable, {non_retryable_count} non-retryable")
    
    # Check coverage of key patterns
    key_patterns = ["rate limit", "usage limit", "timeout", "overloaded", "502", "503"]
    missing_patterns = []
    
    for pattern in key_patterns:
        found = False
        for error in common_errors:
            if pattern in error.lower():
                should_retry, _ = manager.should_retry_error(error)
                if should_retry:
                    found = True
                    break
        if not found:
            missing_patterns.append(pattern)
    
    if missing_patterns:
        print(f"⚠️  Potentially missing patterns: {missing_patterns}")
    else:
        print("✅ All key patterns covered")

def main():
    print("🚀 Claude Code Error Pattern Validation")
    print("=" * 50)
    
    # Test common patterns first (doesn't require API calls)
    test_common_error_patterns()
    
    # Test actual Claude Code agent (may require API keys)
    print("\n" + "=" * 50)
    try:
        asyncio.run(test_claude_code_errors())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("💡 This is expected if Claude Code SDK is not properly configured")
    
    print("\n" + "=" * 50)
    print("🎯 Validation complete!")
    print("\n📝 Recommendations:")
    print("1. Run this test when you encounter real API errors to validate patterns")
    print("2. Update retry patterns based on actual error messages seen in production")
    print("3. Monitor retry statistics to identify new error patterns")

if __name__ == "__main__":
    main()