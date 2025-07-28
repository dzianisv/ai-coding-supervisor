#!/usr/bin/env bash
set -euo pipefail

# Colors for better UX
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print section headers
section() {
  echo -e "\n${YELLOW}==>${NC} ${GREEN}$1${NC}"
}

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Function to detect OS and architecture
detect_os_arch() {
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m)
  
  # Normalize architecture
  case "${ARCH}" in
    x86_64) ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) echo -e "${RED}❌ Unsupported architecture: ${ARCH}${NC}" >&2; exit 1 ;;
  esac
  
  echo "${OS}_${ARCH}"
}

# Function to install cloudflared
install_cloudflared() {
  if ! command_exists cloudflared; then
    section "Installing cloudflared..."
    
    OS_ARCH=$(detect_os_arch)
    DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-${OS_ARCH}"
    
    if [[ "${OS_ARCH}" == "darwin_"* ]]; then
      # For macOS, download the .tgz file
      DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-${ARCH}.tgz"
      curl -L "${DOWNLOAD_URL}" -o cloudflared.tgz
      tar -xzf cloudflared.tgz
    else
      # For Linux, download the binary directly
      curl -L "${DOWNLOAD_URL}" -o cloudflared
      chmod +x cloudflared
    fi
    
    # Move to a location in PATH
    if [[ "${EUID}" -eq 0 ]]; then
      mv cloudflared /usr/local/bin/
    else
      mkdir -p ~/bin
      mv cloudflared ~/bin/
      export PATH="${HOME}/bin:${PATH}"
      echo 'export PATH="${HOME}/bin:${PATH}"' >> ~/.bashrc
      echo 'export PATH="${HOME}/bin:${PATH}"' >> ~/.zshrc 2>/dev/null || true
    fi
    
    # Verify installation
    if ! command_exists cloudflared; then
      echo -e "${RED}❌ Failed to install cloudflared${NC}" >&2
      exit 1
    fi
    
    echo -e "${GREEN}✓ cloudflared installed successfully${NC}"
  else
    echo -e "${GREEN}✓ cloudflared is already installed${NC}"
  fi
}

# Function to get Cloudflare account and zone IDs
get_cloudflare_ids() {
  local token="$1"
  local zone_name="$2"
  
  section "Fetching Cloudflare account and zone information..."
  
  # Get zone ID
  ZONE_RESPONSE=$(curl -s \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    "https://api.cloudflare.com/client/v4/zones?name=${zone_name}")
  
  if ! echo "${ZONE_RESPONSE}" | jq -e '.success' >/dev/null; then
    echo -e "${RED}❌ Failed to fetch zone information:${NC}" >&2
    echo "${ZONE_RESPONSE}" | jq . >&2
    exit 1
  fi
  
  ZONE_ID=$(echo "${ZONE_RESPONSE}" | jq -r '.result[0].id')
  ACCOUNT_ID=$(echo "${ZONE_RESPONSE}" | jq -r '.result[0].account.id')
  
  if [[ -z "${ZONE_ID}" || -z "${ACCOUNT_ID}" ]]; then
    echo -e "${RED}❌ Could not determine ZONE_ID or ACCOUNT_ID${NC}" >&2
    exit 1
  fi
  
  echo -e "${GREEN}✓ Found zone ID: ${ZONE_ID}${NC}"
  echo -e "${GREEN}✓ Using account ID: ${ACCOUNT_ID}${NC}"
}

