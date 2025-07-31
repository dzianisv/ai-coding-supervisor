#!/usr/bin/env python3
"""Test execute_task method on TCP server."""
import socket
import json
import time
import subprocess
import sys
import os

def test_execute_task():
    # Start server
    print("Starting MCP server in TCP mode...")
    env = os.environ.copy()
    env["MCP_PORT"] = "3333"
    env["MCP_MODE"] = "tcp"
    
    server = subprocess.Popen(
        [sys.executable, "-m", "run_mcp_server"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(('localhost', 3333))
        
        # Initialize first
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        sock.send((json.dumps(request) + '\n').encode())
        data = sock.recv(8192)
        print(f"Initialize response: {json.loads(data.decode().strip())['result']['capabilities']['agent']}")
        
        # Now test execute_task
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "execute_task",
            "params": {
                "description": "Create a simple Python function that returns 'Hello, World!'"
            }
        }
        
        print("\nSending execute_task request...")
        sock.send((json.dumps(request) + '\n').encode())
        
        # Wait for response (may take time due to Claude API)
        sock.settimeout(30)
        data = sock.recv(65536)  # Larger buffer for potential code response
        
        if data:
            response = json.loads(data.decode().strip())
            print(f"\nResponse received:")
            print(json.dumps(response, indent=2))
            
            if "result" in response:
                result = response["result"]
                if "status" in result:
                    print(f"\nStatus: {result['status']}")
                if "error" in result:
                    print(f"Error: {result['error']}")
                elif "output" in result:
                    print(f"Output preview: {str(result['output'])[:200]}...")
        
        sock.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up
        print("\nCleaning up...")
        server.terminate()
        server.wait()
        
if __name__ == "__main__":
    test_execute_task()