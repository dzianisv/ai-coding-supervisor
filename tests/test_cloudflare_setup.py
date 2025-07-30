"""
Test Cloudflare tunnel setup and configuration.
"""
import os
import subprocess
import pytest
from pathlib import Path


class TestCloudflareSetup:
    """Test Cloudflare tunnel configuration."""
    
    def test_setup_script_exists(self):
        """Test that the setup script exists and is executable."""
        script_path = Path(__file__).parent.parent / "deploy" / "cloudflare" / "setup_tunnel.sh"
        assert script_path.exists(), f"Setup script not found at {script_path}"
        
        # Check if executable
        stat_info = os.stat(script_path)
        assert stat_info.st_mode & 0o111, "Setup script is not executable"
        
    def test_cloudflare_readme_exists(self):
        """Test that Cloudflare documentation exists."""
        readme_path = Path(__file__).parent.parent / "deploy" / "cloudflare" / "README.md"
        assert readme_path.exists(), f"README not found at {readme_path}"
        
        # Check content
        content = readme_path.read_text()
        assert "Cloudflare" in content
        assert "tunnel" in content.lower()
        
    def test_setup_script_syntax(self):
        """Test that the setup script has valid bash syntax."""
        script_path = Path(__file__).parent.parent / "deploy" / "cloudflare" / "setup_tunnel.sh"
        
        # Use bash -n to check syntax without executing
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Script syntax error: {result.stderr}"
        
    def test_mcp_server_config_compatibility(self):
        """Test that MCP server configuration is compatible with Cloudflare."""
        # Check that the MCP server can bind to localhost:3333 (as configured in Cloudflare script)
        config_path = Path(__file__).parent.parent / "deploy" / "cloudflare" / "setup_tunnel.sh"
        
        content = config_path.read_text()
        # Verify the script configures the correct port
        assert "localhost:3333" in content or "127.0.0.1:3333" in content
        
    def test_systemd_service_template(self):
        """Test that systemd service configuration is present in the script."""
        script_path = Path(__file__).parent.parent / "deploy" / "cloudflare" / "setup_tunnel.sh"
        content = script_path.read_text()
        
        # Check for systemd service configuration
        assert "systemd" in content
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content
        
    def test_required_permissions_documented(self):
        """Test that required Cloudflare permissions are documented."""
        readme_path = Path(__file__).parent.parent / "deploy" / "cloudflare" / "README.md"
        content = readme_path.read_text()
        
        # Check for permission requirements
        assert "DNS:Edit" in content or "permissions" in content.lower()
        assert "Tunnel:Edit" in content or "tunnel" in content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])