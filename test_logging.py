#!/usr/bin/env python3
"""
Test script to demonstrate the improved logging functionality
"""

import sys
import os
from pathlib import Path

# Add the project to the path
sys.path.insert(0, str(Path(__file__).parent))

from agents.claude_code_agent import ClaudeCodeAgent


def demo_improved_logging():
    """Demonstrate the improved logging features"""
    
    print("🚀 VibeTeam Improved Logging Demo")
    print("=" * 50)
    print()
    
    # Create a test agent
    agent = ClaudeCodeAgent(
        debug_mode=False, 
        working_directory='/Users/engineer/workspace/VibeTeam'
    )
    
    print("📋 New Logging Features:")
    print("✓ Tool names with detailed parameters")
    print("✓ Bash commands displayed clearly")
    print("✓ File paths for Read/Write/Edit operations")
    print("✓ Search patterns for Grep/Glob")
    print("✓ Compact format (no double newlines)")
    print("✓ Cost and timing on same line")
    print()
    
    print("🎯 Example Output:")
    print("-" * 30)
    
    # Simulate the improved logging format
    print("🤖 Claude: I'll help you improve the logging system.")
    print("🔧 Using tool: Read")
    print("   → File: /Users/engineer/workspace/VibeTeam/utils/logging.py")
    print("🔧 Using tool: Bash")
    print("   → Command: find . -name '*.py' -exec grep -l 'logging' {} \\;")
    print("🔧 Using tool: Grep")
    print("   → Pattern: def.*logging (in /Users/engineer/workspace/VibeTeam)")
    print("🔧 Using tool: Edit")
    print("   → Editing: /Users/engineer/workspace/VibeTeam/agents/claude_code_agent.py")
    print("👤 User: [tool_result data]")
    print("✅ Task completed successfully")
    print("📄 Result: Enhanced logging with tool parameters and compact format...")
    print("💰 $0.0234 | ⏱️ 2.15s")
    
    print()
    print("🎉 Logging improvements completed!")
    print("   The system now shows detailed tool parameters")
    print("   and uses a more compact, readable format.")


if __name__ == "__main__":
    demo_improved_logging()