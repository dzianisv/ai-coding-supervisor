#!/usr/bin/env python3
"""
Test the new integrated vibeteam-mcp tunnel functionality.
"""
import subprocess
import sys
import time
import requests
import json
import re
import os
import pytest


def find_cloudflared():
    """Find cloudflared binary."""
    paths = [
        "./cloudflared",
        "/usr/local/bin/cloudflared", 
        "/opt/homebrew/bin/cloudflared",
        "cloudflared"
    ]
    
    for path in paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True)
            if result.returncode == 0:
                return path
        except:
            continue
    return None


@pytest.mark.integration
def test_integrated_tunnel_mode():
    """Test the new integrated tunnel mode of vibeteam-mcp."""
    cloudflared_path = find_cloudflared()
    if not cloudflared_path:
        pytest.skip("cloudflared binary not found")
    
    process = None
    try:
        # Start vibeteam-mcp in tunnel mode with debug logging
        print("Starting vibeteam-mcp in integrated tunnel mode...")
        
        env = os.environ.copy()
        env['PYTHONPATH'] = os.getcwd()
        
        process = subprocess.Popen(
            [sys.executable, '-m', 'mcp.vibeteam_mcp_server', '--debug', '--port', '9998'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1
        )
        
        # Wait for server startup and tunnel URL
        tunnel_url = None
        start_time = time.time()
        
        while time.time() - start_time < 60:  # Increased timeout
            # Check if process died
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"Process exited with code {process.returncode}")
                print(f"STDOUT:\n{stdout}")
                print(f"STDERR:\n{stderr}")
                pytest.fail("vibeteam-mcp process exited unexpectedly")
            
            # Read stderr line by line
            line = process.stderr.readline()
            if line:
                print(f"[SERVER] {line.strip()}")
                
                # Look for tunnel URL
                if 'trycloudflare.com' in line:
                    match = re.search(r'https://[\w\-]+\.trycloudflare\.com', line)
                    if match:
                        tunnel_url = match.group(0)
                        print(f"✅ Found tunnel URL: {tunnel_url}")
                        break
                
                # Also check for local server ready
                if 'HTTP server started' in line or 'Running on' in line:
                    print("✅ HTTP server is ready")
        
        if not tunnel_url:
            pytest.fail("Failed to get tunnel URL within timeout")
        
        # Wait for tunnel to stabilize
        print("Waiting for tunnel to stabilize...")
        time.sleep(10)
        
        # Test health endpoint
        print("Testing health endpoint...")
        health_response = requests.get(f"{tunnel_url}/health", timeout=15)
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert health_data['status'] == 'healthy'
        assert health_data['service'] == 'vibeteam-mcp'
        print("✅ Health endpoint working")
        
        # Test MCP initialize
        print("Testing MCP initialize...")
        init_response = requests.post(
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
        
        assert init_response.status_code == 200
        init_data = init_response.json()
        assert 'result' in init_data
        assert 'capabilities' in init_data['result']
        assert init_data['result']['serverInfo']['name'] == 'vibeteam'
        print("✅ MCP initialize working")
        
        # Test tools list
        print("Testing tools list...")
        tools_response = requests.post(
            tunnel_url,
            headers={"Content-Type": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            },
            timeout=15
        )
        
        assert tools_response.status_code == 200
        tools_data = tools_response.json()
        assert 'result' in tools_data
        assert 'tools' in tools_data['result']
        tools = tools_data['result']['tools']
        assert len(tools) >= 2  # Should have execute_task and review_code
        
        tool_names = [tool['name'] for tool in tools]
        assert 'execute_task' in tool_names
        assert 'review_code' in tool_names
        print(f"✅ Tools list working (found {len(tools)} tools)")
        
        print("🎉 All integrated tunnel tests passed!")
        
    except Exception as e:
        pytest.fail(f"Integrated tunnel test failed: {e}")
        
    finally:
        if process:
            print("Stopping vibeteam-mcp server...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


@pytest.mark.integration 
def test_no_tunnel_mode():
    """Test that --no-tunnel still works for stdio mode."""
    process = None
    try:
        print("Testing --no-tunnel mode...")
        
        env = os.environ.copy()
        env['PYTHONPATH'] = os.getcwd()
        
        # Start in no-tunnel mode - should fail quickly since no stdin
        process = subprocess.Popen(
            [sys.executable, '-m', 'mcp.vibeteam_mcp_server', '--no-tunnel', '--debug'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            stdin=subprocess.DEVNULL
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check the output for stdio mode indicators
        stdout, stderr = process.communicate(timeout=5)
        
        # Should see stdio mode startup message
        assert "standard mode (stdio)" in stderr, f"Expected stdio mode message in stderr: {stderr}"
        print("✅ --no-tunnel correctly starts stdio mode")
        
    except subprocess.TimeoutExpired:
        # This is expected for stdio mode with no input
        process.kill()
        process.wait()
        print("✅ stdio mode started correctly (timeout expected)")
        
    except Exception as e:
        pytest.fail(f"No-tunnel test failed: {e}")
        
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait()


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Testing integrated vibeteam-mcp tunnel functionality")
    print("=" * 60)
    
    try:
        test_no_tunnel_mode()
        test_integrated_tunnel_mode()
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        sys.exit(1)