
import asyncio
import os
import re
import json
import time
import random
from typing import Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from agents.claude_code_agent import ClaudeCodeAgent


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""
    max_attempts: int = Field(default=3, description="Maximum number of retry attempts")
    base_delay: float = Field(default=60.0, description="Base delay in seconds before first retry")
    max_delay: float = Field(default=3600.0, description="Maximum delay in seconds")
    exponential_base: float = Field(default=2.0, description="Exponential backoff multiplier")
    jitter: bool = Field(default=True, description="Add random jitter to delays")
    retryable_errors: list[str] = Field(
        default=[
            "usage limit",
            "quota exceeded", 
            "rate limit",
            "429",
            "timeout",
            "temporary failure",
            "service unavailable",
            "502",
            "503",
            "504"
        ],
        description="Error patterns that should trigger retries"
    )


class TaskReflection(BaseModel):
    """Structured output for task reflection analysis."""
    task_completed: bool = Field(description="Whether the task was successfully completed")
    completion_quality: int = Field(description="Quality of completion on a scale of 1-10", ge=1, le=10)
    issues_found: list[str] = Field(description="List of issues or problems identified")
    suggestions: list[str] = Field(description="List of suggestions for improvement")
    needs_retry: bool = Field(description="Whether the task should be retried")
    retry_reason: Optional[str] = Field(default=None, description="Reason why retry is needed if needs_retry is True")
    is_transient_error: bool = Field(default=False, description="Whether the error is likely transient (API limits, timeouts)")


class RetryManager:
    """Manages retry logic for task execution."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    def should_retry_error(self, error_message: str) -> bool:
        """Check if an error should trigger a retry based on configured patterns."""
        error_lower = error_message.lower()
        return any(pattern.lower() in error_lower for pattern in self.config.retryable_errors)
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number with exponential backoff and jitter."""
        if attempt <= 0:
            return 0.0
        
        # Exponential backoff: base_delay * exponential_base^(attempt-1)
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        
        # Cap at max_delay
        delay = min(delay, self.config.max_delay)
        
        # Add jitter if enabled (±25% random variation)
        if self.config.jitter:
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0.0, delay)
    
    def format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"


class ReflectionModule:
    """OpenAI-powered reflection module for task completion analysis."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = None):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
    
    async def reflect_on_task(self, initial_task: str, outcome: str, debug_mode: bool = False) -> TaskReflection:
        """
        Reflect on a completed task and determine if it needs to be retried.
        
        Args:
            initial_task: The original task description
            outcome: The outcome/result of the task execution
            debug_mode: Whether to show debug information
            
        Returns:
            TaskReflection object with analysis and retry decision
        """
        reflection_prompt = f"""
You are a senior software engineer reviewing the completion of a development task.

INITIAL TASK:
{initial_task}

OUTCOME/RESULT:
{outcome}

Please analyze whether this task was completed successfully and provide structured feedback.

Consider:
1. Was the original task requirement fully met?
2. Are there any obvious issues, errors, or incomplete implementations?
3. Does the solution follow best practices?
4. Are there any missing components (tests, documentation, error handling)?
5. Would this pass a code review?
6. IMPORTANT: Check if any failures are due to transient errors like:
   - API usage limits or quotas exceeded
   - Rate limiting (429 errors)
   - Timeouts or temporary service unavailability
   - Network issues or temporary API failures
   
If the failure is due to transient errors (API limits, timeouts, etc.), set is_transient_error=True 
and needs_retry=True. These should be retried later when the issue resolves.

For genuine implementation issues, set is_transient_error=False.

