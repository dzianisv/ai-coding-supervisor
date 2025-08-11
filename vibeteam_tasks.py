
import asyncio
import os
import re
import json
import time
import random
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI
from agents.claude_code_agent import ClaudeCodeAgent
from github import Github
from datetime import datetime
import subprocess


#  - ✅ anthropic.RateLimitError: 429 rate_limit_error
#  - ✅ anthropic.APIError: 529 overloaded_error
#  - ✅ anthropic.APIConnectionError: Connection timeout
#  - ✅ Usage limit exceeded for this month
#  - ✅ Credit limit reached for your account
#  - ✅ Service temporarily overloaded
#  - ✅ Network errors (connection reset, SSL, timeouts)



class RetryConfig(BaseModel):
    """Configuration for retry behavior."""
    max_attempts: int = Field(default=3, description="Maximum number of retry attempts")
    base_delay: float = Field(default=60.0, description="Base delay in seconds before first retry")
    max_delay: float = Field(default=3600.0, description="Maximum delay in seconds")
    exponential_base: float = Field(default=2.0, description="Exponential backoff multiplier")
    jitter: bool = Field(default=True, description="Add random jitter to delays")
    retryable_errors: list[str] = Field(
        default=[
            # General API limits and quotas
            "usage limit",
            "quota exceeded", 
            "rate limit",
            "rate_limit_error",
            "too many requests",
            "monthly limit exceeded",
            "daily limit exceeded",
            
            # Claude/Anthropic specific errors
            "credit limit",
            "anthropic usage",
            "model overloaded",
            "overloaded_error",
            "request queued",
            "claude api",
            "anthropic.ratelimiterror",
            "anthropic.apierror",
            "anthropic.apiconnectionerror",
            
            # OpenAI specific errors
            "openai usage",
            "tokens per minute",
            "requests per minute",
            "model currently overloaded",
            
            # HTTP status codes
            "429",  # Too Many Requests
            "502",  # Bad Gateway
            "503",  # Service Unavailable  
            "504",  # Gateway Timeout
            "524",  # Cloudflare timeout
            
            # Network and timeout errors
            "timeout",
            "read timeout",
            "connection timeout",
            "temporary failure",
            "service unavailable", 
            "service temporarily overloaded",
            "temporarily overloaded",
            "network error",
            "connection error",
            "connection reset",
            "ssl error",
            "httpsconnectionpool",
            
            # Server errors
            "internal server error",
            "server error",
            "bad gateway",
            "gateway timeout",
            "service temporarily unavailable"
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


class GitHubComment(BaseModel):
    """Represents a GitHub PR comment."""
    id: int
    body: str
    user: str
    created_at: datetime
    updated_at: datetime
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    pr_number: int
    is_resolved: bool = False


class RetryManager:
    """Manages retry logic for task execution."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.retry_stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "error_patterns": {}
        }
    
    def should_retry_error(self, error_message: str) -> tuple[bool, str]:
        """Check if an error should trigger a retry based on configured patterns.
        
        Returns:
            tuple: (should_retry: bool, matched_pattern: str)
        """
        error_lower = error_message.lower()
        for pattern in self.config.retryable_errors:
            if pattern.lower() in error_lower:
                # Track error pattern statistics
                self.retry_stats["error_patterns"][pattern] = self.retry_stats["error_patterns"].get(pattern, 0) + 1
                return True, pattern
        return False, ""
    
    def calculate_delay(self, attempt: int, error_type: str = "") -> float:
        """Calculate delay for the given attempt number with exponential backoff and jitter.
        
        Args:
            attempt: The attempt number (1-indexed)
            error_type: The type of error to potentially adjust delay
        """
        if attempt <= 0:
            return 0.0
        
        # Base exponential backoff: base_delay * exponential_base^(attempt-1)
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        
        # Adjust delay based on error type
        if "quota" in error_type.lower() or "limit" in error_type.lower():
            # Longer delays for quota/limit errors
            delay *= 1.5
        elif "overloaded" in error_type.lower() or "queued" in error_type.lower():
            # Shorter delays for overload errors (they resolve faster)
            delay *= 0.75
        
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
    
    def log_retry_attempt(self, attempt: int, max_attempts: int, error: str, delay: float, error_pattern: str = ""):
        """Log retry attempt with detailed information."""
        self.retry_stats["total_attempts"] += 1
        
        print(f"🔄 Retry {attempt}/{max_attempts}: {error_pattern or 'Unknown error'}")
        print(f"   📝 Error: {error[:100]}{'...' if len(error) > 100 else ''}")
        print(f"   ⏱️  Waiting {self.format_duration(delay)} before retry...")
        
        if error_pattern:
            print(f"   🏷️  Pattern matched: '{error_pattern}'")
    
    def log_retry_success(self):
        """Log successful retry."""
        self.retry_stats["successful_retries"] += 1
        print("✅ Retry successful!")
    
    def log_retry_failure(self, final_error: str):
        """Log final retry failure."""
        self.retry_stats["failed_retries"] += 1
        print(f"❌ All retry attempts exhausted. Final error: {final_error[:100]}{'...' if len(final_error) > 100 else ''}")
    
    def get_retry_stats(self) -> dict:
        """Get retry statistics."""
        stats = self.retry_stats.copy()
        if stats["total_attempts"] > 0:
            stats["success_rate"] = (stats["successful_retries"] / stats["total_attempts"]) * 100
        else:
            stats["success_rate"] = 0.0
        return stats
    
    def print_retry_summary(self):
        """Print a summary of retry statistics."""
        stats = self.get_retry_stats()
        if stats["total_attempts"] > 0:
            print("\n📊 Retry Statistics Summary:")
            print(f"   🔄 Total retry attempts: {stats['total_attempts']}")
            print(f"   ✅ Successful retries: {stats['successful_retries']}")
            print(f"   ❌ Failed retries: {stats['failed_retries']}")
            print(f"   📈 Success rate: {stats['success_rate']:.1f}%")
            
            if stats["error_patterns"]:
                print("   🏷️  Most common error patterns:")
                sorted_patterns = sorted(stats["error_patterns"].items(), key=lambda x: x[1], reverse=True)
                for pattern, count in sorted_patterns[:5]:  # Top 5
                    print(f"      • {pattern}: {count} time(s)")
            print()


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




class GitHubPRManager:
    """Manages GitHub PR operations and comment processing."""
    
    def __init__(self, github_token: str, repo_url: str, working_dir: str, debug_mode: bool = False):
        self.github = Github(github_token)
        self.repo_url = repo_url
        self.working_dir = working_dir
        self.debug_mode = debug_mode
        self.github_token = github_token
        
        # Parse repo URL to get owner/repo
        if repo_url.startswith('https://github.com/'):
            repo_path = repo_url.replace('https://github.com/', '').rstrip('/')
            self.clone_url = f"https://{github_token}@github.com/{repo_path}.git"
        elif repo_url.startswith('git@github.com:'):
            repo_path = repo_url.replace('git@github.com:', '').replace('.git', '').rstrip('/')
            self.clone_url = repo_url
        else:
            repo_path = repo_url
            self.clone_url = f"https://{github_token}@github.com/{repo_path}.git"
        
        self.repo_path = repo_path
        self.repo = self.github.get_repo(repo_path)
        self.local_repo_dir = os.path.join(working_dir, repo_path.split('/')[-1])
        
        if debug_mode:
            print(f"🔗 Connected to GitHub repo: {self.repo.full_name}")
            print(f"📁 Local repo directory: {self.local_repo_dir}")
    
    def get_open_pull_requests(self) -> List[Any]:
        """Get all open pull requests."""
        return list(self.repo.get_pulls(state='open'))
    
    def get_pr_comments(self, pr_number: int) -> List[GitHubComment]:
        """Get all comments from a specific pull request."""
        pr = self.repo.get_pull(pr_number)
        comments = []
        
        # Get review comments (file-specific)
        for comment in pr.get_review_comments():
            comments.append(GitHubComment(
                id=comment.id,
                body=comment.body,
                user=comment.user.login,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                file_path=comment.path,
                line_number=comment.line if hasattr(comment, 'line') else comment.original_line,
                pr_number=pr_number
            ))
        
        # Get issue comments (general PR comments)
        for comment in pr.get_issue_comments():
            comments.append(GitHubComment(
                id=comment.id,
                body=comment.body,
                user=comment.user.login,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                pr_number=pr_number
            ))
        
        return comments
    
    def get_all_unaddressed_comments(self) -> List[GitHubComment]:
        """Get all unaddressed comments from all open PRs."""
        all_comments = []
        prs = self.get_open_pull_requests()
        
        if self.debug_mode:
            print(f"📋 Found {len(prs)} open pull request(s)")
        
        for pr in prs:
            comments = self.get_pr_comments(pr.number)
            if self.debug_mode:
                print(f"   PR #{pr.number}: {len(comments)} comment(s)")
            all_comments.extend(comments)
        
        # Filter out comments that are likely resolved (basic heuristic)
        unaddressed = []
        for comment in all_comments:
            # Skip bot comments and author's own comments
            if comment.user.lower() in ['github-actions', 'dependabot', 'renovate']:
                continue
            
            # Check if comment has been addressed (basic check for subsequent commits)
            # This is a simplified approach - in a real implementation you'd want more sophisticated tracking
            unaddressed.append(comment)
        
        return unaddressed
    
    def post_comment_response(self, pr_number: int, comment_id: int, response: str, commit_sha: Optional[str] = None) -> bool:
        """Post a response to a comment."""
        try:
            pr = self.repo.get_pull(pr_number)
            
            # Format response with commit info if provided
            formatted_response = response
            if commit_sha:
                formatted_response += f"\n\n🔄 Addressed in commit: {commit_sha}"
            
            # Post as issue comment (general PR comment)
            pr.create_issue_comment(formatted_response)
            
            if self.debug_mode:
                print(f"✅ Posted response to comment {comment_id} on PR #{pr_number}")
            
            return True
        except Exception as e:
            if self.debug_mode:
                print(f"❌ Failed to post comment response: {e}")
            return False
    
    def setup_repository(self) -> bool:
        """Clone or update the local repository."""
        try:
            if os.path.exists(self.local_repo_dir):
                if self.debug_mode:
                    print(f"📥 Updating existing repository in {self.local_repo_dir}")
                
                # Change to repo directory and fetch latest changes
                os.chdir(self.local_repo_dir)
                subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True)
                
                if self.debug_mode:
                    print("✅ Repository updated successfully")
            else:
                if self.debug_mode:
                    print(f"📥 Cloning repository to {self.local_repo_dir}")
                
                # Clone the repository
                subprocess.run(['git', 'clone', self.clone_url, self.local_repo_dir], 
                             check=True, capture_output=True)
                os.chdir(self.local_repo_dir)
                
                if self.debug_mode:
                    print("✅ Repository cloned successfully")
            
            return True
            
        except subprocess.CalledProcessError as e:
            if self.debug_mode:
                print(f"❌ Failed to setup repository: {e}")
            return False
    
    def switch_to_pr_branch(self, pr_number: int) -> bool:
        """Switch to the branch associated with a specific PR."""
        try:
            # Get PR details
            pr = self.repo.get_pull(pr_number)
            branch_name = pr.head.ref
            
            if self.debug_mode:
                print(f"🔀 Switching to PR branch: {branch_name}")
            
            # Ensure we're in the repo directory
            os.chdir(self.local_repo_dir)
            
            # Fetch the latest changes
            subprocess.run(['git', 'fetch', 'origin'], check=True, capture_output=True)
            
            # Check if branch exists locally
            result = subprocess.run(['git', 'branch', '--list', branch_name], 
                                  capture_output=True, text=True)
            
            if branch_name in result.stdout:
                # Branch exists locally, switch to it
                subprocess.run(['git', 'checkout', branch_name], check=True, capture_output=True)
                # Pull latest changes
                subprocess.run(['git', 'pull', 'origin', branch_name], check=True, capture_output=True)
            else:
                # Branch doesn't exist locally, create and track it
                subprocess.run(['git', 'checkout', '-b', branch_name, f'origin/{branch_name}'], 
                             check=True, capture_output=True)
            
            if self.debug_mode:
                print(f"✅ Successfully switched to branch: {branch_name}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            if self.debug_mode:
                print(f"❌ Failed to switch to PR branch: {e}")
            return False
        except Exception as e:
            if self.debug_mode:
                print(f"❌ Error switching to PR branch: {e}")
            return False
    
    def get_pr_for_comment(self, comment: GitHubComment) -> int:
        """Get the PR number for a given comment."""
        return comment.pr_number
    
    def get_latest_commit_sha(self) -> str:
        """Get the latest commit SHA from the current branch."""
        try:
            # Ensure we're in the repo directory
            os.chdir(self.local_repo_dir)
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown"


async def async_github_mode(github_repo_url: str, working_dir=None, debug_mode=False, enable_retry=False, retry_config=None):
    """
    Async GitHub mode to process PR comments and address them with Claude Code.
    
    Args:
        github_repo_url: GitHub repository URL
        working_dir: Directory to run in (defaults to current directory)
        debug_mode: Enable debug output for technical details
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
    print("🚀 VibeTeam GitHub PR Comment Bot")
    print(f"📁 Working in: {os.getcwd()}")
    print(f"🔗 GitHub repo: {github_repo_url}")
    if debug_mode:
        print("🐛 Debug mode enabled - showing technical details")
    if enable_retry:
        print(f"🔄 Retry mode enabled - max {retry_config.max_attempts} attempts with exponential backoff")
    print()
    
    # Check for required environment variables
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("❌ Error: GITHUB_TOKEN environment variable not set")
        print("💡 Please set GITHUB_TOKEN with a GitHub personal access token")
        return 1
    
    # Initialize GitHub manager
    try:
        github_manager = GitHubPRManager(github_token, github_repo_url, os.getcwd(), debug_mode)
    except Exception as e:
        print(f"❌ Failed to connect to GitHub: {e}")
        return 1
    
    # Setup the repository (clone or update)
    print("📥 Setting up repository...")
    if not github_manager.setup_repository():
        print("❌ Failed to setup repository")
        return 1
    
    # Get all unaddressed comments
    print("🔍 Fetching unaddressed comments from open PRs...")
    unaddressed_comments = github_manager.get_all_unaddressed_comments()
    
    if not unaddressed_comments:
        print("✅ No unaddressed comments found in open PRs!")
        return 0
    
    print(f"📋 Found {len(unaddressed_comments)} unaddressed comment(s)")
    print()
    
    # Group comments by PR to minimize branch switching
    comments_by_pr = {}
    for comment in unaddressed_comments:
        pr_num = comment.pr_number
        if pr_num not in comments_by_pr:
            comments_by_pr[pr_num] = []
        comments_by_pr[pr_num].append(comment)
    
    print(f"📊 Comments span {len(comments_by_pr)} PR(s)")
    print()
    
    # Process comments grouped by PR
    comment_count = 0
    for pr_number, pr_comments in comments_by_pr.items():
        print(f"🔀 Processing PR #{pr_number} ({len(pr_comments)} comment(s))")
        
        # Switch to the PR branch
        if not github_manager.switch_to_pr_branch(pr_number):
            print(f"❌ Failed to switch to PR #{pr_number} branch, skipping...")
            continue
        
        # Process each comment in this PR
        for comment in pr_comments:
            comment_count += 1
            print(f"🎯 Processing comment {comment_count}/{len(unaddressed_comments)}")
            print(f"   👤 Author: {comment.user}")
            print(f"   📄 File: {comment.file_path or 'General PR comment'}")
            print(f"   📝 Content: {comment.body[:100]}{'...' if len(comment.body) > 100 else ''}")
            print("-" * 50)
            
            # Create comprehensive task prompt for Claude Code to analyze and address the comment
            task_prompt = f"""You are addressing a GitHub PR comment. Your task is to:

1. ANALYZE the comment to understand what action is needed
2. ADDRESS the comment appropriately (fix code, answer question, or respond)
3. PROVIDE a clear response for GitHub

PR Comment Details:
- Author: {comment.user}
- File: {comment.file_path or 'General PR comment'}
- Line: {comment.line_number or 'N/A'}
- Comment: {comment.body}

Instructions:
1. First, analyze the comment to determine what type of response is needed:
   - Does it suggest a bug fix or code improvement? → Implement the fix
   - Does it ask a question about the code? → Research and provide a clear answer
   - Is it a style/formatting suggestion? → Make the suggested changes if reasonable
   - Is it a general discussion point? → Provide a thoughtful response

2. If code changes are needed:
   - Read the relevant files to understand the context
   - Implement the suggested changes or fixes
   - Run any relevant tests to ensure the changes work
   - Commit your changes with a clear commit message

3. Always prepare a response that will be posted to GitHub explaining:
   - What you understood from the comment
   - What action you took (if any)
   - Any relevant details or explanations

4. Your response should be professional and helpful, addressing the commenter directly

Focus on being thorough and providing value to the code review process."""
            
            # Execute the task with Claude Code
            max_attempts = retry_config.max_attempts if enable_retry else 1
            attempt = 0
            task_completed_successfully = False
            response_text = ""
            commit_sha = None
            
            while attempt < max_attempts and not task_completed_successfully:
                attempt += 1
                
                if attempt > 1:
                    print(f"🔄 Retry attempt {attempt}/{max_attempts}")
                
                try:
                    claude_agent = ClaudeCodeAgent(
                        working_directory=github_manager.local_repo_dir,
                        permission_mode="bypassPermissions",
                        debug_mode=debug_mode,
                    )
                    
                    # Execute the task
                    execution_result = await claude_agent.execute_task({
                        "description": task_prompt
                    })
                    
                    # Get the response from execution result
                    if hasattr(execution_result, 'output') and execution_result.output:
                        response_text = str(execution_result.output)
                    else:
                        response_text = "I have reviewed and addressed your comment. Thank you for the feedback!"
                    
                    # Check for errors
                    if hasattr(execution_result, 'errors') and execution_result.errors:
                        error_messages = ' '.join(execution_result.errors)
                        
                        should_retry, error_pattern = retry_manager.should_retry_error(error_messages)
                        if enable_retry and should_retry and attempt < max_attempts:
                            delay = retry_manager.calculate_delay(attempt, error_pattern)
                            retry_manager.log_retry_attempt(attempt, max_attempts, error_messages, delay, error_pattern)
                            if delay > 0:
                                await asyncio.sleep(delay)
                            continue
                        else:
                            response_text = f"I reviewed your comment but encountered some issues during execution. The main points have been noted: {error_messages}"
                    
                    task_completed_successfully = True
                    
                    # Log successful retry if this was a retry attempt
                    if attempt > 1 and enable_retry:
                        retry_manager.log_retry_success()
                    
                    # Get the latest commit SHA if code changes were made
                    commit_sha = github_manager.get_latest_commit_sha()
                    
                except Exception as e:
                    print(f"❌ Task execution failed: {e}")
                    should_retry, error_pattern = retry_manager.should_retry_error(str(e))
                    if enable_retry and should_retry and attempt < max_attempts:
                        delay = retry_manager.calculate_delay(attempt, error_pattern)
                        retry_manager.log_retry_attempt(attempt, max_attempts, str(e), delay, error_pattern)
                        if delay > 0:
                            await asyncio.sleep(delay)
                        continue
                    else:
                        response_text = f"Thank you for your comment. I encountered a technical issue while processing it: {str(e)}. Please review manually."
                        task_completed_successfully = True
            
            # Post response to GitHub (always post a response)
            print("📤 Posting response to GitHub...")
            success = github_manager.post_comment_response(
                comment.pr_number, 
                comment.id, 
                response_text, 
                commit_sha if commit_sha != "unknown" else None
            )
            
            if success:
                print("✅ Response posted successfully")
            else:
                print("❌ Failed to post response")
            
            print("=" * 50)
            print()
    
    print(f"🎉 Completed processing {len(unaddressed_comments)} comment(s)!")
    
    # Display retry statistics if retries were enabled
    if enable_retry and retry_manager:
        retry_manager.print_retry_summary()
    
    return 0


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
                if last_error and enable_retry:
                    should_retry, _ = retry_manager.should_retry_error(str(last_error))
                    if should_retry:
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
                    should_retry, error_pattern = retry_manager.should_retry_error(error_messages)
                    if enable_retry and should_retry:
                        if attempt < max_attempts:
                            # Calculate and wait for retry delay
                            delay = retry_manager.calculate_delay(attempt, error_pattern)
                            retry_manager.log_retry_attempt(attempt, max_attempts, error_messages, delay, error_pattern)
                            
                            if delay > 0:
                                await asyncio.sleep(delay)
                            continue
                        else:
                            retry_manager.log_retry_failure(error_messages)
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
                    
                    # Log successful retry if this was a retry attempt
                    if attempt > 1 and enable_retry:
                        retry_manager.log_retry_success()
                    
            except Exception as e:
                last_error = str(e)
                print(f"❌ Task execution failed: {last_error}")
                
                # Check if this is a retryable error
                should_retry, error_pattern = retry_manager.should_retry_error(last_error)
                if enable_retry and should_retry and attempt < max_attempts:
                    delay = retry_manager.calculate_delay(attempt, error_pattern)
                    retry_manager.log_retry_attempt(attempt, max_attempts, last_error, delay, error_pattern)
                    
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue
                else:
                    # Non-retryable error or max attempts reached
                    if should_retry and attempt >= max_attempts:
                        retry_manager.log_retry_failure(last_error)
                    else:
                        print(f"💥 Task failed after {attempt} attempt(s): Non-retryable error")
                    break

        # After the agent runs, we'd expect the tasks file to be modified.
        # The loop will then re-read the file and check for remaining tasks.
        print("=" * 50)
        print("🔄 Task cycle completed! Checking for remaining tasks...")
        print()
    
    # Display retry statistics if retries were enabled
    if enable_retry and retry_manager:
        retry_manager.print_retry_summary()
    
    return 0


def main():
    """
    Console script entry point for vibeteam-task command.
    """
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="VibeTeam automated task completion from a tasks file or GitHub PR comments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Task file mode (default)
  vibeteam-task                           # Run in current directory with tasks.md
  vibeteam-task --dir /path/to/project    # Run in specific directory
  vibeteam-task --tasks-file my-tasks.md # Use custom tasks file
  vibeteam-task -t todo.txt -d /project   # Custom file and directory
  vibeteam-task --enable-reflection       # Enable OpenAI reflection analysis
  vibeteam-task --retry                   # Enable retry for usage limits/timeouts
  vibeteam-task --retry --max-attempts 5  # Retry up to 5 times
  vibeteam-task --retry --base-delay 120  # Wait 2 minutes before first retry
  
  # GitHub mode
  vibeteam-task --github-repo https://github.com/owner/repo
  vibeteam-task --github-repo owner/repo --retry
  vibeteam-task --github-repo https://github.com/owner/repo --debug
  
Task file mode: The tool will read the tasks file and complete unchecked tasks:
  [ ] Write python hello world hello.py
  [ ] Create a REST API endpoint

GitHub mode: The tool will:
1. Clone/update the repository locally (in current directory)
2. Fetch all open pull requests from the specified repository
3. Group comments by PR and switch to appropriate branches
4. Use Claude Code to analyze and address each comment (fix code or provide response)
5. Post responses back to GitHub with commit SHA if changes were made

Environment variables:
- GITHUB_TOKEN: Required for GitHub mode (GitHub personal access token)
- OPENAI_API_KEY: Required for task reflection mode (task file mode only)

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
        help="Path to tasks file (default: tasks.md) - ignored in GitHub mode"
    )
    parser.add_argument(
        "--github-repo",
        metavar="URL_OR_PATH",
        help="GitHub repository URL or owner/repo path (enables GitHub mode)"
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
        # Determine mode based on arguments
        if args.github_repo:
            # GitHub mode
            exit_code = asyncio.run(async_github_mode(
                github_repo_url=args.github_repo,
                working_dir=args.dir, 
                debug_mode=args.debug, 
                enable_retry=args.retry,
                retry_config=retry_config
            ))
        else:
            # Task file mode
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
