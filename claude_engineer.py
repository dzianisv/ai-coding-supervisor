#!/usr/bin/env python3
"""
Claude Code Supervisor using claude-code-sdk-python
Simplified version that leverages the SDK for cleaner interaction
"""

import asyncio
import sys
import re
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, AsyncIterator
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import argparse
from pathlib import Path

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'claude-code-sdk-python', 'src'))

from claude_code_sdk import (
    query,
    ClaudeCodeOptions,
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    CLINotFoundError,
    ProcessError,
)

class TaskState(Enum):
    INITIALIZING = "initializing"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"
    STALLED = "stalled"
    VERIFYING = "verifying"

@dataclass
class CompletionVerification:
    """Track completion verification attempts"""
    verification_count: int = 0
    last_verification_time: float = 0
    verification_questions: List[str] = field(default_factory=list)
    found_issues: bool = False

    def reset(self):
        """Reset verification when task found incomplete"""
        self.verification_count = 0
        self.found_issues = True
        self.verification_questions.clear()

@dataclass
class TaskProgress:
    todos_total: int = 0
    todos_completed: int = 0
    test_cases: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    current_phase: str = ""
    state: TaskState = TaskState.INITIALIZING
    last_action: str = ""
    last_action_time: float = 0
    completion_verification: CompletionVerification = field(default_factory=CompletionVerification)