Be thorough but practical in your assessment.
"""
        
        if debug_mode:
            print("🤔 Reflecting on task completion...")
            print(f"🔍 Using model: {self.model}")
        
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a senior software engineer conducting a thorough code review and task completion analysis."},
                    {"role": "user", "content": reflection_prompt}
                ],
                response_format=TaskReflection,
                temperature=0.1
            )
            
            reflection = response.choices[0].message.parsed
            
            if debug_mode:
                print(f"📊 Reflection Results:")
                print(f"   ✅ Task Completed: {reflection.task_completed}")
                print(f"   🎯 Quality Score: {reflection.completion_quality}/10")
                print(f"   🔄 Needs Retry: {reflection.needs_retry}")
                if reflection.issues_found:
                    print(f"   ⚠️  Issues: {', '.join(reflection.issues_found)}")
                if reflection.suggestions:
                    print(f"   💡 Suggestions: {', '.join(reflection.suggestions)}")
            
            return reflection
            
        except Exception as e:
            if debug_mode:
                print(f"❌ Reflection error: {e}")
            # Return a default reflection that doesn't trigger retry
            return TaskReflection(
                task_completed=True,
                completion_quality=5,
                issues_found=[f"Reflection failed: {str(e)}"],
                suggestions=["Manual review recommended"],
                needs_retry=False
            )


async def async_main(working_dir=None, debug_mode=False, tasks_file="tasks.md", enable_reflection=False, enable_retry=False, retry_config=None):
    """
    Async main function to run the Claude Code Engineer to complete tasks from a specified file.
    
    Args:
        working_dir: Directory to run in (defaults to current directory)
        debug_mode: Enable debug output for technical details
        tasks_file: Path to the tasks file (defaults to tasks.md)
        enable_reflection: Enable OpenAI-powered reflection on task completion
        enable_retry: Enable automatic retry for transient failures
        retry_config: RetryConfig object with retry parameters
    """
    if working_dir:
        os.chdir(working_dir)
    
    # Setup retry configuration
    if retry_config is None:
        retry_config = RetryConfig()
    
    retry_manager = RetryManager(retry_config) if enable_retry else None
    
    # Welcome message
    print("🚀 VibeTeam Task Automation")
    print(f"📁 Working in: {os.getcwd()}")
    print(f"📋 Tasks file: {tasks_file}")
    if debug_mode:
        print("🐛 Debug mode enabled - showing technical details")
    if enable_reflection:
        print("🤔 Reflection mode enabled - using OpenAI for task evaluation")
    if enable_retry:
        print(f"🔄 Retry mode enabled - max {retry_config.max_attempts} attempts with exponential backoff")
        if debug_mode:
            print(f"   📊 Base delay: {retry_manager.format_duration(retry_config.base_delay)}")
            print(f"   📊 Max delay: {retry_manager.format_duration(retry_config.max_delay)}")
    print()
    
    # Initialize reflection module if enabled
    reflection_module = None
    if enable_reflection:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("❌ Error: OPENAI_API_KEY environment variable not set but reflection is enabled")
            print("💡 Please set OPENAI_API_KEY or disable reflection with --no-reflection")
            return 1
        
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        reflection_module = ReflectionModule(openai_api_key, base_url=openai_base_url)
        if debug_mode:
            endpoint_info = f" (using {openai_base_url})" if openai_base_url else ""
            print(f"✅ Reflection module initialized with OpenAI{endpoint_info}")
    
    # Check if tasks file exists
    if not os.path.exists(tasks_file):
        print(f"❌ Error: {tasks_file} file not found.")
        print()
        print("📝 Please create a tasks file with tasks in checkbox format:")
        print("   [ ] Your task description here")
        print("   [ ] Another task to complete")
        print()
        return 1
    
    while True:
        with open(tasks_file, "r") as f:
            tasks_content = f.read()
            tasks = f.readlines()

        # Reset file pointer and read lines again
        with open(tasks_file, "r") as f:
            tasks = f.readlines()

        unchecked_tasks = [task for task in tasks if task.strip().startswith("[ ]")]

        if not unchecked_tasks:
            print(f"✅ All tasks in {tasks_file} are completed!")
            break

        print(f"📋 Found {len(unchecked_tasks)} uncompleted task(s)")
        
        # Show the current task being worked on
        if unchecked_tasks:
            current_task = unchecked_tasks[0].strip()
            task_description = current_task.replace("[ ]", "").strip()
            print(f"🎯 Working on: {task_description}")
            print("-" * 50)
        
        # Create prompt with tasks file content embedded
        prompt = f"""You are a software Engineer. Your task is to complete tasks from the following tasks file content:

{tasks_content}

Instructions:
1. Find the first unchecked task (marked with [ ])
2. Complete the task
3. Cover it with tests
4. Run the tests
5. Fix any related issues if any
6. Re-run tests
7. Reflect on the implementation
8. Review git diff
9. Reflect and fix if any issues
10. Mark the task as completed by changing [ ] to [x] in the tasks file
11. Commit the changes

