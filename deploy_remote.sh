#!/bin/bash
# MCP Server Remote Deployment Script

set -e

echo "🚀 MCP Server Remote Deployment Script"
echo "======================================="

# Configuration
SERVER_USER="mcp"
APP_DIR="/opt/ai-coding-supervisor"
SERVICE_NAME="mcp-server"

# Function to print colored output
print_step() {
    echo -e "\n🔧 $1"
}

print_success() {
    echo -e "✅ $1"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    print_step "Setting up system user and directories..."
    
    # Create system user
    useradd -r -s /bin/false -d $APP_DIR $SERVER_USER || true
    
    # Create application directory
    mkdir -p $APP_DIR
    mkdir -p $APP_DIR/logs
    
    # Install system dependencies
    print_step "Installing system dependencies..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv git curl
    
    print_success "System setup complete"
else
    print_info "Not running as root, skipping system setup"
fi

print_step "Setting up Python environment..."

# Create virtual environment
python3 -m venv $APP_DIR/venv
source $APP_DIR/venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

print_success "Python environment ready"

print_step "Copying application files..."

# Copy application files
cp -r . $APP_DIR/
chown -R $SERVER_USER:$SERVER_USER $APP_DIR

print_success "Application files copied"

if [[ $EUID -eq 0 ]]; then
    print_step "Setting up systemd service..."
    
    # Install systemd service
    cp mcp-server.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable $SERVICE_NAME
    systemctl start $SERVICE_NAME
    
    print_success "Systemd service installed and started"
    
    # Show service status
    systemctl status $SERVICE_NAME --no-pager
fi

print_step "Setting up firewall (if ufw is available)..."
if command -v ufw &> /dev/null; then
    ufw allow 8080/tcp
    print_success "Firewall configured"
else
    print_info "UFW not found, please configure firewall manually to allow port 8080"
fi

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📊 Service Status:"
if [[ $EUID -eq 0 ]]; then
    systemctl is-active $SERVICE_NAME
else
    print_info "Run as root to check service status"
fi
echo ""
echo "🌐 Server should be accessible at:"
echo "   - http://YOUR_SERVER_IP:8080"
echo ""
echo "📝 Useful commands:"
echo "   - Check status: sudo systemctl status $SERVICE_NAME"
echo "   - View logs: sudo journalctl -u $SERVICE_NAME -f"
echo "   - Restart: sudo systemctl restart $SERVICE_NAME"
echo "   - Stop: sudo systemctl stop $SERVICE_NAME"
echo ""
echo "🔧 For HTTPS setup, configure nginx reverse proxy using docker-compose:"
echo "   docker-compose --profile with-nginx up -d"
