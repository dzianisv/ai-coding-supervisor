#!/usr/bin/env python3
"""
Test VibeTeam MCP with Cloudflare tunnel using HTTP wrapper.
"""
import subprocess
import sys
import time
import re
import requests
import json
import os
import socket


def main():
    print("=" * 70)
    print("🚀 VIBETEAM MCP + HTTP WRAPPER + CLOUDFLARE TUNNEL TEST")
    print("=" * 70)
    
    mcp_process = None
    http_process = None
    tunnel_process = None
    
    try:
        # Step 1: Start MCP Server
        print("\n[STEP 1] Starting VibeTeam MCP Server (TCP)...")
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
            print("✅ MCP TCP server running on port 3333")
        except:
            print("❌ Failed to start MCP server")
            return False
        
        # Step 2: Start HTTP wrapper
        print("\n[STEP 2] Starting HTTP wrapper...")
        http_process = subprocess.Popen(
            [sys.executable, 'mcp/http_wrapper.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        time.sleep(3)
        
        # Test HTTP wrapper
        try:
            response = requests.get('http://localhost:8080/health', timeout=5)
            if response.status_code == 200:
                print("✅ HTTP wrapper running on port 8080")
            else:
                print("❌ HTTP wrapper not healthy")
                return False
        except:
            print("❌ Failed to start HTTP wrapper")
            return False
        
        # Step 3: Start Cloudflare Tunnel pointing to HTTP wrapper
        print("\n[STEP 3] Starting Cloudflare tunnel...")
        tunnel_process = subprocess.Popen(
            ['./cloudflared', 'tunnel', '--url', 'http://localhost:8080'],
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
            if line:
                print(f"[TUNNEL] {line.strip()}")
                if 'trycloudflare.com' in line:
                    match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                    if match:
                        tunnel_url = match.group(0)
                        print(f"\n✅ Tunnel created: {tunnel_url}")
                        break
        
        if not tunnel_url:
            print("❌ Failed to create tunnel")
            return False
        
        # Wait for tunnel to stabilize
        print("⏳ Waiting for tunnel to stabilize...")
        time.sleep(10)
        
        # Step 4: Test MCP through Tunnel
        print(f"\n[STEP 4] Testing MCP Server via Cloudflare Tunnel")
        print(f"🌐 Public URL: {tunnel_url}")
        
        # Test 1: Health check
        print("\n📋 Test 1: Health Check")
        try:
            response = requests.get(f"{tunnel_url}/health", timeout=10)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
                print("✅ Health check passed")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
        
        # Test 2: MCP Initialize
        print("\n📋 Test 2: MCP Initialize")
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
            
            if response.status_code == 200:
                result = response.json()
                print(f"   Response: {json.dumps(result, indent=2)}")
                
                if "result" in result:
                    capabilities = result["result"].get("capabilities", {})
                    agent = capabilities.get("agent", {})
                    print(f"\n✅ SUCCESS: Connected to {agent.get('type', 'MCP')} v{agent.get('version', 'unknown')}")
                    print("✅ MCP server is accessible via Cloudflare tunnel!")
                    print(f"🌐 Public HTTPS endpoint: {tunnel_url}")
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
        if http_process:
            http_process.terminate()
        if mcp_process:
            mcp_process.terminate()
            
        if tunnel_process:
            tunnel_process.wait()
        if http_process:
            http_process.wait()
        if mcp_process:
            mcp_process.wait()


if __name__ == "__main__":
    # Install Flask if needed
    try:
        import flask
    except ImportError:
        print("Installing Flask...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'flask'])
    
    success = main()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 PROOF COMPLETE: VibeTeam MCP works with Cloudflare tunnel!")
        print("   - MCP TCP server ✅")
        print("   - HTTP wrapper ✅") 
        print("   - Cloudflare tunnel ✅")
        print("   - Public HTTPS access ✅")
    else:
        print("❌ Test failed - see logs above")
    print("=" * 70)
    
    sys.exit(0 if success else 1)