Focus on the first unchecked task only. Do not work on multiple tasks simultaneously."""
        
        # Enhanced task execution with retry and reflection support
        max_attempts = retry_config.max_attempts if enable_retry else (3 if enable_reflection else 1)
        attempt = 0
        task_completed_successfully = False
        last_error = None
        
        while attempt < max_attempts and not task_completed_successfully:
            attempt += 1
            
            # Show retry status
            if attempt > 1:
                print(f"🔄 Retry attempt {attempt}/{max_attempts}")
                if last_error and enable_retry and retry_manager.should_retry_error(str(last_error)):
                    print(f"   📝 Previous error: {str(last_error)[:100]}...")
                print("-" * 50)
            
            try:
                claude_agent = ClaudeCodeAgent(
                    working_directory=os.getcwd(),
                    permission_mode="bypassPermissions",
                    debug_mode=debug_mode,
                )

                # Execute the task
                execution_result = await claude_agent.execute_task({
                    "description": prompt
                })
                
                # Check if task execution had errors  
                if hasattr(execution_result, 'errors') and execution_result.errors:
                    error_messages = ' '.join(execution_result.errors)
                    last_error = error_messages
                    
                    # Check if this is a retryable error
                    if enable_retry and retry_manager.should_retry_error(error_messages):
                        print(f"⚠️  Detected retryable error: {error_messages[:100]}...")
                        
                        if attempt < max_attempts:
                            # Calculate and wait for retry delay
                            delay = retry_manager.calculate_delay(attempt)
                            print(f"⏱️  Waiting {retry_manager.format_duration(delay)} before retry...")
                            
                            if delay > 0:
                                await asyncio.sleep(delay)
                            continue
                        else:
                            print(f"❌ Max retry attempts reached. Final error: {error_messages}")
                            break
                
                # If reflection is enabled, analyze the task completion
                reflection = None
                if enable_reflection and reflection_module:
                    print("=" * 50)
                    print("🔍 Running reflection analysis...")
                    
                    # Get the outcome by checking what changed
                    outcome_details = []
                    if hasattr(execution_result, 'output'):
                        outcome_details.append(f"Output: {str(execution_result.output)[:200]}")
                    if hasattr(execution_result, 'errors') and execution_result.errors:
                        outcome_details.append(f"Errors: {', '.join(execution_result.errors)}")
                    
                    outcome = "Task execution completed. " + " ".join(outcome_details) if outcome_details else "Task execution completed. Check git diff and file changes for details."
                    
                    try:
                        reflection = await reflection_module.reflect_on_task(
                            initial_task=task_description,
                            outcome=outcome,
                            debug_mode=debug_mode
                        )
                        
                        if reflection.task_completed and not reflection.needs_retry:
                            task_completed_successfully = True
                            print(f"✅ Reflection: Task completed successfully (Quality: {reflection.completion_quality}/10)")
                            if reflection.suggestions:
                                print(f"💡 Suggestions for future: {', '.join(reflection.suggestions)}")
                        elif reflection.needs_retry:
                            print(f"❌ Reflection: Task needs retry - {reflection.retry_reason}")
                            if reflection.issues_found:
                                print(f"⚠️  Issues found: {', '.join(reflection.issues_found)}")
                            
                            # Handle transient errors with retry mechanism
                            if reflection.is_transient_error and enable_retry and attempt < max_attempts:
                                print("🔄 Transient error detected - using retry mechanism")
                                delay = retry_manager.calculate_delay(attempt)
                                print(f"⏱️  Waiting {retry_manager.format_duration(delay)} before retry...")
                                
                                if delay > 0:
                                    await asyncio.sleep(delay)
                                
                                # Update prompt with reflection feedback for retry
                                prompt += f"""

REFLECTION FEEDBACK FROM PREVIOUS ATTEMPT:
Issues found: {', '.join(reflection.issues_found)}
Suggestions: {', '.join(reflection.suggestions)}
Retry reason: {reflection.retry_reason}
Error type: {'Transient (API/Network)' if reflection.is_transient_error else 'Implementation Issue'}

Please address these issues in your implementation."""
                                continue
                            elif attempt < max_attempts:
                                # Non-transient error but still have attempts left
                                print("🔧 Implementation issue detected - retrying with feedback")
                                
                                # Update prompt with reflection feedback for retry
                                prompt += f"""

