# Cloudflare Tunnel for MCP Server

**Note**: These scripts provide advanced tunnel configuration. For simple usage, `vibeteam-mcp` now includes integrated tunnel support - just run `vibeteam-mcp` and it automatically creates a tunnel.

This directory contains scripts to set up a secure Cloudflare Tunnel for your MCP Server, providing:

- Free HTTPS with automatic Let's Encrypt certificates
- Protection behind Cloudflare's global network
- Optional SSO/authentication via Cloudflare Access
- No need for a public IP address

## Prerequisites

1. A domain managed by Cloudflare
2. Cloudflare API Token with:
   - Zone.DNS:Edit
   - Account.Cloudflare Tunnel:Edit
3. Linux/macOS with `curl`, `jq`, and `openssl`

## Quick Start

1. Make the script executable:
   ```bash
   chmod +x setup_tunnel.sh
   ```

2. Run the setup script:
   ```bash
   ./setup_tunnel.sh
   ```

3. Follow the prompts to provide:
   - Your Cloudflare API Token
   - Your domain (e.g., `example.com`)
   - Desired subdomain (e.g., `mcp` for `mcp.example.com`)

## Features

- **Automatic Installation**: Installs `cloudflared` if not present
- **Secure Configuration**: Generates secure tunnel credentials
- **DNS Management**: Automatically creates the required DNS records
- **Systemd Service**: Option to run as a background service
- **Cross-Platform**: Works on Linux and macOS

## Advanced Usage

### Run as Systemd Service (Recommended)

If you run the script as root, it will automatically create and enable a systemd service:

```bash
sudo ./setup_tunnel.sh
```

### Manual Tunnel Management

- **Start tunnel**: `cloudflared tunnel --config ~/.cloudflared/config.yml run`
- **List tunnels**: `cloudflared tunnel list`
- **View logs**: `journalctl -u cloudflared-mcp.service -f` (if using systemd)

## Security Considerations

1. **API Token Security**:
   - The token is only used during setup and not stored
   - Use the principle of least privilege when creating the token

2. **Tunnel Security**:
   - The tunnel uses a randomly generated secret
   - Credentials are stored with restricted permissions (600)

3. **Access Control**:
   - Consider enabling Cloudflare Access for additional security
   - Rate limiting rules can be added in the Cloudflare dashboard

## Troubleshooting

- **Permission Denied**: Ensure the script is executable (`chmod +x setup_tunnel.sh`)
- **API Errors**: Verify your token has the correct permissions
- **Connection Issues**: Check if the MCP Server is running on port 3333

## Next Steps

1. **Enable Cloudflare Access** for SSO protection
2. **Set up monitoring** for the tunnel
3. **Configure backups** of your tunnel credentials

## License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.
