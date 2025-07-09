#!/usr/bin/env python3
"""
Advanced Claude-Code Supervisor with Completion Verification
Fixed version with proper stdin/stdout piping
"""

import asyncio
import sys
import re
import time
import json
import os
import select
import pty
import fcntl
import struct
import termios
import tty
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import argparse
import signal
import threading

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
                (r"Press Ctrl\+C when done", 0.9),
            ],
            'error': [
                (r"(CRITICAL|FATAL) (ERROR|FAILURE)", 1.0),
                (r"❌ .*(failed|error|not working)", 0.8),
                (r"automation (isn't|is not) (working|executing)", 0.85),
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
                (r"FINAL SUMMARY.*completed", 0.8),
            ],
            'incomplete_realization': [
                (r"(actually|still) (not|isn't|hasn't) (working|completed|done)", 0.9),
                (r"(need|needs) to (fix|implement|debug)", 0.85),
                (r"(found|discovered|noticed) (issue|problem|error)", 0.9),
                (r"let me (fix|check|verify) that", 0.8),
                (r"you're right", 0.7),
                (r"I (should|need to) (check|verify|test)", 0.8),
            ]
        }

        # Verification questions for different scenarios
        self.verification_questions = [
            {
                "question": "Are you absolutely sure the task is complete? Please verify:\n1. Did you run all tests and check they actually pass?\n2. Did you analyze the test outputs/logs for any errors?\n3. Did you verify screenshots show the expected behavior?\n\nPlease double-check now.",
                "keywords": ["test", "verify", "check", "analyze"]
            },
            {
                "question": "I need you to be 100% certain. Please confirm:\n1. Have you examined ALL test results, not just the summary?\n2. Did you look at actual screenshots/outputs to verify success?\n3. Are there any warnings or errors you might have missed?\n\nTake a moment to thoroughly review everything.",
                "keywords": ["examine", "screenshots", "outputs", "warnings"]
            },
            {
                "question": "Before we conclude, one final verification:\n1. Can you show me specific evidence (logs/screenshots) that prove each test case works?\n2. Did the automation actually perform the expected actions (not just attempt them)?\n3. Is there ANYTHING that might not be working correctly?\n\nPlease provide concrete evidence of completion.",
                "keywords": ["evidence", "prove", "concrete", "specific"]
            }
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

class AdvancedClaudeCodeSupervisor:
    def __init__(self,
                 command: List[str],
                 task_description: Optional[str] = None,
                 auto_continue: bool = True,
                 max_continues: int = 100,
                 log_file: Optional[str] = None,
                 verbose: bool = False,
                 continue_delay: float = 3.0,
                 stall_timeout: float = 300.0,
                 verify_completion: bool = True,
                 verification_attempts: int = 3):

        self.command = command
        self.task_description = task_description
        self.auto_continue = auto_continue
        self.max_continues = max_continues
        self.log_file = log_file or f"claude_supervisor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.verbose = verbose
        self.continue_delay = continue_delay
        self.stall_timeout = stall_timeout
        self.verify_completion = verify_completion
        self.verification_attempts = verification_attempts

        # Core components
        self.process: Optional[asyncio.subprocess.Process] = None
        self.matcher = PatternMatcher()
        self.progress = TaskProgress()
        self.metrics = SupervisorMetrics()
        
        # PTY handling
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None

        # Buffers
        self.output_buffer = deque(maxlen=500)
        self.recent_output = deque(maxlen=100)
        self.command_history = deque(maxlen=50)

        # State
        self.last_output_time = time.time()
        self.last_continue_time = 0
        self.running = True
        self.in_verification = False

        # Threading for stdin handling
        self.stdin_thread = None
        self.stop_stdin_thread = threading.Event()

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

    def start_stdin_thread(self):
        """Start thread to handle stdin forwarding using PTY"""
        def stdin_forwarder():
            # Set stdin to raw mode for proper terminal handling
            old_settings = None
            try:
                old_settings = termios.tcgetattr(sys.stdin)
                tty.setraw(sys.stdin.fileno())
            except Exception:
                pass
            
            try:
                while not self.stop_stdin_thread.is_set() and self.master_fd is not None:
                    try:
                        # Use select to check if stdin has data
                        ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                        if ready:
                            try:
                                data = os.read(sys.stdin.fileno(), 1024)
                                if data:
                                    # Check for supervisor commands (Ctrl+/ prefix)
                                    if data == b'\x1f':  # Ctrl+/ (0x1f)
                                        # Read the rest of the command
                                        try:
                                            cmd_data = os.read(sys.stdin.fileno(), 64)
                                            command = cmd_data.decode('utf-8', errors='ignore').strip()
                                            if command:
                                                asyncio.run_coroutine_threadsafe(
                                                    self.handle_command('/' + command),
                                                    self.loop
                                                )
                                                continue
                                        except Exception:
                                            pass
                                    
                                    # Forward all other input to PTY
                                    os.write(self.master_fd, data)
                                    self.last_output_time = time.time()
                                    
                                    # Track user input for metrics
                                    if b'\n' in data or b'\r' in data:
                                        self.metrics.user_inputs_sent += 1
                                        
                            except (BlockingIOError, OSError):
                                pass
                            except Exception as e:
                                if self.verbose:
                                    print(f"[SUPERVISOR-ERROR] PTY write error: {e}", file=sys.stderr)
                                
                    except Exception as e:
                        if self.verbose:
                            print(f"[SUPERVISOR-ERROR] Stdin error: {e}", file=sys.stderr)
                        time.sleep(0.1)
            finally:
                # Restore original terminal settings
                if old_settings:
                    try:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    except Exception:
                        pass

        self.stdin_thread = threading.Thread(target=stdin_forwarder, daemon=True)
        self.stdin_thread.start()

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

        # Get the appropriate verification question
        question_data = self.matcher.verification_questions[verification.verification_count]
        question = question_data["question"]

        await self.log('INFO', f"Challenging completion claim (attempt {verification.verification_count + 1}/{self.verification_attempts})")

        # Send verification question
        print(f"\n[SUPERVISOR-VERIFY] Questioning completion claim...", file=sys.stderr)

        try:
            if self.master_fd is not None:
                os.write(self.master_fd, f"\n{question}\n".encode())
            else:
                await self.log('ERROR', "PTY not available for verification question")
                return False
        except Exception as e:
            await self.log('ERROR', f"Failed to send verification question: {e}")
            return False

        verification.verification_count += 1
        verification.last_verification_time = time.time()
        verification.verification_questions.append(question)

        # Clear buffers to analyze fresh response
        self.recent_output.clear()

        return False

    async def analyze_verification_response(self, text: str) -> bool:
        """Analyze response to verification question"""
        # Check if Claude realized the task isn't complete
        found_incomplete, confidence = self.matcher.match(text, 'incomplete_realization')

        if found_incomplete and confidence > 0.7:
            await self.log('INFO', "Claude realized task is incomplete, resetting verification")
            self.progress.completion_verification.reset()
            self.progress.state = TaskState.WORKING
            self.in_verification = False
            return False

        # Check if Claude is still claiming completion
        still_complete, complete_conf = self.matcher.match(text, 'completion')

        if still_complete and complete_conf > 0.8:
            # Continue verification or accept completion
            if self.progress.completion_verification.verification_count < self.verification_attempts:
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

    async def analyze_state(self, text: str) -> TaskState:
        """Analyze text to determine current state"""
        # If in verification, handle specially
        if self.in_verification:
            await self.analyze_verification_response(text)
            return self.progress.state

        # Check patterns with confidence
        is_complete, complete_conf = self.matcher.match(text, 'completion')
        is_error, error_conf = self.matcher.match(text, 'error')
        is_waiting, wait_conf = self.matcher.match(text, 'waiting')
        has_progress, _ = self.matcher.match(text, 'progress')

        # If claiming completion, verify it
        if is_complete and complete_conf > 0.8 and self.progress.state != TaskState.COMPLETED:
            is_verified = await self.handle_completion_claim()
            if is_verified:
                return TaskState.COMPLETED
            else:
                return TaskState.VERIFYING

        # Normal state determination
        if is_error and error_conf > 0.7:
            return TaskState.ERROR
        elif is_waiting and wait_conf > 0.6:
            return TaskState.WAITING
        elif has_progress:
            return TaskState.WORKING
        else:
            # Check for stall
            if time.time() - self.last_output_time > self.stall_timeout:
                return TaskState.STALLED
            return self.progress.state

    async def should_continue(self) -> Tuple[bool, str]:
        """Determine if we should send continue"""
        if self.metrics.continues_sent >= self.max_continues:
            return False, "Max continues reached"

        # Don't auto-continue during verification
        if self.progress.state == TaskState.VERIFYING:
            return False, "In verification phase"

        if self.progress.state == TaskState.COMPLETED:
            return False, "Task completed and verified"

        if self.progress.state == TaskState.ERROR:
            # Check if it's a recoverable error
            recent_text = ''.join(self.recent_output)
            if "retry" in recent_text.lower() or "fixing" in recent_text.lower():
                return True, "Attempting to recover from error"
            return False, "Unrecoverable error detected"

        if self.progress.state == TaskState.WAITING:
            # Check if we have pending work
            if self.progress.todos_total > self.progress.todos_completed:
                return True, f"TODOs remaining: {self.progress.todos_total - self.progress.todos_completed}"

            # Check failed tests
            failed_tests = [name for name, passed in self.progress.test_cases.items() if not passed]
            if failed_tests:
                return True, f"Failed tests: {', '.join(failed_tests[:3])}"

            return True, "Claude-Code is waiting for input"

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

    async def handle_pty_output(self):
        """Handle output from Claude-Code via PTY with proper real-time display"""
        buffer = b""

        while self.master_fd is not None and not self.stop_stdin_thread.is_set():
            try:
                # Use select to check if PTY has data
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                if ready:
                    try:
                        # Read available data (non-blocking)
                        chunk = os.read(self.master_fd, 1024)
                        if not chunk:
                            break

                        buffer += chunk

                        # Process complete lines
                        while b'\n' in buffer:
                            line_bytes, buffer = buffer.split(b'\n', 1)
                            line = line_bytes.decode('utf-8', errors='replace') + '\n'

                            # Display immediately to user
                            sys.stdout.write(line)
                            sys.stdout.flush()

                            # Update buffers
                            self.output_buffer.append(line)
                            self.recent_output.append(line)
                            self.last_output_time = time.time()

                        # Process any remaining buffer content if it's substantial
                        if len(buffer) > 0:
                            partial_line = buffer.decode('utf-8', errors='replace')
                            if len(partial_line) > 50:  # Only if substantial content
                                sys.stdout.write(partial_line)
                                sys.stdout.flush()
                                self.output_buffer.append(partial_line)
                                self.recent_output.append(partial_line)
                                self.last_output_time = time.time()
                                buffer = b""

                        # Analyze output periodically
                        if len(self.recent_output) >= 10:
                            recent_text = ''.join(self.recent_output)

                            # Extract progress
                            progress_updates = self.extract_progress(recent_text)
                            for key, value in progress_updates.items():
                                setattr(self.progress, key, value)

                            # Update state
                            new_state = await self.analyze_state(recent_text)
                            if new_state != self.progress.state:
                                old_state = self.progress.state
                                self.progress.state = new_state
                                self.metrics.state_changes.append((time.time(), new_state))
                                await self.log('INFO', f"State changed from {old_state.value} to {new_state.value}")

                    except (BlockingIOError, OSError):
                        pass
                    except Exception as e:
                        await self.log('ERROR', f"PTY read error: {e}")
                        break

            except Exception as e:
                await self.log('ERROR', f"Output handling error: {e}")
                break

    async def handle_command(self, command: str):
        """Handle supervisor commands"""
        parts = command.split()
        cmd = parts[0].lower()

        if cmd == '/status':
            print(f"\n[SUPERVISOR] Status Report", file=sys.stderr)
            print(f"  State: {self.progress.state.value}", file=sys.stderr)
            print(f"  Duration: {self.metrics.duration:.1f}s", file=sys.stderr)
            print(f"  Continues sent: {self.metrics.continues_sent}", file=sys.stderr)
            print(f"  TODOs: {self.progress.todos_completed}/{self.progress.todos_total}", file=sys.stderr)
            print(f"  Tests: {sum(1 for p in self.progress.test_cases.values() if p)}/{len(self.progress.test_cases)}", file=sys.stderr)
            if self.in_verification:
                print(f"  Verification: {self.progress.completion_verification.verification_count}/{self.verification_attempts}", file=sys.stderr)

        elif cmd == '/verify':
            if len(parts) > 1:
                self.verify_completion = parts[1].lower() == 'on'
                print(f"\n[SUPERVISOR] Completion verification: {'ON' if self.verify_completion else 'OFF'}", file=sys.stderr)

        elif cmd == '/auto':
            if len(parts) > 1:
                self.auto_continue = parts[1].lower() == 'on'
                print(f"\n[SUPERVISOR] Auto-continue: {'ON' if self.auto_continue else 'OFF'}", file=sys.stderr)

        elif cmd == '/continue':
            print("\n[SUPERVISOR] Forcing continue...", file=sys.stderr)
            try:
                if self.master_fd is not None:
                    os.write(self.master_fd, b"continue\n")
                    self.metrics.continues_sent += 1
                else:
                    await self.log('ERROR', "PTY not available for continue command")
            except Exception as e:
                await self.log('ERROR', f"Failed to send continue: {e}")

        else:
            print(f"\n[SUPERVISOR] Unknown command: {cmd}", file=sys.stderr)

    async def auto_continue_monitor(self):
        """Monitor and auto-continue when appropriate"""
        while self.process and self.process.returncode is None:
            try:
                await asyncio.sleep(1)

                # Check if we should auto-continue
                if (self.auto_continue and
                    time.time() - self.last_output_time > self.continue_delay and
                    time.time() - self.last_continue_time > self.continue_delay):

                    should_cont, reason = await self.should_continue()

                    if should_cont:
                        self.metrics.continues_sent += 1
                        self.last_continue_time = time.time()

                        await self.log('INFO', f"Auto-continue #{self.metrics.continues_sent}: {reason}")

                        try:
                            if self.master_fd is not None:
                                os.write(self.master_fd, b"continue\n")
                            else:
                                await self.log('ERROR', "PTY not available for auto-continue")
                        except Exception as e:
                            await self.log('ERROR', f"Failed to send auto-continue: {e}")

                        # Clear recent output after continue
                        self.recent_output.clear()

                # Check for stalls
                if time.time() - self.last_output_time > self.stall_timeout:
                    if self.progress.state != TaskState.STALLED:
                        self.progress.state = TaskState.STALLED
                        await self.log('WARNING', "Process appears stalled")

            except Exception as e:
                await self.log('ERROR', f"Monitor error: {e}")

    async def generate_report(self):
        """Generate final report"""
        report = {
            'task_description': self.task_description,
            'command': ' '.join(self.command),
            'start_time': datetime.fromtimestamp(self.metrics.start_time).isoformat(),
            'end_time': datetime.fromtimestamp(self.metrics.end_time or time.time()).isoformat(),
            'duration_seconds': self.metrics.duration,
            'final_state': self.progress.state.value,
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
            ]
        }

        report_file = self.log_file.replace('.log', '_report.json')
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        return report_file

    async def run(self):
        """Main supervisor execution"""
        print(f"[SUPERVISOR] Advanced Claude-Code Supervisor with Verification", file=sys.stderr)
        print(f"[SUPERVISOR] Task: {self.task_description or 'Not specified'}", file=sys.stderr)
        print(f"[SUPERVISOR] Auto-continue: {'ON' if self.auto_continue else 'OFF'}", file=sys.stderr)
        print(f"[SUPERVISOR] Completion verification: {'ON' if self.verify_completion else 'OFF'}", file=sys.stderr)
        print(f"[SUPERVISOR] Max continues: {self.max_continues}", file=sys.stderr)
        print(f"[SUPERVISOR] Log file: {self.log_file}", file=sys.stderr)
        print("-" * 80, file=sys.stderr)

        # Store event loop for threading
        self.loop = asyncio.get_event_loop()

        # Create PTY for proper terminal interaction
        self.master_fd, self.slave_fd = pty.openpty()
        
        # Set terminal size to match current terminal
        try:
            rows, cols = os.get_terminal_size()
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass  # Fallback to default size

        # Start subprocess with PTY
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            preexec_fn=os.setsid  # Create new session
        )

        await self.log('INFO', "Started", {'pid': self.process.pid})

        # Start stdin forwarding thread
        self.start_stdin_thread()

        # Create tasks
        tasks = [
            asyncio.create_task(self.handle_pty_output(), name='pty_handler'),
            asyncio.create_task(self.auto_continue_monitor(), name='monitor'),
        ]

        try:
            # Wait for process completion
            await self.process.wait()
            self.metrics.end_time = time.time()

            await self.log('INFO', f"Process completed with code {self.process.returncode}")

        finally:
            self.running = False

            # Stop stdin thread
            self.stop_stdin_thread.set()
            if self.stdin_thread and self.stdin_thread.is_alive():
                self.stdin_thread.join(timeout=1.0)

            # Close PTY file descriptors
            if self.master_fd is not None:
                try:
                    os.close(self.master_fd)
                except Exception:
                    pass
                self.master_fd = None
            
            if self.slave_fd is not None:
                try:
                    os.close(self.slave_fd)
                except Exception:
                    pass
                self.slave_fd = None

            # Cancel tasks
            for task in tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            # Generate report
            report_file = await self.generate_report()

            print(f"\n[SUPERVISOR] Session completed", file=sys.stderr)
            print(f"[SUPERVISOR] Duration: {self.metrics.duration:.1f} seconds", file=sys.stderr)
            print(f"[SUPERVISOR] Final state: {self.progress.state.value}", file=sys.stderr)
            print(f"[SUPERVISOR] Continues sent: {self.metrics.continues_sent}", file=sys.stderr)
            if self.verify_completion:
                print(f"[SUPERVISOR] Verification attempts: {self.progress.completion_verification.verification_count}", file=sys.stderr)
            print(f"[SUPERVISOR] Report saved: {report_file}", file=sys.stderr)

async def main():
    parser = argparse.ArgumentParser(
        description='Advanced Claude-Code Supervisor with completion verification'
    )
    parser.add_argument('-t', '--task', help='Task description for better tracking')
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

    args = parser.parse_args()

    supervisor = AdvancedClaudeCodeSupervisor(
        command=['claude', '--dangerously-skip-permissions', '--continue'],
        task_description=args.task,
        auto_continue=not args.no_auto,
        max_continues=args.max_continues,
        log_file=args.log_file,
        verbose=args.verbose,
        continue_delay=args.delay,
        stall_timeout=args.stall_timeout,
        verify_completion=not args.no_verify,
        verification_attempts=args.verify_attempts
    )

    # Handle Ctrl+C gracefully
    loop = asyncio.get_event_loop()

    def signal_handler():
        print("\n[SUPERVISOR] Interrupt received, shutting down...", file=sys.stderr)
        supervisor.running = False
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, signal_handler)

    try:
        await supervisor.run()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"\n[SUPERVISOR] Fatal error: {e}", file=sys.stderr)
        raise

if __name__ == '__main__':
    asyncio.run(main())