REFLECTION FEEDBACK FROM PREVIOUS ATTEMPT:
Issues found: {', '.join(reflection.issues_found)}
Suggestions: {', '.join(reflection.suggestions)}
Retry reason: {reflection.retry_reason}

Please address these issues in your implementation."""
                                continue
                            else:
                                # Max attempts reached
                                task_completed_successfully = True
                                print(f"⚠️  Max attempts reached. Proceeding despite issues.")
                        else:
                            task_completed_successfully = True
                            
                    except Exception as e:
                        print(f"❌ Reflection failed: {e}")
                        task_completed_successfully = True  # Proceed without reflection
                else:
                    # No reflection enabled, assume task completed if no obvious errors
                    task_completed_successfully = True
                    
            except Exception as e:
                last_error = str(e)
                print(f"❌ Task execution failed: {last_error}")
                
                # Check if this is a retryable error
                if enable_retry and retry_manager.should_retry_error(last_error) and attempt < max_attempts:
                    print(f"🔄 Retryable error detected, will retry...")
                    delay = retry_manager.calculate_delay(attempt)
                    print(f"⏱️  Waiting {retry_manager.format_duration(delay)} before retry...")
                    
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue
                else:
                    # Non-retryable error or max attempts reached
                    print(f"💥 Task failed after {attempt} attempt(s)")
                    break

        # After the agent runs, we'd expect the tasks file to be modified.
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
        description="VibeTeam automated task completion from a tasks file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vibeteam-task                           # Run in current directory with tasks.md
  vibeteam-task --dir /path/to/project    # Run in specific directory
  vibeteam-task --tasks-file my-tasks.md # Use custom tasks file
  vibeteam-task -t todo.txt -d /project   # Custom file and directory
  vibeteam-task --enable-reflection       # Enable OpenAI reflection analysis
  vibeteam-task --retry                   # Enable retry for usage limits/timeouts
  vibeteam-task --retry --max-attempts 5  # Retry up to 5 times
  vibeteam-task --retry --base-delay 120  # Wait 2 minutes before first retry
  
The tool will read the tasks file and complete unchecked tasks:
  [ ] Write python hello world hello.py
  [ ] Create a REST API endpoint

Reflection mode requires OPENAI_API_KEY environment variable.
Use OPENAI_BASE_URL to specify custom OpenAI-compatible API endpoint.

Retry mode automatically retries tasks when encountering:
- Claude usage limit reached (most common case)
- API rate limiting (429 errors)
- Timeouts and temporary service issues
- Other transient network failures

Retry uses exponential backoff with jitter for optimal behavior.
        """
    )
    parser.add_argument(
        "--dir", "-d",
        metavar="PATH",
        help="Working directory (default: current directory)"
    )
    parser.add_argument(
        "--tasks-file", "-t",
        metavar="FILE",
        default="tasks.md",
        help="Path to tasks file (default: tasks.md)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for technical details"
    )
    parser.add_argument(
        "--enable-reflection",
        action="store_true",
        help="Enable OpenAI-powered reflection analysis (requires OPENAI_API_KEY, optionally OPENAI_BASE_URL)"
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Enable automatic retry for transient failures (usage limits, timeouts, etc.)"
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        metavar="N",
        help="Maximum number of retry attempts (default: 3)"
    )
    parser.add_argument(
        "--base-delay",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="Base delay in seconds before first retry (default: 60.0)"
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=3600.0,
        metavar="SECONDS",
        help="Maximum delay in seconds between retries (default: 3600.0)"
    )
    parser.add_argument(
        "--version", "-v",
        action="version", 
        version="vibeteam-task 0.1.0"
    )
    
    args = parser.parse_args()
    
    # Create retry configuration if retry is enabled
    retry_config = None
    if args.retry:
        retry_config = RetryConfig(
            max_attempts=args.max_attempts,
            base_delay=args.base_delay,
            max_delay=args.max_delay
        )
    
    try:
        exit_code = asyncio.run(async_main(
            working_dir=args.dir, 
            debug_mode=args.debug, 
            tasks_file=args.tasks_file,
            enable_reflection=args.enable_reflection,
            enable_retry=args.retry,
            retry_config=retry_config
        ))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Task execution interrupted by user")
        print("👋 Goodbye!")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("💡 Try checking your tasks file format or Claude CLI setup")
        sys.exit(1)


if __name__ == "__main__":
    main()
