# MCP Server Deployment Guide

This guide provides instructions for deploying the MCP Software Engineer Server with various options from local development to production.

## Option 1: Cloudflare Tunnel (Recommended for Production)

**Best for**: Secure, production-grade access without a public IP

### Features
- Free HTTPS with automatic Let's Encrypt certificates
- Protection behind Cloudflare's global network
- Optional SSO/authentication via Cloudflare Access
- No need for a public IP address

### Quick Start

1. **Prerequisites**
   - A domain managed by Cloudflare
   - Cloudflare API Token with:
     - Zone.DNS:Edit
     - Account.Cloudflare Tunnel:Edit

2. **Run the setup script**:
   ```bash
   chmod +x deploy/cloudflare/setup_tunnel.sh
   ./deploy/cloudflare/setup_tunnel.sh
   ```

3. **Follow the prompts** to provide:
   - Your Cloudflare API Token
   - Your domain (e.g., `example.com`)
   - Desired subdomain (e.g., `mcp` for `mcp.example.com`)

4. **Access your MCP Server** at `https://your-subdomain.your-domain.com`

For detailed instructions, see [deploy/cloudflare/README.md](./deploy/cloudflare/README.md)

## Option 2: Localhost Deployment (FREE)

**Best for**: Development, testing, local control

### Quick Start
```bash
# 1. Setup environment
chmod +x setup_localhost.sh
./setup_localhost.sh

# 2. Start the server
python3 run_mcp_server.py
```

### External Access (Optional)
If you need external access (e.g., for ChatGPT app):

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com

# Expose local server
ngrok http 8080
```

Use the ngrok URL in your ChatGPT app configuration.

---

## Option 2: Remote Cloud Deployment

### Recommended Providers (Cheapest to Most Expensive)

1. **Hetzner Cloud** - €3.29/month (CX11 instance)
   - 1 vCPU, 2GB RAM, 20GB SSD
   - Best value for money
   - EU-based

2. **DigitalOcean** - $4/month (Basic Droplet)
   - 1 vCPU, 1GB RAM, 25GB SSD
   - Easy to use, good documentation

3. **Scaleway** - €2.99/month (DEV1-S)
   - 2 vCPU, 2GB RAM, 20GB SSD
   - Good for EU users

4. **Linode** - $5/month (Nanode)
   - 1 vCPU, 1GB RAM, 25GB SSD
   - Reliable performance

### Deployment Methods

#### Method A: Docker Deployment (Recommended)

```bash
# 1. Clone repository on your server
git clone <your-repo-url>
cd ai-coding-supervisor

# 2. Build and run with Docker Compose
docker-compose up -d

# 3. With HTTPS (optional)
docker-compose --profile with-nginx up -d
```

#### Method B: Direct VPS Deployment

```bash
# 1. Clone repository
git clone <your-repo-url>
cd ai-coding-supervisor

# 2. Run deployment script
chmod +x deploy_remote.sh
sudo ./deploy_remote.sh
```

### Server Setup Steps

1. **Create VPS Instance**
   - Choose Ubuntu 20.04/22.04 LTS
   - Minimum: 1GB RAM, 1 vCPU
   - Enable firewall, allow SSH (22) and HTTP (80/443)

2. **Initial Server Setup**
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y
   
   # Install Docker (for Docker method)
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Deploy Application**
   - Follow Method A or B above

4. **Configure Domain (Optional)**
   - Point your domain to server IP
   - Update nginx.conf with your domain
   - Get SSL certificate (Let's Encrypt recommended)

### Security Considerations

- Change default SSH port
- Use SSH keys instead of passwords
- Configure firewall (UFW)
- Regular security updates
- Consider API authentication for production

---

## Cost Comparison

| Provider | Instance | Monthly Cost | Specs |
|----------|----------|--------------|-------|
| **Hetzner** | CX11 | €3.29 | 1 vCPU, 2GB RAM |
| **DigitalOcean** | Basic | $4.00 | 1 vCPU, 1GB RAM |
| **Scaleway** | DEV1-S | €2.99 | 2 vCPU, 2GB RAM |
| **Linode** | Nanode | $5.00 | 1 vCPU, 1GB RAM |
| **Localhost** | - | FREE | Your machine |

**Recommendation**: Hetzner Cloud CX11 offers the best value with 2GB RAM for €3.29/month.

---

## Monitoring and Maintenance

### Check Service Status
```bash
# Docker deployment
docker-compose ps
docker-compose logs -f

# Systemd deployment
sudo systemctl status mcp-server
sudo journalctl -u mcp-server -f
```

### Update Deployment
```bash
# Docker method
git pull
docker-compose build
docker-compose up -d

# Systemd method
git pull
sudo systemctl restart mcp-server
```

### Backup Important Data
```bash
# Backup logs and configuration
tar -czf mcp-backup-$(date +%Y%m%d).tar.gz logs/ *.yml *.conf
```

---

## Troubleshooting

### Common Issues

1. **Port 8080 not accessible**
   - Check firewall: `sudo ufw status`
   - Allow port: `sudo ufw allow 8080`

2. **Service won't start**
   - Check logs: `sudo journalctl -u mcp-server -n 50`
   - Verify dependencies: `pip list`

3. **High memory usage**
   - Monitor with: `htop` or `docker stats`
   - Consider upgrading to 2GB RAM instance

4. **SSL certificate issues**
   - Use Let's Encrypt: `sudo certbot --nginx`
   - Verify certificate: `openssl s_client -connect yourdomain.com:443`

### Getting Help

- Check server logs for error messages
- Verify all dependencies are installed
- Ensure correct file permissions
- Test locally first before deploying remotely

---

## Next Steps

After deployment:

1. Test the MCP server connection
2. Configure your ChatGPT app to use the server URL
3. Set up monitoring and alerts
4. Plan for regular backups and updates
5. Consider scaling if needed
