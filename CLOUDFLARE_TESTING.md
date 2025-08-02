# Testing MCP Server with Cloudflare Tunnel

This guide explains how to test the VibeTeam MCP server end-to-end with Cloudflare tunnel for public access.

## Prerequisites

1. Domain managed by Cloudflare
2. Cloudflare API token with DNS:Edit and Tunnel:Edit permissions
3. MCP server working locally (verified ✅)

## Local Testing (Completed ✅)

The MCP server has been tested and verified to work in both modes:

### 1. TCP Mode (Port 3333) - For Cloudflare
```bash
# Start server
MCP_PORT=3333 MCP_MODE=tcp vibeteam-mcp

# Server is accessible at http://localhost:3333
```

### 2. STDIO Mode - Standard MCP
```bash
# Start server
vibeteam-mcp

# Communicates via stdin/stdout
```

## Cloudflare Tunnel Setup

### Step 1: Run Setup Script
```bash
cd deploy/cloudflare
chmod +x setup_tunnel.sh
./setup_tunnel.sh
```

You'll be prompted for:
- Cloudflare API Token
- Your domain (e.g., example.com)
- Subdomain (e.g., mcp)

### Step 2: Verify Tunnel Configuration
The script will:
1. Install cloudflared if needed
2. Create tunnel with secure credentials
3. Set up DNS record (mcp.example.com → tunnel)
4. Configure tunnel to forward to localhost:3333

### Step 3: Start Services

1. Start MCP server in TCP mode:
```bash
MCP_PORT=3333 MCP_MODE=tcp vibeteam-mcp
```

2. Start Cloudflare tunnel:
```bash
cloudflared tunnel --config ~/.cloudflared/config.yml run
```

Or as a systemd service (if configured):
```bash
sudo systemctl start cloudflared-mcp
```

## Testing Public Access

### Using the Test Client
```bash
# Test over HTTPS (through Cloudflare)
python3 test_mcp_http_client.py mcp.yourdomain.com

# Test locally
python3 test_mcp_http_client.py localhost:3333 --http
```

### Manual Testing with curl
```bash
# Initialize
curl -X POST https://mcp.yourdomain.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# List tools
curl -X POST https://mcp.yourdomain.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Execute tasks
curl -X POST https://mcp.yourdomain.com \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "complete_tasks",
      "arguments": {
        "tasks": [
          "Create a Python function to calculate factorial",
          "Add docstring and type hints"
        ]
      }
    }
  }'
```

## Current Status

✅ **Local Testing**: MCP server verified working on port 3333
✅ **Protocol Support**: Both TCP (for tunnel) and stdio (standard MCP) modes work
✅ **Tool Registration**: 8 tools available including task completion
✅ **Ready for Cloudflare**: Server compatible with tunnel forwarding

⏳ **Pending**: Cloudflare tunnel setup (requires API token and domain)

## Security Considerations

1. **Authentication**: Consider adding Cloudflare Access for SSO
2. **Rate Limiting**: Configure in Cloudflare dashboard
3. **API Keys**: Set ANTHROPIC_API_KEY environment variable for Claude
4. **HTTPS Only**: Cloudflare provides automatic SSL/TLS

## Troubleshooting

### MCP Server Issues
- Check logs: `tail -f vibeteam-mcp.log`
- Verify port 3333 is not in use: `lsof -i :3333`

### Cloudflare Tunnel Issues
- Check tunnel status: `cloudflared tunnel list`
- View logs: `journalctl -u cloudflared-mcp -f`
- Verify DNS: `dig mcp.yourdomain.com`

## Example Integration

Once publicly accessible, you can integrate with:
- ChatGPT (using MCP plugin)
- Custom AI assistants
- CI/CD pipelines
- Any MCP-compatible client

The server accepts task arrays, making it perfect for batch processing:
```json
{
  "tasks": [
    "Implement feature X",
    "Write tests for feature X",
    "Update documentation"
  ]
}
```