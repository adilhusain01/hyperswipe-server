#!/bin/bash

# HyperSwipe Server AWS EC2 Deployment Script
# This script sets up the HyperSwipe server on a fresh Ubuntu EC2 instance

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="hyperswipe-server"
APP_USER="hyperswipe"
APP_DIR="/opt/hyperswipe"
REPO_URL="https://github.com/your-username/hyperswipe.git"  # Update this
DOMAIN="your-domain.com"  # Update this

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root (use sudo)"
fi

log "Starting HyperSwipe Server deployment on AWS EC2..."

# Update system
log "Updating system packages..."
apt update && apt upgrade -y

# Install required packages
log "Installing required packages..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    ufw \
    certbot \
    python3-certbot-nginx \
    supervisor \
    htop \
    curl \
    unzip

# Create application user
log "Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d $APP_DIR $APP_USER
    log "Created user: $APP_USER"
else
    info "User $APP_USER already exists"
fi

# Create application directory
log "Setting up application directory..."
mkdir -p $APP_DIR
chown $APP_USER:$APP_USER $APP_DIR

# Clone repository (if provided)
if [ "$REPO_URL" != "https://github.com/your-username/hyperswipe.git" ]; then
    log "Cloning repository..."
    cd /tmp
    git clone $REPO_URL hyperswipe-repo
    cp -r hyperswipe-repo/hyperswipe-server/* $APP_DIR/
    chown -R $APP_USER:$APP_USER $APP_DIR
    rm -rf hyperswipe-repo
else
    warn "Please update REPO_URL in this script or manually copy your code to $APP_DIR"
fi

# Switch to app user for Python setup
log "Setting up Python environment..."
sudo -u $APP_USER bash << EOF
cd $APP_DIR

# Create virtual environment
python3 -m venv venv

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create logs directory
mkdir -p logs
EOF

# Create environment file
log "Creating environment configuration..."
cat > $APP_DIR/.env << EOF
# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8081
RELOAD=false

# CORS - Update with your frontend domain
CORS_ORIGINS=https://$DOMAIN,https://www.$DOMAIN

# Security
RATE_LIMIT_PER_MINUTE=100

# Hyperliquid
HYPERLIQUID_TESTNET=true
HYPERLIQUID_BASE_URL=https://api.hyperliquid-testnet.xyz
EOF

chown $APP_USER:$APP_USER $APP_DIR/.env

# Create systemd service
log "Creating systemd service..."
cat > /etc/systemd/system/$APP_NAME.service << EOF
[Unit]
Description=HyperSwipe FastAPI Server
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/python run.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$APP_NAME

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

# Create nginx configuration
log "Configuring Nginx..."
cat > /etc/nginx/sites-available/$APP_NAME << EOF
# HyperSwipe Server Nginx Configuration

# Rate limiting
limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone \$binary_remote_addr zone=ws:10m rate=5r/s;

# Upstream for the FastAPI app
upstream hyperswipe_app {
    server 127.0.0.1:8081;
}

server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # WebSocket configuration
    location /ws {
        limit_req zone=ws burst=10 nodelay;
        
        proxy_pass http://hyperswipe_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket specific timeouts
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # API endpoints
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://hyperswipe_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # CORS headers for API
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization" always;
        
        if (\$request_method = 'OPTIONS') {
            return 204;
        }
    }

    # Health check and docs
    location ~ ^/(health|status|docs|redoc) {
        proxy_pass http://hyperswipe_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Root redirect
    location = / {
        proxy_pass http://hyperswipe_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Block access to sensitive files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF

# Enable nginx site
ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
nginx -t || error "Nginx configuration test failed"

# Configure firewall
log "Configuring firewall..."
ufw --force enable
ufw allow ssh
ufw allow 80
ufw allow 443
ufw allow 8081  # For direct access during testing

# Start and enable services
log "Starting services..."
systemctl daemon-reload
systemctl enable $APP_NAME
systemctl start $APP_NAME
systemctl enable nginx
systemctl restart nginx

# Check service status
log "Checking service status..."
if systemctl is-active --quiet $APP_NAME; then
    log "✅ HyperSwipe service is running"
else
    error "❌ HyperSwipe service failed to start"
fi

if systemctl is-active --quiet nginx; then
    log "✅ Nginx is running"
else
    error "❌ Nginx failed to start"
fi

# Setup SSL certificate (optional)
log "Setting up SSL certificate..."
if [ "$DOMAIN" != "your-domain.com" ]; then
    info "Setting up Let's Encrypt SSL certificate for $DOMAIN"
    certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
else
    warn "Please update DOMAIN variable to enable SSL certificate"
fi

# Create monitoring script
log "Creating monitoring script..."
cat > /usr/local/bin/hyperswipe-monitor.sh << 'EOF'
#!/bin/bash

# HyperSwipe monitoring script
SERVICE_NAME="hyperswipe-server"
LOG_FILE="/var/log/hyperswipe-monitor.log"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

# Check if service is running
if ! systemctl is-active --quiet $SERVICE_NAME; then
    log_message "Service $SERVICE_NAME is not running, attempting to restart..."
    systemctl start $SERVICE_NAME
    
    # Wait and check again
    sleep 10
    if systemctl is-active --quiet $SERVICE_NAME; then
        log_message "Service $SERVICE_NAME restarted successfully"
    else
        log_message "Failed to restart service $SERVICE_NAME"
    fi
fi

# Check if API is responding
if ! curl -f http://localhost:8081/health > /dev/null 2>&1; then
    log_message "API health check failed"
fi
EOF

chmod +x /usr/local/bin/hyperswipe-monitor.sh

# Add monitoring cron job
echo "*/5 * * * * root /usr/local/bin/hyperswipe-monitor.sh" > /etc/cron.d/hyperswipe-monitor

