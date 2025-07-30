#!/usr/bin/env python3
"""
Final proof that VibeTeam MCP server works with Cloudflare tunnel.
"""
import subprocess
import sys
import time
import re
import requests
import json
import os
import socket
import threading


def monitor_output(proc, name, patterns):
    """Monitor process output for patterns."""
    found = {}
    for line in iter(proc.stderr.readline, ''):
        if line:
            line = line.strip()
            print(f"[{name}] {line}")
            for key, pattern in patterns.items():
                if pattern in line and key not in found:
                    match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                    if match:
                        found[key] = match.group(0)


def main():
    print("=" * 70)
    print("🚀 VIBETEAM MCP + CLOUDFLARE TUNNEL - FINAL PROOF TEST")
    print("=" * 70)
    
    mcp_process = None
    tunnel_process = None
    
    try:
        # Step 1: Start MCP Server
        print("\n[STEP 1] Starting VibeTeam MCP Server...")
        env = os.environ.copy()
        env["MCP_PORT"] = "3333"
        env["MCP_MODE"] = "tcp"
        
        mcp_process = subprocess.Popen(
            [sys.executable, '-m', 'run_mcp_server'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        time.sleep(3)
        
        # Verify MCP is running
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(('localhost', 3333))
            sock.close()
            print("✅ MCP server running on port 3333")
        except:
            print("❌ Failed to start MCP server")
            return False
        
        # Step 2: Start Cloudflare Tunnel
        print("\n[STEP 2] Starting Cloudflare Quick Tunnel...")
        tunnel_process = subprocess.Popen(
            ['./cloudflared', 'tunnel', '--url', 'http://localhost:3333'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Wait for tunnel URL
        tunnel_url = None
        start_time = time.time()
        
        while time.time() - start_time < 30:
            line = tunnel_process.stderr.readline()
            if line and 'trycloudflare.com' in line:
                match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                if match:
                    tunnel_url = match.group(0)
                    print(f"✅ Tunnel created: {tunnel_url}")
                    break
        
        if not tunnel_url:
            print("❌ Failed to create tunnel")
            return False
        
        # Wait for DNS and tunnel to stabilize
        print("⏳ Waiting for tunnel to stabilize...")
        time.sleep(10)
        
        # Step 3: Test MCP through Tunnel
        print(f"\n[STEP 3] Testing MCP Server via Cloudflare Tunnel")
        print(f"URL: {tunnel_url}")
        
        # Test 1: Initialize
        print("\n📋 Test 1: MCP Initialize")
        try:
            response = requests.post(
                tunnel_url,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {}
                },
                timeout=15
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"   Response: {json.dumps(result, indent=2)}")
                
                if "result" in result:
                    capabilities = result["result"].get("capabilities", {})
                    agent = capabilities.get("agent", {})
                    print(f"\n✅ SUCCESS: Connected to {agent.get('type', 'MCP')} v{agent.get('version', 'unknown')}")
                    print("✅ MCP server is accessible via Cloudflare tunnel!")
                    
                    # Test 2: Try a tool
                    print("\n📋 Test 2: MCP Tool Execution")
                    response2 = requests.post(
                        tunnel_url,
                        headers={"Content-Type": "application/json"},
                        json={
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/execute",
                            "params": {
                                "name": "generate_code",
                                "arguments": {
                                    "specification": "Hello world function",
                                    "language": "python"
                                }
                            }
                        },
                        timeout=30
                    )
                    
                    print(f"   Status Code: {response2.status_code}")
                    if response2.status_code == 200:
                        print("✅ Tool execution endpoint accessible")
                    
                    return True
                    
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            
        return False
        
    finally:
        # Cleanup
        print("\n[CLEANUP] Stopping services...")
        if tunnel_process:
            tunnel_process.terminate()
            tunnel_process.wait()
        if mcp_process:
            mcp_process.terminate()
            mcp_process.wait()


if __name__ == "__main__":
    success = main()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 PROOF COMPLETE: VibeTeam MCP server works with Cloudflare tunnel!")
        print("🌐 You can expose your MCP server to the internet using Cloudflare!")
    else:
        print("❌ Test failed - check the logs above for details")
    print("=" * 70)
    
    sys.exit(0 if success else 1)