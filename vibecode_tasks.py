
import asyncio
import os
import re
from agents.claude_code_agent import ClaudeCodeAgent

async def main():
    """
    Main function to run the Claude Code Engineer to complete tasks from tasks.md.
    """
    prompt = "You are a software Engineer. Your task is to get a task from the tasks.md. Complete it. Cover with test. Run test. Fix any related issues if any. Re-run test. Reflect. Review git diff. Reflect. Fix if any issues. Commit"
    
    while True:
        with open("tasks.md", "r") as f:
            tasks = f.readlines()

        unchecked_tasks = [task for task in tasks if task.strip().startswith("[ ]")]

        if not unchecked_tasks:
            print("All tasks in tasks.md are completed.")
            break

        # For simplicity, we'll just work on the first unchecked task.
        # A more robust solution would involve prioritizing or selecting tasks.
        
        claude_agent = ClaudeCodeAgent(
            working_directory=os.getcwd(),
            permission_mode="bypassPermissions",
        )

        # We are not passing any specific task, the agent will read the file
        # as per the initial prompt.
        await claude_agent.execute_task({
            "description": prompt
        })

        # After the agent runs, we'd expect tasks.md to be modified.
        # The loop will then re-read the file and check for remaining tasks.
        print("Completed a task cycle. Checking for remaining tasks.")


if __name__ == "__main__":
    asyncio.run(main())
