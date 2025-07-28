#!/usr/bin/env bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
DEFAULT_IMAGE="ubuntu-22.04"
DEFAULT_TYPE="cpx11"
DEFAULT_REGION="nbg1"
DEFAULT_DOMAIN="example.com"
DEFAULT_SSH_KEY="$HOME/.ssh/id_ed25519.pub"

# Check if hcloud CLI is installed
if ! command -v hcloud &> /dev/null; then
    echo -e "${YELLOW}⚠️  hcloud CLI not found. Installing...${NC}"
    curl -fsSL https://packages.hetzner.cloud/public/setup.sh | bash
    apt-get install -y hcloud
fi

# Check if HETZNER_TOKEN is set
if [ -z "$HETZNER_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  HETZNER_TOKEN environment variable is not set${NC}"
    echo "Please create a new token at: https://console.hetzner.cloud/projects"
    read -p "Enter your Hetzner Cloud API token: " HETZNER_TOKEN
    export HETZNER_TOKEN
fi

# Configure hcloud CLI
hcloud context create mcp-deploy > /dev/null 2>&1 || true
hcloud context use mcp-deploy > /dev/null

# Get user input with defaults
read -p "Enter server name [mcp-$(date +%s)]: " SERVER_NAME
SERVER_NAME=${SERVER_NAME:-mcp-$(date +%s)}

read -p "Enter server type [$DEFAULT_TYPE]: " SERVER_TYPE
SERVER_TYPE=${SERVER_TYPE:-$DEFAULT_TYPE}

read -p "Enter region [$DEFAULT_REGION]: " REGION
REGION=${REGION:-$DEFAULT_REGION}

read -p "Enter domain name [$DEFAULT_DOMAIN]: " DOMAIN
DOMAIN=${DOMAIN:-$DEFAULT_DOMAIN}

read -p "Enter path to SSH public key [$DEFAULT_SSH_KEY]: " SSH_KEY_PATH
SSH_KEY_PATH=${SSH_KEY_PATH:-$DEFAULT_SSH_KEY}

# Check if SSH key exists
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo -e "${YELLOW}⚠️  SSH key not found at $SSH_KEY_PATH${NC}"
    read -p "Would you like to generate a new SSH key pair? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p "$(dirname "$DEFAULT_SSH_KEY")"
        ssh-keygen -t ed25519 -f "${DEFAULT_SSH_KEY%.pub}" -N ""
        chmod 600 "${DEFAULT_SSH_KEY%.pub}"
        echo -e "${GREEN}✅ Generated new SSH key pair at ${DEFAULT_SSH_KEY%.pub}${NC}"
    else
        echo -e "${YELLOW}⚠️  Please provide a valid SSH public key path and try again.${NC}"
        exit 1
    fi
fi

# Add SSH key to Hetzner Cloud
SSH_KEY_NAME="mcp-$(whoami)-$(date +%Y%m%d)"
SSH_PUBLIC_KEY=$(cat "$SSH_KEY_PATH")

if ! hcloud ssh-key list | grep -q "$SSH_PUBLIC_KEY"; then
    echo -e "\n🔑 Adding SSH key to Hetzner Cloud..."
    hcloud ssh-key create --name "$SSH_KEY_NAME" --public-key "$SSH_PUBLIC_KEY"
fi

# Create cloud-init config
CLOUD_INIT_PATH="/tmp/cloud-init-$(date +%s).yaml"
cat > "$CLOUD_INIT_PATH" << EOF
#cloud-config
package_update: true
package_upgrade: true

packages:
  - docker.io
  - caddy

write_files:
  - path: /etc/caddy/Caddyfile
    content: |
      $DOMAIN {
        reverse_proxy localhost:3333
      }

runcmd:
  - systemctl enable --now docker
  - systemctl enable --now caddy
  - docker pull ghcr.io/$(git config --get remote.origin.url | sed -n 's/.*:\([^/]*\/.*\)\.git/\1/p'):latest
  - |
    docker run -d \
      --name mcp-server \
      --restart unless-stopped \
      -p 3333:3333 \
      -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
      ghcr.io/$(git config --get remote.origin.url | sed -n 's/.*:\([^/]*\/.*\)\.git/\1/p'):latest

final_message: "MCP Server is ready! Visit https://$DOMAIN"
EOF

echo -e "\n🚀 Creating Hetzner Cloud server ($SERVER_TYPE in $REGION)..."

# Create the server
SERVER_INFO=$(hcloud server create \
  --name "$SERVER_NAME" \
  --type "$SERVER_TYPE" \
  --image "$DEFAULT_IMAGE" \
  --ssh-key "$SSH_KEY_NAME" \
  --location "$REGION" \
  --user-data-from-file "$CLOUD_INIT_PATH" \
  --output json \
  --output-format "{{.Server.PublicNet.IPv4.IP}},{{.Server.PublicNet.IPv6.IP}},{{.Server.ID}}")

# Extract server info
SERVER_IP=$(echo "$SERVER_INFO" | cut -d',' -f1)
SERVER_IPV6=$(echo "$SERVER_INFO" | cut -d',' -f2)
SERVER_ID=$(echo "$SERVER_INFO" | cut -d',' -f3)

# Clean up
rm -f "$CLOUD_INIT_PATH"

echo -e "\n${GREEN}✅ Server created successfully!${NC}"
echo -e "\n📋 Server Details:"
echo -e "  Name:        $SERVER_NAME"
echo -e "  ID:          $SERVER_ID"
echo -e "  IPv4:        $SERVER_IP"
echo -e "  IPv6:        $SERVER_IPV6"
echo -e "  Type:        $SERVER_TYPE"
echo -e "  Region:      $REGION"
echo -e "  SSH Command: ssh root@$SERVER_IP"

echo -e "\n🌐 Setting up DNS for $DOMAIN..."
# Note: This is a placeholder. In a real scenario, you would use a DNS API to update records.
echo -e "${YELLOW}⚠️  Please update your DNS settings to point $DOMAIN to $SERVER_IP${NC}"
echo -e "   - Create an A record: $DOMAIN -> $SERVER_IP"
echo -e "   - Create an AAAA record: $DOMAIN -> $SERVER_IPV6 (optional)"

echo -e "\n🚀 Deployment in progress! This may take a few minutes..."
echo -e "   - The server will automatically install Docker, Caddy, and start the MCP Server"
echo -e "   - Once complete, visit: https://$DOMAIN"
echo -e "\n🔍 To check the deployment status, run:"
echo -e "   ssh root@$SERVER_IP 'docker logs mcp-server --follow'"

echo -e "\n✅ ${GREEN}Deployment initiated!${NC} Your MCP Server will be available at https://$DOMAIN"
echo -e "   (Note: It may take a few minutes for DNS to propagate and services to start)"
