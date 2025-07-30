#!/usr/bin/env python3
"""Simple TCP test to debug server communication."""
import socket
import json
import time
import subprocess
import sys
import os

def test_tcp_server():
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
    
    # Check if server is running
    if server.poll() is not None:
        stdout, stderr = server.communicate()
        print(f"Server exited with code {server.returncode}")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")
        return
    
    try:
        # Try to connect
        print("Connecting to server...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(('localhost', 3333))
        
        # Send initialize request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        
        print("Sending initialize request...")
        sock.send((json.dumps(request) + '\n').encode())
        
        # Read response
        sock.settimeout(10)
        data = sock.recv(8192)
        if data:
            print(f"Received response: {data.decode()}")
            response = json.loads(data.decode().strip())
            print(f"Parsed: {json.dumps(response, indent=2)}")
        else:
            print("No response received")
            
        sock.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up
        print("Cleaning up...")
        server.terminate()
        server.wait()
        
if __name__ == "__main__":
    test_tcp_server()