# Function to create a Cloudflare tunnel
create_tunnel() {
  local token="$1"
  local account_id="$2"
  local tunnel_name="$3"
  
  section "Creating Cloudflare tunnel '${tunnel_name}'..."
  
  local tunnel_secret=$(openssl rand -hex 32)
  
  local tunnel_json=$(curl -s -X POST \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${tunnel_name}\",\"tunnel_secret\":\"${tunnel_secret}\"}" \
    "https://api.cloudflare.com/client/v4/accounts/${account_id}/cfd_tunnel")
  
  if ! echo "${tunnel_json}" | jq -e '.success' >/dev/null; then
    echo -e "${RED}❌ Failed to create tunnel:${NC}" >&2
    echo "${tunnel_json}" | jq . >&2
    exit 1
  fi
  
  TUNNEL_ID=$(echo "${tunnel_json}" | jq -r '.result.id')
  TUNNEL_NAME=$(echo "${tunnel_json}" | jq -r '.result.name')
  
  if [[ -z "${TUNNEL_ID}" ]]; then
    echo -e "${RED}❌ Failed to get tunnel ID${NC}" >&2
    exit 1
  fi
  
  echo -e "${GREEN}✓ Created tunnel: ${TUNNEL_NAME} (${TUNNEL_ID})${NC}"
  
  # Save credentials
  mkdir -p ~/.cloudflared
  echo "${tunnel_json}" | jq --arg account "${account_id}" --arg id "${TUNNEL_ID}" '
    .result | {
      "AccountTag": $account,
      "TunnelID": $id,
      "TunnelName": .name,
      "TunnelSecret": .tunnel_secret
    }' > "${HOME}/.cloudflared/${TUNNEL_ID}.json"
  
  chmod 600 "${HOME}/.cloudflared/${TUNNEL_ID}.json"
  echo -e "${GREEN}✓ Saved tunnel credentials to ${HOME}/.cloudflared/${TUNNEL_ID}.json${NC}"
}

# Function to create DNS record
create_dns_record() {
  local token="$1"
  local zone_id="$2"
  local subdomain="$3"
  local tunnel_id="$4"
  
  section "Creating DNS record ${subdomain}..."
  
  local dns_response=$(curl -s -X POST \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -d "{\"type\":\"CNAME\",\"name\":\"${subdomain}\",\"content\":\"${tunnel_id}.cfargotunnel.com\",\"ttl\":120,\"proxied\":true}" \
    "https://api.cloudflare.com/client/v4/zones/${zone_id}/dns_records")
  
  if ! echo "${dns_response}" | jq -e '.success' >/dev/null; then
    echo -e "${YELLOW}⚠️  Failed to create DNS record (it might already exist):${NC}" >&2
    echo "${dns_response}" | jq . >&2
  else
    echo -e "${GREEN}✓ Created DNS record: ${subdomain} → ${tunnel_id}.cfargotunnel.com${NC}"
  fi
}

# Function to create config file
create_config() {
  local subdomain="$1"
  local zone_name="$2"
  local tunnel_id="$3"
  
  section "Creating Cloudflare tunnel configuration..."
  
  local config_path="${HOME}/.cloudflared/config.yml"
  
  cat > "${config_path}" <<EOF
tunnel: ${tunnel_id}
credentials-file: ${HOME}/.cloudflared/${tunnel_id}.json
logfile: ${HOME}/.cloudflared/cloudflared.log
loglevel: info

# Route traffic to MCP Server
# Uncomment and adjust the following if you want to use a bearer token
# originRequest:
#   noTLSVerify: true
#   httpHostHeader: ${subdomain}.${zone_name}
#   originServerName: ${subdomain}.${zone_name}
#   noHappyEyeballs: true
#   keepAliveConnections: 1
#   keepAliveTimeout: 30s
#   connectTimeout: 30s
#   tcpKeepAlive: 30s
#   noTLSVerify: true

# Ingress rules
# The first matching rule will be used
# The last rule should always be a catch-all 404
# See: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/configuration/ingress/
ingress:
  # MCP Server
  - hostname: ${subdomain}.${zone_name}
    service: http://localhost:3333
    # Uncomment to enable basic auth
    # originRequest:
    #   auth:
    #     username: your_username
    #     password: your_password
  # Catch-all rule
  - service: http_status:404
    path: /.*
EOF
  
  chmod 600 "${config_path}"
  echo -e "${GREEN}✓ Created tunnel configuration at ${config_path}${NC}"
}

