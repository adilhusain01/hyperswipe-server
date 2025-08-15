#!/bin/bash

# HyperSwipe Docker Deployment Script
# Simple one-click deployment to AWS EC2 with Docker

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
DOMAIN="app.hyperswipe.rizzmo.site"
EMAIL="admin@hyperswipe.rizzmo.site"
PROJECT_NAME="hyperswipe"

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
if [[ $EUID -eq 0 ]]; then
   error "Don't run this script as root. Run as ubuntu user."
fi

log "🚀 Starting HyperSwipe Docker deployment..."

# Update system
log "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
if ! command -v docker &> /dev/null; then
    log "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    log "✅ Docker installed. Please log out and back in for group changes to take effect."
else
    log "✅ Docker already installed"
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    log "🐙 Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log "✅ Docker Compose installed"
else
    log "✅ Docker Compose already installed"
fi

# Create project directory
log "📁 Setting up project directory..."
mkdir -p ~/$PROJECT_NAME
cd ~/$PROJECT_NAME

# Download or copy project files (if not already present)
if [ ! -f "docker-compose.yml" ]; then
    log "📥 Setting up project files..."
    
    # Create necessary directories
    mkdir -p nginx/sites-available nginx/ssl nginx/logs nginx/webroot logs data
    
    # You would typically git clone here or copy files
    # For now, we'll create a minimal structure
    warn "Please ensure your project files are in the current directory: $(pwd)"
    warn "Required files: Dockerfile, docker-compose.yml, requirements.txt, app/, etc."
fi

# Create environment file if it doesn't exist
if [ ! -f ".env" ]; then
    log "⚙️ Creating environment configuration..."
    cat > .env << EOF
# HyperSwipe Docker Environment
COMPOSE_PROJECT_NAME=$PROJECT_NAME
DOMAIN=$DOMAIN
EMAIL=$EMAIL

# Application settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8081
RELOAD=false

# CORS - Update with your frontend domains
CORS_ORIGINS=https://$DOMAIN,https://www.$DOMAIN

# Hyperliquid
HYPERLIQUID_TESTNET=true
HYPERLIQUID_BASE_URL=https://api.hyperliquid-testnet.xyz

# Security
RATE_LIMIT_PER_MINUTE=100
EOF
    log "✅ Environment file created"
fi

# Setup firewall
log "🔥 Configuring firewall..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
log "✅ Firewall configured"

# Build and start services
log "🏗️ Building and starting services..."
docker-compose down --remove-orphans
docker-compose build --no-cache
docker-compose up -d

# Wait for services to start
log "⏳ Waiting for services to start..."
sleep 30

# Check service health
log "🏥 Checking service health..."
if docker-compose exec hyperswipe-server curl -f http://localhost:8081/health > /dev/null 2>&1; then
    log "✅ HyperSwipe server is healthy"
else
    warn "⚠️ HyperSwipe server health check failed"
fi

# Setup SSL certificate
log "🔒 Setting up SSL certificate..."

# First, get certificate in staging mode
info "Getting staging certificate first (for testing)..."
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/html \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    --staging \
    -d $DOMAIN

if [ $? -eq 0 ]; then
    log "✅ Staging certificate obtained successfully"
    
    # Now get the real certificate
    info "Getting production certificate..."
    docker-compose run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/html \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        -d $DOMAIN
    
    if [ $? -eq 0 ]; then
        log "✅ Production SSL certificate obtained"
        
        # Restart nginx to use the new certificate
        docker-compose restart nginx
    else
        warn "⚠️ Failed to get production certificate, using staging"
    fi
else
    warn "⚠️ Failed to get SSL certificate"
fi

# Setup certificate renewal
log "🔄 Setting up certificate renewal..."
cat > ~/renew-certs.sh << 'EOF'
#!/bin/bash
cd ~/hyperswipe
docker-compose run --rm certbot renew --quiet
docker-compose exec nginx nginx -s reload
EOF

chmod +x ~/renew-certs.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "0 3 * * * /home/ubuntu/renew-certs.sh >> /home/ubuntu/certbot.log 2>&1") | crontab -

log "✅ Certificate auto-renewal configured"

# Create management scripts
log "🛠️ Creating management scripts..."

# Create start script
cat > ~/start-hyperswipe.sh << 'EOF'
#!/bin/bash
cd ~/hyperswipe
docker-compose up -d
echo "HyperSwipe started. Check status with: docker-compose ps"
EOF

# Create stop script
cat > ~/stop-hyperswipe.sh << 'EOF'
#!/bin/bash
cd ~/hyperswipe
docker-compose down
echo "HyperSwipe stopped."
EOF

# Create update script
cat > ~/update-hyperswipe.sh << 'EOF'
#!/bin/bash
cd ~/hyperswipe
echo "Pulling latest changes..."
git pull  # If using git
echo "Rebuilding containers..."
docker-compose build --no-cache
echo "Restarting services..."
docker-compose down
docker-compose up -d
echo "Update complete!"
EOF

# Create logs script
cat > ~/logs-hyperswipe.sh << 'EOF'
#!/bin/bash
cd ~/hyperswipe
echo "HyperSwipe Logs (Ctrl+C to exit):"
docker-compose logs -f
EOF

chmod +x ~/start-hyperswipe.sh ~/stop-hyperswipe.sh ~/update-hyperswipe.sh ~/logs-hyperswipe.sh

log "✅ Management scripts created"

# Final status check
log "📊 Final system check..."
docker-compose ps

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 HYPERSWIPE DOCKER DEPLOYMENT COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Your HyperSwipe server is running at:"
echo "   📱 API Docs: https://$DOMAIN/docs"
echo "   💓 Health: https://$DOMAIN/health"
echo "   🔌 WebSocket: wss://$DOMAIN/ws"
echo
echo "🛠️  MANAGEMENT COMMANDS:"
echo "   ./start-hyperswipe.sh    - Start all services"
echo "   ./stop-hyperswipe.sh     - Stop all services"
echo "   ./update-hyperswipe.sh   - Update and restart"
echo "   ./logs-hyperswipe.sh     - View logs"
echo
echo "🐳 DOCKER COMMANDS:"
echo "   cd ~/hyperswipe && docker-compose ps              - Show status"
echo "   cd ~/hyperswipe && docker-compose logs -f         - View logs"
echo "   cd ~/hyperswipe && docker-compose restart nginx   - Restart nginx"
echo "   cd ~/hyperswipe && docker-compose down && docker-compose up -d  - Full restart"
echo
echo "📝 CONFIGURATION:"
echo "   Environment: ~/hyperswipe/.env"
echo "   Nginx Config: ~/hyperswipe/nginx/sites-available/hyperswipe.conf"
echo "   Logs: ~/hyperswipe/logs/ and ~/hyperswipe/nginx/logs/"
echo
echo "🔧 TROUBLESHOOTING:"
echo "   1. Check logs: ./logs-hyperswipe.sh"
echo "   2. Restart services: ./stop-hyperswipe.sh && ./start-hyperswipe.sh"
echo "   3. Check container status: cd ~/hyperswipe && docker-compose ps"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Final instructions
echo
info "🚀 Next steps:"
echo "   1. Update your frontend to use wss://$DOMAIN/ws"
echo "   2. Test the API at https://$DOMAIN/docs"
echo "   3. Monitor logs with ./logs-hyperswipe.sh"
echo "   4. Set up monitoring and backups as needed"

log "✅ Deployment completed successfully!"