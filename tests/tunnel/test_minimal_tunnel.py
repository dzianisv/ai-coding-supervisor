#!/usr/bin/env python3
"""
Minimal E2E test for Cloudflare tunnel without requiring API keys.
Tests basic connectivity and tunnel creation.
"""

import subprocess
import time
import requests
import json
import re
import sys
import os
import pytest
import socket
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestMinimalCloudfareTunnel:
    """Test basic Cloudflare tunnel functionality without MCP server."""
    
    def test_cloudflare_tunnel_basic(self):
        """Test that we can create a Cloudflare tunnel and access it."""
        # Start a simple HTTP server using Python
        http_process = None
        tunnel_process = None
        port = 8888
        
        try:
            # Start simple HTTP server
            print("Starting simple HTTP server...")
            http_process = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Give it time to start
            time.sleep(2)
            
            # Verify server is running
            try:
                response = requests.get(f"http://localhost:{port}", timeout=5)
                print(f"✅ HTTP server running on port {port}")
            except:
                pytest.fail("Failed to start HTTP server")
            
            # Start cloudflare tunnel
            print("Starting Cloudflare tunnel...")
            
            # Try multiple locations for cloudflared
            cloudflared_paths = [
                "./cloudflared",
                "/usr/local/bin/cloudflared",
                "cloudflared"
            ]
            
            cloudflared_path = None
            for path in cloudflared_paths:
                try:
                    result = subprocess.run([path, "--version"], capture_output=True)
                    if result.returncode == 0:
                        cloudflared_path = path
                        break
                except:
                    continue
            
            if not cloudflared_path:
                pytest.skip("cloudflared binary not found")
            
            tunnel_process = subprocess.Popen(
                [cloudflared_path, "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for tunnel URL
            tunnel_url = None
            start_time = time.time()
            
            while time.time() - start_time < 30:
                line = tunnel_process.stderr.readline()
                if line:
                    print(f"[TUNNEL] {line.strip()}")
                    if 'trycloudflare.com' in line:
                        match = re.search(r'https://[\w\-]+\.trycloudflare\.com', line)
                        if match:
                            tunnel_url = match.group(0)
                            print(f"\n✅ Tunnel URL: {tunnel_url}")
                            break
            
            assert tunnel_url is not None, "Failed to get tunnel URL"
            
            # Wait for DNS propagation
            print("Waiting for tunnel to stabilize...")
            time.sleep(10)
            
            # Test the tunnel
            print(f"\nTesting access through tunnel: {tunnel_url}")
            
            try:
                response = requests.get(tunnel_url, timeout=15)
                assert response.status_code == 200
                assert "Directory listing" in response.text or "Index of" in response.text
                print("✅ Successfully accessed HTTP server through Cloudflare tunnel!")
                
            except Exception as e:
                pytest.fail(f"Failed to access through tunnel: {e}")
                
        finally:
            # Cleanup
            if tunnel_process:
                tunnel_process.terminate()
                tunnel_process.wait()
            if http_process:
                http_process.terminate()
                http_process.wait()
    
    def test_tcp_echo_server(self):
        """Test TCP connectivity without MCP complexity."""
        echo_process = None
        port = 9999
        
        try:
            # Create a simple echo server script
            echo_script = """
import socket
import sys

port = int(sys.argv[1])
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('0.0.0.0', port))
server.listen(1)
print(f"Echo server listening on port {port}", flush=True)

while True:
    conn, addr = server.accept()
    data = conn.recv(1024)
    if data:
        conn.send(data)
    conn.close()
"""
            
            with open("echo_server.py", "w") as f:
                f.write(echo_script)
            
            # Start echo server
            print(f"Starting echo server on port {port}...")
            echo_process = subprocess.Popen(
                [sys.executable, "echo_server.py", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for server to start
            time.sleep(2)
            
            # Test connection
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect(('localhost', port))
                
                # Send test message
                test_msg = b"Hello, Echo!"
                sock.send(test_msg)
                
                # Receive echo
                response = sock.recv(1024)
                assert response == test_msg
                
                sock.close()
                print("✅ Echo server working correctly")
                
            except Exception as e:
                pytest.fail(f"Failed to connect to echo server: {e}")
                
        finally:
            # Cleanup
            if echo_process:
                echo_process.terminate()
                echo_process.wait()
            if os.path.exists("echo_server.py"):
                os.remove("echo_server.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])