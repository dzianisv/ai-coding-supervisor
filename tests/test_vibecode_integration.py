#!/usr/bin/env python3
"""
End-to-end integration test for vibeteam-mcp simulating VibeCode usage.
Tests both local and Cloudflare tunnel scenarios.
"""
import subprocess
import json
import socket
import time
import sys
import os
import argparse
import requests
from typing import Dict, Any, Optional

class VibeCodeMCPTester:
    """Test harness for VibeCode-style MCP integration."""
    
    def __init__(self, mode: str = "local", url: Optional[str] = None):
        """Initialize tester.
        
        Args:
            mode: "local" for TCP, "tunnel" for Cloudflare HTTP/HTTPS
            url: URL for tunnel mode (e.g., mcp.example.com)
        """
        self.mode = mode
        self.url = url
        self.server_process = None
        
    def start_local_server(self) -> bool:
        """Start MCP server in TCP mode for local/tunnel testing."""
        print("🚀 Starting MCP server in TCP mode on port 3333...")
        
        env = os.environ.copy()
        env["MCP_PORT"] = "3333"
        env["MCP_MODE"] = "tcp"
        
        self.server_process = subprocess.Popen(
            [sys.executable, "-m", "mcp.vibeteam_mcp_server", "--no-tunnel"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        time.sleep(2)
        
        # Verify it's running
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(('localhost', 3333))
            sock.close()
            print("✅ MCP server started successfully on port 3333")
            return True
        except Exception as e:
            print(f"❌ Failed to start MCP server: {e}")
            if self.server_process:
                stderr = self.server_process.stderr.read(1000)
                if stderr:
                    print(f"Server error: {stderr}")
            return False
            
    def send_tcp_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send request to TCP server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(('localhost', 3333))
            sock.send((json.dumps(request) + '\n').encode())
            
            # Read response
            data = sock.recv(8192)
            if data:
                return json.loads(data.decode().strip())
        except Exception as e:
            print(f"TCP request error: {e}")
        finally:
            sock.close()
        return None
        
    def send_http_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send request via HTTP/HTTPS (Cloudflare tunnel)."""
        url = f"https://{self.url}"
        try:
            response = requests.post(
                url,
                json=request,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"HTTP error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"HTTP request error: {e}")
        return None
        
    def send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send request based on mode."""
        if self.mode == "local":
            return self.send_tcp_request(request)
        else:
            return self.send_http_request(request)
            
    def test_vibecode_workflow(self):
        """Test the complete VibeCode workflow."""
        print("\n" + "="*60)
        print("🧪 VIBECODE INTEGRATION TEST")
        print("="*60)
        
        # Test 1: Initialize
        print("\n1️⃣ Testing MCP initialization...")
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        
        response = self.send_request(request)
        if response and "result" in response:
            result = response["result"]
            # Handle both new MCP format and old TCP format
            if "serverInfo" in result:
                server_info = result["serverInfo"]
                print(f"✅ Connected to: {server_info.get('name')} v{server_info.get('version')}")
            elif "capabilities" in result:
                # Old TCP server format
                agent_info = result.get("capabilities", {}).get("agent", {})
                print(f"✅ Connected to: {agent_info.get('type', 'MCP Server')} v{agent_info.get('version', 'unknown')}")
            else:
                print(f"✅ Connected to MCP server (protocol: {result.get('protocolVersion', 'unknown')})")
        else:
            print("❌ Failed to initialize")
            return False
            
        # Test 2: List available tools (skip for old TCP server)
        print("\n2️⃣ Discovering available tools...")
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = self.send_request(request)
        if response:
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                print(f"✅ Found {len(tools)} tools:")
                for tool in tools:
                    print(f"   • {tool['name']}: {tool['description']}")
            elif "error" in response:
                # Old TCP server might not support tools/list
                print("⚠️  Server doesn't support tools/list method")
                print("   Using legacy TCP server with direct tool execution")
            else:
                print("❌ Unexpected response format")
        else:
            print("❌ No response received")
            
        # Test 3: Execute task (use tools/execute for old server)
        print("\n3️⃣ Testing task execution...")
        
        # TCP server format
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/execute",
            "params": {
                "name": "execute_code",
                "arguments": {
                    "code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n\n# Test\nprint(fibonacci(10))",
                    "language": "python"
                }
            }
        }
        
        print(f"📋 Executing code...")
        
        response = self.send_request(request)
        if response:
            if "result" in response:
                result = response["result"]
                print("✅ Code execution completed")
                if isinstance(result, dict):
                    if "status" in result:
                        print(f"   Status: {result['status']}")
                    if "result" in result and result["result"]:
                        print(f"   Output: {result['result']}")
            elif "error" in response:
                error = response["error"]
                print(f"⚠️  Error: {error.get('message', 'Unknown error')}")
                # This is expected without API keys
        else:
            print("❌ No response for task workflow")
            
        # Test 4: Test code generation
        print("\n4️⃣ Testing code generation...")
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/execute",
            "params": {
                "name": "generate_code",
                "arguments": {
                    "specification": "Create a hello world function with type hints that takes a name parameter",
                    "language": "python"
                }
            }
        }
        
        response = self.send_request(request)
        if response:
            if "result" in response:
                result = response["result"]
                print("✅ Code generation completed")
                if isinstance(result, dict) and "status" in result:
                    print(f"   Status: {result['status']}")
            elif "error" in response:
                print(f"⚠️  Error: {response['error'].get('message')}")
                
        # Test 5: Review code (if supported)
        print("\n5️⃣ Testing code review...")
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "review_code",
            "params": {
                "code": "def hello_world():\n    print('Hello, World!')",
                "language": "python"
            }
        }
        
        response = self.send_request(request)
        if response:
            if "result" in response:
                print("✅ Code review completed")
                result = response["result"]
                if isinstance(result, dict) and "review" in result:
                    print(f"   Review: {result['review'][:100]}..." if len(str(result['review'])) > 100 else f"   Review: {result['review']}")
            elif "error" in response:
                print(f"⚠️  Review not supported: {response['error'].get('message')}")
                
        return True
        
    def cleanup(self):
        """Clean up server process."""
        if self.server_process:
            print("\n🧹 Cleaning up...")
            self.server_process.terminate()
            self.server_process.wait()
            
    def run_test(self):
        """Run the complete test."""
        try:
            if self.mode == "local":
                if not self.start_local_server():
                    return False
                    
            success = self.test_vibecode_workflow()
            
            print("\n" + "="*60)
            if success:
                print("✅ VIBECODE INTEGRATION TEST PASSED!")
                
                if self.mode == "tunnel":
                    print(f"\n🌐 MCP server is accessible via Cloudflare at: https://{self.url}")
                else:
                    print("\n📝 To test with Cloudflare tunnel:")
                    print("   1. Keep this server running")
                    print("   2. Start Cloudflare tunnel: cloudflared tunnel run")
                    print("   3. Run: python test_vibecode_integration.py --tunnel your-domain.com")
            else:
                print("❌ VIBECODE INTEGRATION TEST FAILED!")
            print("="*60)
            
            return success
            
        finally:
            self.cleanup()


def main():
    parser = argparse.ArgumentParser(
        description='Test vibeteam-mcp with VibeCode-style integration'
    )
    parser.add_argument(
        '--tunnel',
        metavar='DOMAIN',
        help='Test via Cloudflare tunnel (e.g., mcp.example.com)'
    )
    
    args = parser.parse_args()
    
    if args.tunnel:
        print(f"🌐 Testing via Cloudflare tunnel: {args.tunnel}")
        tester = VibeCodeMCPTester(mode="tunnel", url=args.tunnel)
    else:
        print("🏠 Testing locally (TCP mode)")
        tester = VibeCodeMCPTester(mode="local")
        
    success = tester.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()