# Function to create systemd service
create_systemd_service() {
  local user=$(whoami)
  local config_path="${HOME}/.cloudflared/config.yml"
  
  section "Creating systemd service..."
  
  local service_file="/etc/systemd/system/cloudflared-mcp.service"
  
  if [[ "${EUID}" -ne 0 ]]; then
    echo -e "${YELLOW}⚠️  Need root privileges to create systemd service${NC}"
    return 1
  fi
  
  cat > "${service_file}" <<EOF
[Unit]
Description=Cloudflare Tunnel for MCP Server
After=network.target

[Service]
Type=simple
User=${user}
WorkingDirectory=${HOME}
Environment="TUNNEL_CONFIG_FILE=${config_path}"
ExecStart=/usr/local/bin/cloudflared tunnel --config "${config_path}" run
Restart=always
RestartSec=5
StartLimitInterval=0

[Install]
WantedBy=multi-user.target
EOF
  
  systemctl daemon-reload
  systemctl enable --now cloudflared-mcp.service
  
  echo -e "${GREEN}✓ Created and started systemd service${NC}"
  echo -e "  ${YELLOW}To view logs:${NC} journalctl -u cloudflared-mcp.service -f"
}

# Main function
main() {
  echo -e "${YELLOW}🚀 MCP Server Cloudflare Tunnel Setup${NC}"
  
  # Check for dependencies
  if ! command_exists jq; then
    echo -e "${RED}❌ jq is required but not installed. Please install it first.${NC}" >&2
    echo -e "  On macOS: ${YELLOW}brew install jq${NC}" >&2
    echo -e "  On Ubuntu/Debian: ${YELLOW}sudo apt-get install jq${NC}" >&2
    exit 1
  fi
  
  if ! command_exists openssl; then
    echo -e "${RED}❌ openssl is required but not installed.${NC}" >&2
    exit 1
  fi
  
  # Get user input
  echo -e "\n${YELLOW}Please provide the following information:${NC}"
  read -rp "Cloudflare API Token (with DNS:Edit & Tunnel:Edit permissions): " CF_API_TOKEN
  read -rp "Zone (example.com, not including subdomain): " ZONE_NAME
  read -rp "Subdomain to use (e.g., 'mcp' for mcp.example.com): " SUBDOMAIN
  
  # Validate inputs
  if [[ -z "${CF_API_TOKEN}" || -z "${ZONE_NAME}" || -z "${SUBDOMAIN}" ]]; then
    echo -e "${RED}❌ All fields are required${NC}" >&2
    exit 1
  fi
  
  # Install cloudflared if needed
  install_cloudflared
  
  # Get Cloudflare account and zone IDs
  get_cloudflare_ids "${CF_API_TOKEN}" "${ZONE_NAME}"
  
  # Create tunnel
  create_tunnel "${CF_API_TOKEN}" "${ACCOUNT_ID}" "mcp-${SUBDOMAIN}"
  
  # Create DNS record
  create_dns_record "${CF_API_TOKEN}" "${ZONE_ID}" "${SUBDOMAIN}" "${TUNNEL_ID}"
  
  # Create config file
  create_config "${SUBDOMAIN}" "${ZONE_NAME}" "${TUNNEL_ID}"
  
  # Create systemd service if running as root
  if [[ "${EUID}" -eq 0 ]]; then
    create_systemd_service
  fi
  
  # Run the tunnel
  section "Starting Cloudflare tunnel..."
  echo -e "${GREEN}✓ Tunnel is ready!${NC}"
  echo -e "  ${YELLOW}Access your MCP Server at:${NC} https://${SUBDOMAIN}.${ZONE_NAME}"
  echo -e "\n${YELLOW}To run the tunnel in the foreground:${NC}"
  echo "  cloudflared tunnel --config ~/.cloudflared/config.yml run"
  
  if [[ "${EUID}" -ne 0 ]]; then
    echo -e "\n${YELLOW}To run as a systemd service (requires root):${NC}"
    echo "  sudo ${0} --install-service"
  fi
  
  echo -e "\n${YELLOW}To check tunnel status:${NC}"
  echo "  cloudflared tunnel list"
  
  # Write a completion marker for Windsurf
  echo -e "\n# >> windsrf_check"
  echo -e "${GREEN}✅ Cloudflare tunnel setup completed successfully!${NC}"
}

# Run main function
main "$@"
