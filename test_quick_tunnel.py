#!/usr/bin/env python3
"""
Test VibeTeam MCP server with Cloudflare quick tunnel.
This creates a temporary public HTTPS URL without needing credentials.
"""
import subprocess
import sys
import time
import re
import requests
import json
import threading
import os
import socket


class QuickTunnelTest:
    def __init__(self):
        self.mcp_process = None
        self.tunnel_process = None
        self.tunnel_url = None
        self.port = 3333
        
    def start_mcp_server(self):
        """Start MCP server in TCP mode."""
        print("🚀 Starting MCP server on port 3333...")
        
        env = os.environ.copy()
        env["MCP_PORT"] = str(self.port)
        env["MCP_MODE"] = "tcp"
        
        self.mcp_process = subprocess.Popen(
            [sys.executable, '-m', 'run_mcp_server'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        # Wait for server
        time.sleep(3)
        
        # Verify it's running
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(('localhost', self.port))
            sock.close()
            print("✅ MCP server started successfully")
            return True
        except:
            print("❌ Failed to start MCP server")
            return False
    
    def start_quick_tunnel(self):
        """Start Cloudflare quick tunnel."""
        print("🌐 Starting Cloudflare quick tunnel...")
        
        # Use the downloaded cloudflared binary
        cloudflared_path = "./cloudflared"
        if not os.path.exists(cloudflared_path):
            print("❌ cloudflared binary not found")
            return False
            
        self.tunnel_process = subprocess.Popen(
            [cloudflared_path, 'tunnel', '--url', f'http://localhost:{self.port}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Wait for tunnel URL
        print("⏳ Waiting for tunnel URL...")
        start_time = time.time()
        
        while time.time() - start_time < 30:
            line = self.tunnel_process.stderr.readline()
            if line:
                print(f"[TUNNEL] {line.strip()}")
                
                # Look for the tunnel URL
                if 'trycloudflare.com' in line:
                    match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                    if match:
                        self.tunnel_url = match.group(0)
                        print(f"\n✅ Tunnel URL: {self.tunnel_url}")
                        print("⏳ Waiting for DNS propagation...")
                        time.sleep(10)  # Wait for DNS to propagate
                        return True
        
        print("❌ Failed to get tunnel URL")
        return False
    
    def test_tunnel_access(self):
        """Test MCP server through tunnel."""
        if not self.tunnel_url:
            return False
            
        print(f"\n🧪 Testing MCP server at {self.tunnel_url}")
        
        # Test DNS resolution first
        print("🔍 Checking DNS resolution...")
        for i in range(5):
            try:
                import socket as sock
                host = self.tunnel_url.replace("https://", "").replace("http://", "")
                sock.gethostbyname(host)
                print("✅ DNS resolved successfully")
                break
            except:
                if i < 4:
                    print(f"   Waiting for DNS... ({i+1}/5)")
                    time.sleep(3)
                else:
                    print("❌ DNS resolution failed")
                    return False
        
        try:
            # Test 1: Initialize
            print("\n1️⃣ Testing initialization...")
            response = requests.post(
                self.tunnel_url,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {}
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    capabilities = result["result"].get("capabilities", {})
                    agent = capabilities.get("agent", {})
                    print(f"✅ Connected to: {agent.get('type', 'MCP')} v{agent.get('version', 'unknown')}")
                    print(f"   Response time: {response.elapsed.total_seconds():.2f}s")
                else:
                    print("❌ Invalid response format")
                    return False
            else:
                print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
                return False
            
            # Test 2: Execute code
            print("\n2️⃣ Testing code execution...")
            response = requests.post(
                self.tunnel_url,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/execute",
                    "params": {
                        "name": "execute_code",
                        "arguments": {
                            "code": "print('Hello from Cloudflare tunnel!')",
                            "language": "python"
                        }
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                print("✅ Code execution request: 200 OK")
                result = response.json()
                if "error" in result:
                    print(f"   Expected error (no API key): {result['error'].get('message', 'Unknown')}")
                elif "result" in result:
                    print(f"   Result: {result['result']}")
            
            # Test 3: Generate code
            print("\n3️⃣ Testing code generation...")
            response = requests.post(
                self.tunnel_url,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/execute",
                    "params": {
                        "name": "generate_code",
                        "arguments": {
                            "specification": "Create a Python function to calculate factorial",
                            "language": "python"
                        }
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                print("✅ Code generation request: 200 OK")
            
            return True
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up processes."""
        print("\n🧹 Cleaning up...")
        
        if self.tunnel_process:
            self.tunnel_process.terminate()
            self.tunnel_process.wait()
            
        if self.mcp_process:
            self.mcp_process.terminate()
            self.mcp_process.wait()
    
    def run(self):
        """Run the complete test."""
        print("=" * 60)
        print("🌐 VIBETEAM MCP + CLOUDFLARE QUICK TUNNEL TEST")
        print("=" * 60)
        
        try:
            # Start MCP server
            if not self.start_mcp_server():
                return False
            
            # Start quick tunnel
            if not self.start_quick_tunnel():
                return False
            
            # Test access through tunnel
            if not self.test_tunnel_access():
                return False
            
            print("\n" + "=" * 60)
            print("✅ SUCCESS: MCP server is accessible via Cloudflare tunnel!")
            print(f"🌐 Public URL: {self.tunnel_url}")
            print("=" * 60)
            
            return True
            
        finally:
            self.cleanup()


if __name__ == "__main__":
    tester = QuickTunnelTest()
    success = tester.run()
    sys.exit(0 if success else 1)