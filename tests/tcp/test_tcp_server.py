#!/usr/bin/env python3
"""Test TCP server binding and HTTP compatibility."""
import socket
import subprocess
import sys
import os
import time
import requests

# Start MCP server
print("Starting MCP server...")
env = os.environ.copy()
env["MCP_PORT"] = "3333"
env["MCP_MODE"] = "tcp"

mcp = subprocess.Popen(
    [sys.executable, '-m', 'run_mcp_server'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env
)

time.sleep(3)

# Test 1: Raw TCP
print("\n1. Testing raw TCP connection...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', 3333))
    sock.send(b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
    data = sock.recv(8192)
    print(f"✅ TCP Response: {data.decode()[:100]}...")
    sock.close()
except Exception as e:
    print(f"❌ TCP failed: {e}")

# Test 2: HTTP request
print("\n2. Testing HTTP connection...")
try:
    response = requests.post(
        'http://localhost:3333',
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        timeout=5
    )
    print(f"✅ HTTP Status: {response.status_code}")
    print(f"   Response: {response.text[:100]}...")
except Exception as e:
    print(f"❌ HTTP failed: {e}")

# Check server logs
print("\n3. Server logs:")
for i in range(5):
    line = mcp.stderr.readline()
    if line:
        print(f"   {line.strip()}")

mcp.terminate()
mcp.wait()