@dataclass
class SupervisorMetrics:
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    continues_sent: int = 0
    user_inputs_sent: int = 0
    errors_detected: int = 0
    state_changes: List[Tuple[float, TaskState]] = field(default_factory=list)
    total_cost_usd: float = 0.0

    @property
    def duration(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

class PatternMatcher:
    """Advanced pattern matching with confidence scoring"""

    def __init__(self):
        self.patterns = {
            'waiting': [
                (r"Would you like me to (continue|proceed|fix)", 0.9),
                (r"Should I (continue|proceed|update|fix|implement)", 0.9),
                (r"Do you want me to", 0.85),
                (r"Shall I", 0.85),
                (r"Next steps (would be|are|include)", 0.8),
                (r"I (can|could|should) (now|next)", 0.7),
                (r"waiting for (user|your) (input|response)", 0.95),
            ],
            'error': [
                (r"(CRITICAL|FATAL) (ERROR|FAILURE)", 1.0),
                (r"❌ .*(failed|error|not working)", 0.8),
                (r"Still (failing|not working)", 0.8),
                (r"cannot (proceed|continue)", 0.9),
            ],
            'progress': [
                (r"☐ (Fix|Create|Implement|Test|Verify|Debug)", 0.7),
                (r"☒ .*(completed|done|fixed)", 0.8),
                (r"Step \d+/\d+", 0.6),
                (r"Processing \d+%", 0.7),
            ],
            'completion': [
                (r"✅ All \d+ test cases? passed", 0.95),
                (r"☒ All tasks completed", 0.95),
                (r"Task completed successfully", 0.9),
                (r"Everything is working (correctly|as expected)", 0.9),
                (r"Successfully completed all", 0.95),
                (r"All automation (tasks|scenarios) (completed|working)", 0.9),
                (r"implementation (is )?complete", 0.8),
                (r"(task|work|implementation) (is )?(done|finished|complete)", 0.8),
            ],
            'incomplete_realization': [
                (r"(actually|still) (not|isn't|hasn't) (working|completed|done)", 0.9),
                (r"(need|needs) to (fix|implement|debug)", 0.85),
                (r"(found|discovered|noticed) (issue|problem|error)", 0.9),
                (r"let me (fix|check|verify) that", 0.8),
                (r"I (should|need to) (check|verify|test)", 0.8),
                (r"(further|additional) testing needed", 0.9),
                (r"needs? (more|further|additional) (testing|verification)", 0.85),
            ]
        }

        self.verification_questions = [
            "Are you absolutely sure the task is complete? Please verify:\n1. Did you run all tests and check they actually pass?\n2. Did you analyze the test outputs/logs for any errors?\n3. Did you verify screenshots show the expected behavior?\n\nPlease double-check now.",
            "I need you to be 100% certain. Please confirm:\n1. Have you examined ALL test results, not just the summary?\n2. Did you look at actual screenshots/outputs to verify success?\n3. Are there any warnings or errors you might have missed?\n\nTake a moment to thoroughly review everything.",
            "Before we conclude, one final verification:\n1. Can you show me specific evidence (logs/screenshots) that prove each test case works?\n2. Did the automation actually perform the expected actions (not just attempt them)?\n3. Is there ANYTHING that might not be working correctly?\n\nPlease provide concrete evidence of completion."
        ]

    def match(self, text: str, category: str) -> Tuple[bool, float]:
        """Match text against patterns in category, return (matched, confidence)"""
        max_confidence = 0.0
        matched = False

        for pattern, confidence in self.patterns.get(category, []):
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                matched = True
                max_confidence = max(max_confidence, confidence)

        return matched, max_confidence

class ClaudeCodeSupervisor:
    def __init__(self,
                 task_description: Optional[str] = None,
                 auto_continue: bool = True,
                 max_continues: int = 100,
                 log_file: Optional[str] = None,
                 verbose: bool = False,
                 continue_delay: float = 3.0,
                 stall_timeout: float = 300.0,
                 verify_completion: bool = True,
                 verification_attempts: int = 3,
                 working_directory: Optional[str] = None,
                 allowed_tools: Optional[List[str]] = None,
                 system_prompt: Optional[str] = None,
                 model: Optional[str] = None,
                 permission_mode: Optional[str] = None,
                 resume_session: Optional[str] = None):

        self.task_description = task_description
        self.auto_continue = auto_continue
        self.max_continues = max_continues
        self.log_file = log_file or f"claude_supervisor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.verbose = verbose
        self.continue_delay = continue_delay
        self.stall_timeout = stall_timeout
        self.verify_completion = verify_completion
        self.verification_attempts = verification_attempts
        self.working_directory = working_directory
        self.allowed_tools = allowed_tools or []
        self.system_prompt = system_prompt
        self.model = model
        self.permission_mode = permission_mode
        self.resume_session = resume_session

        # Core components
        self.matcher = PatternMatcher()
        self.progress = TaskProgress()
        self.metrics = SupervisorMetrics()

        # Message history
        self.message_history = deque(maxlen=1000)
        self.recent_output = deque(maxlen=100)

        # State
        self.running = True
        self.in_verification = False
        self.session_id: Optional[str] = None
        self.last_message_time = time.time()

    async def log(self, level: str, message: str, data: Optional[Dict] = None):
        """Async logging"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'data': data or {}
        }

        # Write to log file
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass

        if self.verbose or level in ['ERROR', 'WARNING']:
            prefix = f"[SUPERVISOR-{level}]"
            print(f"\n{prefix} {message}", file=sys.stderr)
            if data and self.verbose:
                print(f"{prefix} Data: {json.dumps(data, indent=2)}", file=sys.stderr)

    def extract_text_from_message(self, message: AssistantMessage) -> str:
        """Extract all text from an assistant message"""
        text_parts = []
        for block in message.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif isinstance(block, ToolUseBlock):
                text_parts.append(f"[Tool Use: {block.name}]")
            elif isinstance(block, ToolResultBlock):
                if block.content:
                    text_parts.append(f"[Tool Result: {block.content}]")
        return "\n".join(text_parts)

    async def analyze_state(self, text: str) -> TaskState:
        """Analyze text to determine current state"""
        # Check patterns with confidence
        is_complete, complete_conf = self.matcher.match(text, 'completion')
        is_error, error_conf = self.matcher.match(text, 'error')
        is_waiting, wait_conf = self.matcher.match(text, 'waiting')
        has_progress, _ = self.matcher.match(text, 'progress')
        is_incomplete, incomplete_conf = self.matcher.match(text, 'incomplete_realization')

        # First check if Claude is being honest about incompleteness
        if is_incomplete and incomplete_conf > 0.8:
            await self.log('INFO', f"Claude admits task is incomplete (confidence: {incomplete_conf:.2f})")
            return TaskState.WAITING

        # If claiming completion, verify it
        if is_complete and complete_conf > 0.8 and self.progress.state != TaskState.COMPLETED:
            if self.verify_completion and not self.in_verification:
                return TaskState.VERIFYING
            else:
                return TaskState.COMPLETED

        # Normal state determination
        if is_error and error_conf > 0.7:
            return TaskState.ERROR
        elif is_waiting and wait_conf > 0.6:
            return TaskState.WAITING
        elif has_progress:
            return TaskState.WORKING
        else:
            # Check for stall
            if time.time() - self.last_message_time > self.stall_timeout:
                return TaskState.STALLED
            return self.progress.state

    async def should_continue(self) -> Tuple[bool, str]:
        """Determine if we should send continue"""
        if self.metrics.continues_sent >= self.max_continues:
            return False, "Max continues reached"

        if self.progress.state == TaskState.VERIFYING:
            return False, "In verification phase"

        if self.progress.state == TaskState.COMPLETED:
            return False, "Task completed and verified"

        if self.progress.state == TaskState.ERROR:
            recent_text = ''.join(self.recent_output)
            if "retry" in recent_text.lower() or "fixing" in recent_text.lower():
                return True, "Attempting to recover from error"
            return False, "Unrecoverable error detected"

        if self.progress.state == TaskState.WAITING:
            if self.progress.todos_total > self.progress.todos_completed:
                return True, f"TODOs remaining: {self.progress.todos_total - self.progress.todos_completed}"

            failed_tests = [name for name, passed in self.progress.test_cases.items() if not passed]
            if failed_tests:
                return True, f"Failed tests: {', '.join(failed_tests[:3])}"

            return True, "Claude is waiting for input"

        if self.progress.state == TaskState.STALLED:
            return True, "Process appears stalled, attempting to continue"

        return False, "No clear indication to continue"

    def extract_progress(self, text: str) -> Dict[str, Any]:
        """Extract progress indicators from text"""
        updates = {}

        # Extract TODO counts
        completed = len(re.findall(r'☒', text))
        pending = len(re.findall(r'☐', text))
        if completed + pending > 0:
            updates['todos_completed'] = completed
            updates['todos_total'] = completed + pending

        # Extract test results
        test_patterns = [
            r'(✅|❌)\s+(.+?):\s*(PASSED|FAILED|Working|Not working)',
            r'Test[:\s]+(.+?)\s*[-:]\s*(✅|❌)',
        ]

        test_results = {}
        for pattern in test_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                test_name = match[1] if '✅' in match[0] or '❌' in match[0] else match[0]
                passed = '✅' in str(match) or 'PASSED' in str(match)
                test_results[test_name.strip()] = passed

        if test_results:
            updates['test_cases'] = test_results

        # Extract phase/step
        phase_match = re.search(r'(Step|Phase|Stage)\s+(\d+)', text, re.IGNORECASE)
        if phase_match:
            updates['current_phase'] = phase_match.group(0)

        return updates

    async def send_verification_question(self, question_idx: int) -> str:
        """Send verification question and get response"""
        question = self.matcher.verification_questions[question_idx]
        
        await self.log('INFO', f"Sending verification question {question_idx + 1}/{self.verification_attempts}")
        
        # Send the verification question
        options = ClaudeCodeOptions(
            system_prompt=self.system_prompt,
            allowed_tools=self.allowed_tools,
            model=self.model,
            permission_mode=self.permission_mode,
            cwd=self.working_directory,
            resume=self.session_id,  # Resume the same session
            max_turns=1  # Single turn for verification
        )
        
        full_response = ""
        async for message in query(prompt=question, options=options):
            if isinstance(message, AssistantMessage):
                response_text = self.extract_text_from_message(message)
                full_response += response_text
                print(response_text)
            elif isinstance(message, ResultMessage):
                if message.total_cost_usd:
                    self.metrics.total_cost_usd += message.total_cost_usd
                self.session_id = message.session_id
        
        return full_response

    async def handle_completion_claim(self) -> bool:
        """Handle when Claude claims completion. Returns True if actually complete."""
        if not self.verify_completion:
            return True

        verification = self.progress.completion_verification

        # Check if we've already verified enough times
        if verification.verification_count >= self.verification_attempts:
            await self.log('INFO', f"Completion verified after {verification.verification_count} checks")
            return True

        # Enter verification state
        self.progress.state = TaskState.VERIFYING
        self.in_verification = True

        await self.log('INFO', f"Challenging completion claim (attempt {verification.verification_count + 1}/{self.verification_attempts})")

        # Send verification question and get response
        response = await self.send_verification_question(verification.verification_count)
        
        verification.verification_count += 1
        verification.last_verification_time = time.time()

        # Analyze response
        found_incomplete, confidence = self.matcher.match(response, 'incomplete_realization')

        if found_incomplete and confidence > 0.7:
            await self.log('INFO', "Claude realized task is incomplete, resetting verification")
            verification.reset()
            self.progress.state = TaskState.WORKING
            self.in_verification = False
            return False

        # Check if Claude is still claiming completion
        still_complete, complete_conf = self.matcher.match(response, 'completion')

        if still_complete and complete_conf > 0.8:
            # Continue verification or accept completion
            if verification.verification_count < self.verification_attempts:
                return await self.handle_completion_claim()
            else:
                # Verified multiple times, accept completion
                self.progress.state = TaskState.COMPLETED
                self.in_verification = False
                return True

        # If unclear, continue working
        self.progress.state = TaskState.WORKING
        self.in_verification = False
        return False

    async def run_query(self, prompt: str, continue_session: bool = False) -> bool:
        """Run a single query and process responses. Returns True if completed."""
        options = ClaudeCodeOptions(
            system_prompt=self.system_prompt,
            allowed_tools=self.allowed_tools,
            model=self.model,
            permission_mode=self.permission_mode,
            cwd=self.working_directory,
            resume=self.session_id if continue_session else self.resume_session,
            continue_conversation=continue_session,
            max_turns=None  # Let Claude decide when to stop
        )

        try:
            full_text = ""
            
            async for message in query(prompt=prompt, options=options):
                self.last_message_time = time.time()
                
                if isinstance(message, UserMessage):
                    print(f"\nUser: {message.content}")
                    self.message_history.append(("user", message.content))
                    
                elif isinstance(message, AssistantMessage):
                    text = self.extract_text_from_message(message)
                    print(text)
                    self.message_history.append(("assistant", text))
                    self.recent_output.append(text)
                    full_text += text + "\n"
                    
                    # Extract progress
                    progress_updates = self.extract_progress(text)
                    for key, value in progress_updates.items():
                        setattr(self.progress, key, value)
                    
                elif isinstance(message, SystemMessage):
                    await self.log('DEBUG', f"System message: {message.subtype}", message.data)
                    
                elif isinstance(message, ResultMessage):
                    self.session_id = message.session_id
                    if message.total_cost_usd:
                        self.metrics.total_cost_usd += message.total_cost_usd
                    
                    await self.log('INFO', f"Query completed", {
                        'duration_ms': message.duration_ms,
                        'cost_usd': message.total_cost_usd,
                        'session_id': message.session_id,
                        'num_turns': message.num_turns
                    })
                    
                    if message.is_error:
                        self.metrics.errors_detected += 1
                        self.progress.state = TaskState.ERROR
                        return False

            # Update state based on full response
            if full_text:
                new_state = await self.analyze_state(full_text)
                if new_state != self.progress.state:
                    old_state = self.progress.state
                    self.progress.state = new_state
                    self.metrics.state_changes.append((time.time(), new_state))
                    await self.log('INFO', f"State changed from {old_state.value} to {new_state.value}")
                
                # Handle completion claims
                if new_state == TaskState.VERIFYING:
                    is_verified = await self.handle_completion_claim()
                    if is_verified:
                        self.progress.state = TaskState.COMPLETED
                        return True

            return self.progress.state == TaskState.COMPLETED
            
        except CLINotFoundError as e:
            await self.log('ERROR', f"Claude Code not found: {e}")
            raise
        except ProcessError as e:
            await self.log('ERROR', f"Process error: {e}")
            self.metrics.errors_detected += 1
            self.progress.state = TaskState.ERROR
            return False
        except Exception as e:
            await self.log('ERROR', f"Unexpected error: {e}")
            self.metrics.errors_detected += 1
            return False

    async def generate_report(self):
        """Generate final report"""
        report = {
            'task_description': self.task_description,
            'start_time': datetime.fromtimestamp(self.metrics.start_time).isoformat(),
            'end_time': datetime.fromtimestamp(self.metrics.end_time or time.time()).isoformat(),
            'duration_seconds': self.metrics.duration,
            'final_state': self.progress.state.value,
            'total_cost_usd': self.metrics.total_cost_usd,
            'verification': {
                'enabled': self.verify_completion,
                'attempts': self.progress.completion_verification.verification_count,
                'found_issues': self.progress.completion_verification.found_issues,
            },
            'metrics': {
                'continues_sent': self.metrics.continues_sent,
                'user_inputs_sent': self.metrics.user_inputs_sent,
                'errors_detected': self.metrics.errors_detected,
            },
            'progress': {
                'todos_completed': self.progress.todos_completed,
                'todos_total': self.progress.todos_total,
                'test_results': self.progress.test_cases,
            },
            'state_timeline': [
                {'time': t, 'state': s.value}
                for t, s in self.metrics.state_changes
            ],
            'session_id': self.session_id
        }

        report_file = self.log_file.replace('.log', '_report.json')
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        return report_file

    async def run(self):
        """Main supervisor execution"""
        print(f"[SUPERVISOR] Claude Code Supervisor (SDK Version)", file=sys.stderr)
        print(f"[SUPERVISOR] Task: {self.task_description or 'Not specified'}", file=sys.stderr)
        print(f"[SUPERVISOR] Auto-continue: {'ON' if self.auto_continue else 'OFF'}", file=sys.stderr)
        print(f"[SUPERVISOR] Completion verification: {'ON' if self.verify_completion else 'OFF'}", file=sys.stderr)
        print(f"[SUPERVISOR] Max continues: {self.max_continues}", file=sys.stderr)
        print(f"[SUPERVISOR] Continue delay: {self.continue_delay}s", file=sys.stderr)
        print(f"[SUPERVISOR] Working directory: {self.working_directory or 'Current directory'}", file=sys.stderr)
        print(f"[SUPERVISOR] Log file: {self.log_file}", file=sys.stderr)
        print("-" * 80, file=sys.stderr)

        await self.log('INFO', "Started")

        try:
            # Initial query with task description
            initial_prompt = self.task_description or "continue"
            completed = await self.run_query(initial_prompt, continue_session=False)

            # Auto-continue loop
            while not completed and self.auto_continue and self.running:
                # Wait before checking if we should continue
                await asyncio.sleep(self.continue_delay)
                
                should_cont, reason = await self.should_continue()
                
                if should_cont and self.metrics.continues_sent < self.max_continues:
                    self.metrics.continues_sent += 1
                    await self.log('INFO', f"Auto-continue #{self.metrics.continues_sent}: {reason}")
                    
                    # Send continue
                    completed = await self.run_query("continue", continue_session=True)
                else:
                    # No reason to continue or max continues reached
                    await self.log('INFO', f"Stopping: {reason}")
                    break

            self.metrics.end_time = time.time()

            # Generate report
            report_file = await self.generate_report()

            print(f"\n[SUPERVISOR] Session completed", file=sys.stderr)
            print(f"[SUPERVISOR] Duration: {self.metrics.duration:.1f} seconds", file=sys.stderr)
            print(f"[SUPERVISOR] Final state: {self.progress.state.value}", file=sys.stderr)
            print(f"[SUPERVISOR] Continues sent: {self.metrics.continues_sent}", file=sys.stderr)
            print(f"[SUPERVISOR] Total cost: ${self.metrics.total_cost_usd:.4f}", file=sys.stderr)
            if self.verify_completion:
                print(f"[SUPERVISOR] Verification attempts: {self.progress.completion_verification.verification_count}", file=sys.stderr)
            print(f"[SUPERVISOR] Report saved: {report_file}", file=sys.stderr)

        except KeyboardInterrupt:
            await self.log('INFO', "Interrupted by user")
            self.running = False
        except Exception as e:
            await self.log('ERROR', f"Fatal error: {e}")
            raise

async def main():
    parser = argparse.ArgumentParser(
        description='Claude Code Supervisor using SDK'
    )
    parser.add_argument('-t', '--task', help='Task description')
    parser.add_argument('-m', '--max-continues', type=int, default=100,
                        help='Maximum number of auto-continues')
    parser.add_argument('-d', '--delay', type=float, default=3.0,
                        help='Delay before auto-continue (seconds)')
    parser.add_argument('-s', '--stall-timeout', type=float, default=300.0,
                        help='Time before considering process stalled (seconds)')
    parser.add_argument('--no-auto', action='store_true',
                        help='Disable auto-continue')
    parser.add_argument('--no-verify', action='store_true',
                        help='Disable completion verification')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose logging')
    parser.add_argument('-l', '--log-file', help='Custom log file path')
    parser.add_argument('--verify-attempts', type=int, default=3,
                        help='Number of verification attempts (default: 3)')
    parser.add_argument('-w', '--working-directory', help='Working directory for Claude')
    parser.add_argument('--tools', nargs='+', help='Allowed tools (e.g., Read Write Edit)')
    parser.add_argument('--system-prompt', help='System prompt for Claude')
    parser.add_argument('--model', help='Model to use (e.g., claude-3-5-sonnet-20241022)')
    parser.add_argument('--permission-mode', choices=['default', 'acceptEdits', 'bypassPermissions'],
                        help='Permission mode for tool use', default='bypassPermissions')
    parser.add_argument('--resume', help='Resume a previous session by ID')

    args = parser.parse_args()

    supervisor = ClaudeCodeSupervisor(
        task_description=args.task,
        auto_continue=not args.no_auto,
        max_continues=args.max_continues,
        log_file=args.log_file,
        verbose=args.verbose,
        continue_delay=args.delay,
        stall_timeout=args.stall_timeout,
        verify_completion=not args.no_verify,
        verification_attempts=args.verify_attempts,
        working_directory=args.working_directory,
        allowed_tools=args.tools,
        system_prompt=args.system_prompt,
        model=args.model,
        permission_mode=args.permission_mode,
        resume_session=args.resume
    )

    await supervisor.run()

if __name__ == '__main__':
    asyncio.run(main()) 