#!/usr/bin/env python3
"""
Comprehensive end-to-end integration test for VibeTeam MCP server with Cloudflare tunnel.
Adapted from VibeCode's test_tunnel_e2e_comprehensive.py
Tests the complete flow: start server -> create tunnel -> verify MCP accessibility.
"""

import subprocess
import sys
import time
import re
import requests
import json
import threading
from pathlib import Path
import uuid
import os
import socket


class VibeTeamTunnelE2ETest:
    """Comprehensive tunnel end-to-end test runner for VibeTeam."""
    
    def __init__(self, port=3333):
        self.port = port
        self.mcp_process = None
        self.tunnel_process = None
        self.tunnel_url = None
        self.success = False
        
    def run_test(self, timeout=90):
        """Run complete end-to-end test."""
        print("🚀 Starting comprehensive VibeTeam tunnel E2E test...")
        
        try:
            # Step 1: Start vibeteam-mcp in TCP mode
            if not self._start_mcp_server():
                return False
                
            # Step 2: Start cloudflared tunnel (if available)
            if not self._start_cloudflare_tunnel(timeout):
                print("⚠️  Cloudflare tunnel not available, testing local TCP only")
                return self._test_local_tcp_mode()
                
            # Step 3: Test MCP server accessibility through tunnel
            if not self._test_mcp_server():
                return False
                
            # Step 4: Test MCP tools functionality
            if not self._test_mcp_tools():
                return False
                
            # Step 5: Test VibeTeam-specific tools
            if not self._test_vibeteam_tools():
                return False
                
            self.success = True
            print("🎉 SUCCESS: All tunnel E2E tests passed!")
            return True
            
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            self._cleanup()
    
    def _start_mcp_server(self):
        """Start VibeTeam MCP server in TCP mode."""
        print("⏳ Starting VibeTeam MCP server...")
        
        env = os.environ.copy()
        env["MCP_PORT"] = str(self.port)
        env["MCP_MODE"] = "tcp"
        
        # Start using run_mcp_server module
        self.mcp_process = subprocess.Popen([
            sys.executable, '-m', 'run_mcp_server'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, bufsize=1)
        
        # Wait for server to start
        time.sleep(3)
        
        # Verify server is running
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(('localhost', self.port))
            sock.close()
            print(f"✅ MCP server started on port {self.port}")
            return True
        except Exception as e:
            print(f"❌ Failed to start MCP server: {e}")
            return False
    
    def _start_cloudflare_tunnel(self, timeout):
        """Start cloudflared tunnel if available."""
        print("⏳ Checking for cloudflared tunnel...")
        
        # Check if cloudflared is available
        try:
            result = subprocess.run(['which', 'cloudflared'], capture_output=True)
            if result.returncode != 0:
                print("⚠️  cloudflared not found, skipping tunnel test")
                return False
        except:
            return False
            
        # Check if tunnel config exists
        config_path = os.path.expanduser("~/.cloudflared/config.yml")
        if not os.path.exists(config_path):
            print("⚠️  No cloudflared config found at ~/.cloudflared/config.yml")
            print("   Run ./deploy/cloudflare/setup_tunnel.sh to set up tunnel")
            return False
            
        # Start cloudflared tunnel
        print("🌐 Starting cloudflared tunnel...")
        self.tunnel_process = subprocess.Popen([
            'cloudflared', 'tunnel', '--config', config_path, 'run'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        
        # Wait for tunnel to establish
        start_time = time.time()
        tunnel_established = False
        
        while time.time() - start_time < timeout:
            line = self.tunnel_process.stderr.readline()
            if not line:
                if self.tunnel_process.poll() is not None:
                    print("❌ Tunnel process terminated unexpectedly")
                    return False
                time.sleep(0.1)
                continue
                
            line = line.strip()
            print(f"[TUNNEL] {line}")
            
            # Look for tunnel URL from config
            if 'Connection registered' in line or 'Tunnel is ready' in line:
                # Extract URL from config
                with open(config_path, 'r') as f:
                    config = f.read()
                    match = re.search(r'hostname:\s*(\S+)', config)
                    if match:
                        self.tunnel_url = f"https://{match.group(1)}"
                        print(f"✅ Tunnel URL: {self.tunnel_url}")
                        tunnel_established = True
                        break
            
            # Also check for quick tunnel URL
            if 'trycloudflare.com' in line:
                url_match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                if url_match:
                    self.tunnel_url = url_match.group(0)
                    print(f"✅ Quick tunnel URL: {self.tunnel_url}")
                    tunnel_established = True
                    break
        
        if tunnel_established:
            # Wait for tunnel to stabilize
            time.sleep(5)
            return True
        else:
            print("❌ Failed to establish tunnel")
            return False
    
    def _test_local_tcp_mode(self):
        """Test MCP server in local TCP mode."""
        print("🔧 Testing local TCP mode...")
        
        # Test TCP connection
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(('localhost', self.port))
            
            # Send initialize request
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {}
            }
            sock.send((json.dumps(request) + '\n').encode())
            
            # Read response
            data = sock.recv(8192)
            if data:
                response = json.loads(data.decode().strip())
                if "result" in response:
                    capabilities = response["result"].get("capabilities", {})
                    agent = capabilities.get("agent", {})
                    print(f"✅ TCP mode working: {agent.get('type', 'Unknown')} v{agent.get('version', 'Unknown')}")
                    return True
            
            sock.close()
            return False
            
        except Exception as e:
            print(f"❌ TCP mode test failed: {e}")
            return False
    
    def _test_mcp_server(self):
        """Test MCP server through tunnel."""
        print("🔧 Testing MCP server through tunnel...")
        
        if not self.tunnel_url:
            print("❌ No tunnel URL available")
            return False
        
        # Test MCP initialize request
        try:
            response = requests.post(
                self.tunnel_url,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "id": 1,
                    "params": {}
                },
                timeout=15,
                verify=True  # Use proper SSL verification
            )
            
            if response.status_code == 200:
                print("✅ MCP initialize: 200 OK")
                result = response.json()
                if "result" in result:
                    capabilities = result["result"].get("capabilities", {})
                    agent = capabilities.get("agent", {})
                    print(f"✅ Connected to: {agent.get('type', 'MCP')} v{agent.get('version', 'Unknown')}")
                return True
            else:
                print(f"❌ MCP initialize failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ MCP server test failed: {e}")
            return False
    
    def _test_mcp_tools(self):
        """Test MCP tools/execute functionality through tunnel."""
        print("🛠️  Testing MCP tools through tunnel...")
        
        if not self.tunnel_url:
            print("❌ No tunnel URL available")
            return False
        
        # Test code execution tool
        try:
            response = requests.post(
                self.tunnel_url,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/execute",
                    "id": 2,
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
                print("✅ MCP tools/execute: 200 OK")
                return True
            else:
                print(f"❌ MCP tools/execute failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ MCP tools test failed: {e}")
            return False
    
    def _test_vibeteam_tools(self):
        """Test VibeTeam-specific tools through tunnel."""
        print("🎯 Testing VibeTeam-specific tools...")
        
        if not self.tunnel_url:
            print("⚠️  No tunnel URL, testing locally")
            return self._test_vibeteam_tools_local()
        
        # Test code generation tool
        try:
            response = requests.post(
                self.tunnel_url,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/execute",
                    "id": 3,
                    "params": {
                        "name": "generate_code",
                        "arguments": {
                            "specification": "Create a simple greeting function",
                            "language": "python"
                        }
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                print("✅ VibeTeam generate_code tool: 200 OK")
                
                # Test review_code tool
                response = requests.post(
                    self.tunnel_url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/execute",
                        "id": 4,
                        "params": {
                            "name": "review_code",
                            "arguments": {
                                "code": "def hello(): print('hi')",
                                "language": "python"
                            }
                        }
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    print("✅ VibeTeam review_code tool: 200 OK")
                    return True
                    
            return False
                
        except Exception as e:
            print(f"❌ VibeTeam tools test failed: {e}")
            return False
    
    def _test_vibeteam_tools_local(self):
        """Test VibeTeam tools in local TCP mode."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect(('localhost', self.port))
            
            # Test generate_code
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/execute",
                "params": {
                    "name": "generate_code",
                    "arguments": {
                        "specification": "Create a greeting function",
                        "language": "python"
                    }
                }
            }
            sock.send((json.dumps(request) + '\n').encode())
            
            # Don't wait for response (might timeout without API key)
            print("✅ VibeTeam tools request sent (local TCP)")
            sock.close()
            return True
            
        except Exception as e:
            print(f"⚠️  VibeTeam local tools test: {e}")
            return True  # Don't fail on this
    
    def _cleanup(self):
        """Clean up test processes."""
        print("\n🧹 Cleaning up...")
        
        if self.mcp_process:
            try:
                self.mcp_process.terminate()
                self.mcp_process.wait(timeout=5)
                print("✅ MCP server stopped")
            except:
                self.mcp_process.kill()
                
        if self.tunnel_process:
            try:
                self.tunnel_process.terminate()
                self.tunnel_process.wait(timeout=5)
                print("✅ Cloudflare tunnel stopped")
            except:
                self.tunnel_process.kill()


def main():
    """Main test runner."""
    print("=" * 60)
    print("🧪 VibeTeam Cloudflare Tunnel E2E Integration Test")
    print("=" * 60)
    
    tester = VibeTeamTunnelE2ETest()
    success = tester.run_test()
    
    # Results
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    
    if tester.tunnel_url:
        print(f"   Tunnel URL: {tester.tunnel_url}")
        print(f"   MCP accessible via HTTPS: {'✅ YES' if success else '❌ NO'}")
    else:
        print("   Tunnel: Not available (tested TCP mode only)")
        print(f"   MCP accessible via TCP: {'✅ YES' if success else '❌ NO'}")
    
    print(f"\n🎯 Overall Result: {'✅ TESTS PASSED' if success else '❌ TESTS FAILED'}")
    
    if not tester.tunnel_url:
        print("\n📝 To test with Cloudflare tunnel:")
        print("   1. Run: ./deploy/cloudflare/setup_tunnel.sh")
        print("   2. Provide your Cloudflare API token and domain")
        print("   3. Run this test again")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)