# Create backup script
log "Creating backup script..."
cat > /usr/local/bin/hyperswipe-backup.sh << EOF
#!/bin/bash

# HyperSwipe backup script
BACKUP_DIR="/opt/backups/hyperswipe"
DATE=\$(date +%Y%m%d_%H%M%S)

mkdir -p \$BACKUP_DIR

# Backup application code and configuration
tar -czf \$BACKUP_DIR/hyperswipe_\$DATE.tar.gz -C /opt hyperswipe

# Keep only last 7 days of backups
find \$BACKUP_DIR -name "hyperswipe_*.tar.gz" -mtime +7 -delete

echo "Backup completed: hyperswipe_\$DATE.tar.gz"
EOF

chmod +x /usr/local/bin/hyperswipe-backup.sh

# Add daily backup cron job
echo "0 2 * * * root /usr/local/bin/hyperswipe-backup.sh" > /etc/cron.d/hyperswipe-backup

# Display final information
log "🎉 Deployment completed successfully!"
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 DEPLOYMENT SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏠 Application Directory: $APP_DIR"
echo "👤 Application User: $APP_USER"
echo "🌐 Domain: $DOMAIN"
echo "🔗 API URL: https://$DOMAIN/docs"
echo "🔗 Health Check: https://$DOMAIN/health"
echo "🔗 WebSocket: wss://$DOMAIN/ws"
echo "📁 Logs: journalctl -u $APP_NAME -f"
echo "📝 Config: $APP_DIR/.env"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "🔧 USEFUL COMMANDS:"
echo "   sudo systemctl status $APP_NAME    # Check service status"
echo "   sudo systemctl restart $APP_NAME   # Restart service"
echo "   sudo journalctl -u $APP_NAME -f    # View logs"
echo "   sudo nginx -t                      # Test nginx config"
echo "   sudo systemctl reload nginx        # Reload nginx"
echo
echo "⚠️  IMPORTANT: Update the following before production:"
echo "   1. Change DOMAIN variable in this script"
echo "   2. Update REPO_URL if using git deployment"
echo "   3. Configure your frontend to use wss://$DOMAIN/ws"
echo "   4. Review and adjust the .env file at $APP_DIR/.env"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"