"""
Synchronous MCP Server implementation for better subprocess compatibility.
"""
import json
import sys
import logging
import asyncio
from typing import Any, Dict, Optional, Callable
import threading
import queue

logger = logging.getLogger(__name__)


class SyncStdioMCPServer:
    """MCP Server with synchronous I/O for subprocess compatibility."""
    
    def __init__(self, async_server):
        """Initialize with an async server to delegate to.
        
        Args:
            async_server: The async StdioMCPServer instance
        """
        self.async_server = async_server
        self._running = False
        self._loop = None
        self._thread = None
        
    def start(self):
        """Start the server (blocking)."""
        self._running = True
        logger.info("Starting synchronous MCP server")
        
        # Run async event loop in a separate thread
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_async_loop)
        self._thread.start()
        
        logger.info("Ready to receive messages on stdin")
        
        # Read from stdin in main thread
        try:
            while self._running:
                try:
                    line = sys.stdin.readline()
                    if not line:  # EOF
                        break
                        
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Parse message
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError as e:
                        error = {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32700,
                                "message": "Parse error"
                            }
                        }
                        self._send_response(error)
                        continue
                    
                    # Handle message asynchronously
                    future = asyncio.run_coroutine_threadsafe(
                        self.async_server._handle_message(message),
                        self._loop
                    )
                    
                    # Wait for response
                    try:
                        response = future.result(timeout=30)
                        if response:
                            self._send_response(response)
                    except Exception as e:
                        logger.error(f"Error handling message: {e}", exc_info=True)
                        if "id" in message:
                            error = {
                                "jsonrpc": "2.0",
                                "id": message["id"],
                                "error": {
                                    "code": -32603,
                                    "message": f"Internal error: {str(e)}"
                                }
                            }
                            self._send_response(error)
                            
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    
        finally:
            self.stop()
            
    def stop(self):
        """Stop the server."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
            
    def _run_async_loop(self):
        """Run the async event loop in a thread."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        self._loop.close()
        
    def _send_response(self, response: Dict[str, Any]):
        """Send a response to stdout."""
        try:
            json_str = json.dumps(response, separators=(',', ':'))
            sys.stdout.write(json_str + '\n')
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error sending response: {e}", exc_info=True)