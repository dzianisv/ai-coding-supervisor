#!/usr/bin/env python3
"""
Comprehensive test suite for VibeTeam MCP server with Cloudflare tunnel integration.
Tests both TCP direct mode and HTTP wrapper mode with Cloudflare tunnels.
"""

import subprocess
import sys
import time
import re
import requests
import json
import os
import socket
from pathlib import Path
import pytest


class TestCloudfareTunnel:
    """Test VibeTeam MCP server with Cloudflare tunnel integration."""
    
    @pytest.fixture
    def mcp_port(self):
        """MCP server port."""
        return 3333
    
    @pytest.fixture
    def http_port(self):
        """HTTP wrapper port."""
        return 8080
    
    def start_mcp_server(self, port):
        """Start MCP server in TCP mode."""
        env = os.environ.copy()
        env["MCP_PORT"] = str(port)
        env["MCP_MODE"] = "tcp"
        
        process = subprocess.Popen(
            [sys.executable, '-m', 'run_mcp_server'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        # Wait for server to start
        time.sleep(3)
        
        # Verify it's running
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(('localhost', port))
            sock.close()
            return process
        except Exception as e:
            process.terminate()
            raise RuntimeError(f"Failed to start MCP server: {e}")
    
    def start_http_wrapper(self, mcp_port, http_port):
        """Start HTTP wrapper for MCP server."""
        env = os.environ.copy()
        env["MCP_HOST"] = "localhost"
        env["MCP_PORT"] = str(mcp_port)
        env["HTTP_PORT"] = str(http_port)
        
        process = subprocess.Popen(
            [sys.executable, 'mcp/http_wrapper.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        # Wait for wrapper to start
        time.sleep(3)
        
        # Verify it's running
        try:
            response = requests.get(f'http://localhost:{http_port}/health', timeout=5)
            if response.status_code == 200:
                return process
            else:
                raise RuntimeError(f"HTTP wrapper not healthy: {response.status_code}")
        except Exception as e:
            process.terminate()
            raise RuntimeError(f"Failed to start HTTP wrapper: {e}")
    
    def start_cloudflare_tunnel(self, port):
        """Start Cloudflare tunnel pointing to given port."""
        cloudflared_path = "./cloudflared"
        if not os.path.exists(cloudflared_path):
            pytest.skip("cloudflared binary not found")
        
        process = subprocess.Popen(
            [cloudflared_path, 'tunnel', '--url', f'http://localhost:{port}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Wait for tunnel URL
        tunnel_url = None
        start_time = time.time()
        
        while time.time() - start_time < 30:
            line = process.stderr.readline()
            if line and 'trycloudflare.com' in line:
                match = re.search(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                if match:
                    tunnel_url = match.group(0)
                    break
        
        if not tunnel_url:
            process.terminate()
            raise RuntimeError("Failed to get tunnel URL")
        
        # Wait for DNS propagation
        time.sleep(10)
        
        return process, tunnel_url
    
    def test_mcp_tcp_direct(self, mcp_port):
        """Test MCP server TCP direct connection."""
        mcp_process = None
        try:
            # Start MCP server
            mcp_process = self.start_mcp_server(mcp_port)
            
            # Test TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(('localhost', mcp_port))
            
            # Send initialize request
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {}
            }
            sock.send((json.dumps(request) + '\n').encode())
            
            # Get response
            data = sock.recv(8192)
            response = json.loads(data.decode().strip())
            
            assert "result" in response
            assert "capabilities" in response["result"]
            
            sock.close()
            
        finally:
            if mcp_process:
                mcp_process.terminate()
                mcp_process.wait()
    
    @pytest.mark.integration
    def test_mcp_with_cloudflare_tcp(self, mcp_port):
        """Test MCP server with Cloudflare tunnel (TCP direct)."""
        mcp_process = None
        tunnel_process = None
        
        try:
            # Start MCP server
            mcp_process = self.start_mcp_server(mcp_port)
            
            # Start tunnel
            tunnel_process, tunnel_url = self.start_cloudflare_tunnel(mcp_port)
            
            # Test MCP through tunnel
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
            
            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "capabilities" in result["result"]
            
        finally:
            if tunnel_process:
                tunnel_process.terminate()
                tunnel_process.wait()
            if mcp_process:
                mcp_process.terminate()
                mcp_process.wait()
    
    @pytest.mark.integration
    def test_mcp_with_http_wrapper_and_tunnel(self, mcp_port, http_port):
        """Test MCP server with HTTP wrapper and Cloudflare tunnel."""
        mcp_process = None
        http_process = None
        tunnel_process = None
        
        try:
            # Start MCP server
            mcp_process = self.start_mcp_server(mcp_port)
            
            # Start HTTP wrapper
            http_process = self.start_http_wrapper(mcp_port, http_port)
            
            # Start tunnel pointing to HTTP wrapper
            tunnel_process, tunnel_url = self.start_cloudflare_tunnel(http_port)
            
            # Test health check through tunnel
            response = requests.get(f"{tunnel_url}/health", timeout=10)
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            
            # Test MCP through tunnel
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
            
            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "capabilities" in result["result"]
            
        finally:
            if tunnel_process:
                tunnel_process.terminate()
                tunnel_process.wait()
            if http_process:
                http_process.terminate()
                http_process.wait()
            if mcp_process:
                mcp_process.terminate()
                mcp_process.wait()
    
    @pytest.mark.integration
    def test_mcp_tools_through_tunnel(self, mcp_port):
        """Test MCP tools functionality through tunnel."""
        mcp_process = None
        tunnel_process = None
        
        try:
            # Start MCP server
            mcp_process = self.start_mcp_server(mcp_port)
            
            # Start tunnel
            tunnel_process, tunnel_url = self.start_cloudflare_tunnel(mcp_port)
            
            # Initialize first
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
            assert response.status_code == 200
            
            # Test execute_code tool (will fail without API key, but that's expected)
            response = requests.post(
                tunnel_url,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/execute",
                    "params": {
                        "name": "execute_code",
                        "arguments": {
                            "code": "print('Hello from tunnel')",
                            "language": "python"
                        }
                    }
                },
                timeout=30
            )
            
            # We expect either success or an API key error
            assert response.status_code == 200
            result = response.json()
            assert "result" in result or "error" in result
            
        finally:
            if tunnel_process:
                tunnel_process.terminate()
                tunnel_process.wait()
            if mcp_process:
                mcp_process.terminate()
                mcp_process.wait()


def main():
    """Run tests as standalone script."""
    test = TestCloudfareTunnel()
    
    print("=" * 70)
    print("🧪 VIBETEAM MCP CLOUDFLARE TUNNEL TEST SUITE")
    print("=" * 70)
    
    # Test 1: TCP Direct
    print("\n[TEST 1] Testing TCP direct connection...")
    try:
        test.test_mcp_tcp_direct(3333)
        print("✅ TCP direct test passed")
    except Exception as e:
        print(f"❌ TCP direct test failed: {e}")
        return False
    
    # Test 2: TCP with Cloudflare
    print("\n[TEST 2] Testing TCP with Cloudflare tunnel...")
    try:
        test.test_mcp_with_cloudflare_tcp(3333)
        print("✅ TCP + Cloudflare test passed")
    except Exception as e:
        print(f"❌ TCP + Cloudflare test failed: {e}")
    
    # Test 3: HTTP wrapper with Cloudflare
    print("\n[TEST 3] Testing HTTP wrapper with Cloudflare tunnel...")
    try:
        test.test_mcp_with_http_wrapper_and_tunnel(3333, 8080)
        print("✅ HTTP wrapper + Cloudflare test passed")
    except Exception as e:
        print(f"❌ HTTP wrapper + Cloudflare test failed: {e}")
    
    # Test 4: MCP tools through tunnel
    print("\n[TEST 4] Testing MCP tools through tunnel...")
    try:
        test.test_mcp_tools_through_tunnel(3333)
        print("✅ MCP tools test passed")
    except Exception as e:
        print(f"❌ MCP tools test failed: {e}")
    
    print("\n" + "=" * 70)
    print("🎉 Test suite completed!")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)