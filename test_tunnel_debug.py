#!/usr/bin/env python3
"""Debug tunnel connectivity issues."""
import subprocess
import time
import threading
import os
import sys
import socket
import json

def read_output(proc, name):
    """Read process output in background."""
    for line in iter(proc.stdout.readline, ''):
        if line:
            print(f"[{name} STDOUT] {line.strip()}")
    for line in iter(proc.stderr.readline, ''):
        if line:
            print(f"[{name} STDERR] {line.strip()}")

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

# Monitor MCP output
mcp_thread = threading.Thread(target=read_output, args=(mcp, "MCP"))
mcp_thread.daemon = True
mcp_thread.start()

time.sleep(3)

# Test local connection
print("\nTesting local connection...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(('localhost', 3333))
    
    # Send test request
    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    sock.send((json.dumps(request) + '\n').encode())
    
    # Read response
    data = sock.recv(8192)
    if data:
        print(f"Local test response: {data.decode()[:100]}...")
        sock.close()
        print("✅ Local connection works")
    else:
        print("❌ No response from local server")
except Exception as e:
    print(f"❌ Local connection failed: {e}")

# Now start tunnel with verbose logging
print("\nStarting Cloudflare tunnel with verbose logging...")
tunnel = subprocess.Popen(
    ['./cloudflared', 'tunnel', '--url', 'http://localhost:3333', '--loglevel', 'debug'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Monitor tunnel output
tunnel_thread = threading.Thread(target=read_output, args=(tunnel, "TUNNEL"))
tunnel_thread.daemon = True
tunnel_thread.start()

# Wait and let it run
print("\nMonitoring connections for 30 seconds...")
print("Look for any connection errors or issues...")
time.sleep(30)

# Cleanup
print("\nCleaning up...")
tunnel.terminate()
mcp.terminate()
tunnel.wait()
mcp.wait()