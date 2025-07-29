
import asyncio
import os
import re
from agents.claude_code_agent import ClaudeCodeAgent

async def async_main(working_dir=None, debug_mode=False):
    """
    Async main function to run the Claude Code Engineer to complete tasks from tasks.md.
    
    Args:
        working_dir: Directory to run in (defaults to current directory)
        debug_mode: Enable debug output for technical details
    """
    if working_dir:
        os.chdir(working_dir)
    
    # Welcome message
    print("🚀 VibeTeam Task Automation")
    print(f"📁 Working in: {os.getcwd()}")
    if debug_mode:
        print("🐛 Debug mode enabled - showing technical details")
    print()
    
    prompt = "You are a software Engineer. Your task is to get a task from the tasks.md. Complete it. Cover with test. Run test. Fix any related issues if any. Re-run test. Reflect. Review git diff. Reflect. Fix if any issues. Commit"
    
    # Check if tasks.md exists
    if not os.path.exists("tasks.md"):
        print("❌ Error: tasks.md file not found in current directory.")
        print()
        print("📝 Please create a tasks.md file with tasks in checkbox format:")
        print("   [ ] Your task description here")
        print("   [ ] Another task to complete")
        print()
        return 1
    
    while True:
        with open("tasks.md", "r") as f:
            tasks = f.readlines()

        unchecked_tasks = [task for task in tasks if task.strip().startswith("[ ]")]

        if not unchecked_tasks:
            print("✅ All tasks in tasks.md are completed!")
            break

        print(f"📋 Found {len(unchecked_tasks)} uncompleted task(s)")
        
        # Show the current task being worked on
        if unchecked_tasks:
            current_task = unchecked_tasks[0].strip()
            task_description = current_task.replace("[ ]", "").strip()
            print(f"🎯 Working on: {task_description}")
            print("-" * 50)
        
        claude_agent = ClaudeCodeAgent(
            working_directory=os.getcwd(),
            permission_mode="bypassPermissions",
            debug_mode=debug_mode,
        )

        # We are not passing any specific task, the agent will read the file
        # as per the initial prompt.
        await claude_agent.execute_task({
            "description": prompt
        })

        # After the agent runs, we'd expect tasks.md to be modified.
        # The loop will then re-read the file and check for remaining tasks.
        print("=" * 50)
        print("🔄 Task cycle completed! Checking for remaining tasks...")
        print()
    
    return 0


def main():
    """
    Console script entry point for vibeteam-task command.
    """
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="VibeTeam automated task completion from tasks.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vibeteam-task                    # Run in current directory
  vibeteam-task --dir /path/to/project
  
The tool will read tasks.md and complete unchecked tasks:
  [ ] Write python hello world hello.py
  [ ] Create a REST API endpoint
        """
    )
    parser.add_argument(
        "--dir", "-d",
        metavar="PATH",
        help="Working directory (default: current directory)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for technical details"
    )
    parser.add_argument(
        "--version", "-v",
        action="version", 
        version="vibeteam-task 0.1.0"
    )
    
    args = parser.parse_args()
    
    try:
        exit_code = asyncio.run(async_main(working_dir=args.dir, debug_mode=args.debug))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Task execution interrupted by user")
        print("👋 Goodbye!")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("💡 Try checking your tasks.md file format or Claude CLI setup")
        sys.exit(1)


if __name__ == "__main__":
    main()
