# 🐳 HyperSwipe Docker Deployment Guide

This guide shows you how to deploy HyperSwipe server using Docker - much simpler and more reliable than manual setup!

## ✨ Why Docker?

- **Simple**: One command deployment
- **Reliable**: Consistent environment everywhere
- **Easy Updates**: `docker-compose up -d` to update
- **Easy Rollback**: Quick container restarts
- **Isolated**: No conflicts with system packages
- **Portable**: Works on any server with Docker

## 🚀 Quick Deployment (5 minutes)

### Step 1: Launch EC2 Instance

1. **Instance**: Ubuntu 22.04 LTS, t3.small or larger
2. **Storage**: 20GB SSD minimum
3. **Security Group**: Ports 22 (SSH), 80 (HTTP), 443 (HTTPS)

### Step 2: One-Command Deploy

```bash
# Connect to your server
ssh -i your-key.pem ubuntu@your-server-ip

# Download and run the Docker deployment script
curl -fsSL https://raw.githubusercontent.com/your-username/hyperswipe/main/hyperswipe-server/deploy-docker.sh -o deploy-docker.sh
chmod +x deploy-docker.sh
./deploy-docker.sh
```

**That's it!** ✨ Your server will be running at `https://your-domain.com`

## 📋 What the Script Does

1. **Installs Docker & Docker Compose** automatically
2. **Sets up SSL certificates** with Let's Encrypt
3. **Configures Nginx** as reverse proxy
4. **Starts all services** in containers
5. **Creates management scripts** for easy maintenance

## 🛠️ Manual Docker Deployment

If you prefer step-by-step:

### Step 1: Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login again for group changes
```

### Step 2: Setup Project

```bash
# Create project directory
sudo mkdir -p /home/ubuntu/projects/hyperswipe-server
sudo chown ubuntu:ubuntu /home/ubuntu/projects/hyperswipe-server
cd /home/ubuntu/projects/hyperswipe-server

# Copy your HyperSwipe server files here
# (Dockerfile, docker-compose.yml, app/, requirements.txt, etc.)

# Or clone from git:
git clone https://github.com/your-username/hyperswipe.git .
```

### Step 3: Configure Environment

```bash
# Create .env file
cat > .env << EOF
DOMAIN=your-domain.com
EMAIL=your-email@domain.com
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://your-frontend-domain.com
EOF
```

### Step 4: Deploy

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Step 5: Setup SSL

```bash
# Get SSL certificate
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/html \
    --email your-email@domain.com \
    --agree-tos \
    --no-eff-email \
    -d your-domain.com

# Restart nginx
docker-compose restart nginx
```

## 🔧 Container Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx       │    │  HyperSwipe     │    │     Redis       │
│   (SSL + Proxy) │────│    Server       │────│   (Caching)     │
│   Port 80/443   │    │   Port 8081     │    │   Port 6379     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Certbot       │
                    │ (SSL Renewal)   │
                    └─────────────────┘
```

## 📊 Service Management

### Start/Stop Services

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart hyperswipe-server
docker-compose restart nginx

# View status
docker-compose ps
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f hyperswipe-server
docker-compose logs -f nginx

# Last 100 lines
docker-compose logs --tail=100 hyperswipe-server
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Or use the provided script
./update-hyperswipe.sh
```

## 🔍 Health Monitoring

### Quick Health Check

```bash
# Check API health
curl -f https://your-domain.com/health

# Check WebSocket (install websocat first: cargo install websocat)
echo '{"type":"ping"}' | websocat wss://your-domain.com/ws
```

### Container Health

```bash
# Check container status
docker-compose ps

# Check resource usage
docker stats

# Check container logs for errors
docker-compose logs hyperswipe-server | grep ERROR
```

## 🔒 Security Features

The Docker setup includes:

- ✅ **SSL/TLS encryption** with automatic renewal
- ✅ **Rate limiting** to prevent abuse
- ✅ **Security headers** (HSTS, CSP, etc.)
- ✅ **Non-root containers** for better security
- ✅ **Firewall configuration** (UFW)
- ✅ **Container isolation**

## 📈 Performance Tuning

### Scale Up

```yaml
# In docker-compose.yml, add replicas:
services:
  hyperswipe-server:
    deploy:
      replicas: 3
    # ... rest of config
```

### Resource Limits

```yaml
# Add resource limits
services:
  hyperswipe-server:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
        reservations:
          memory: 512M
          cpus: '0.25'
```

## 🔄 Backup Strategy

### Automated Backup Script

```bash
#!/bin/bash
# backup-hyperswipe.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/ubuntu/backups"

mkdir -p $BACKUP_DIR

# Backup containers and data
cd ~/hyperswipe
tar -czf $BACKUP_DIR/hyperswipe_$DATE.tar.gz .

# Keep only last 7 days
find $BACKUP_DIR -name "hyperswipe_*.tar.gz" -mtime +7 -delete

echo "Backup completed: hyperswipe_$DATE.tar.gz"
```

Add to crontab:
```bash
crontab -e
# Add this line:
0 2 * * * /home/ubuntu/backup-hyperswipe.sh
```

## 🚨 Troubleshooting

### Common Issues

1. **Container won't start**:
   ```bash
   docker-compose logs hyperswipe-server
   docker-compose ps
   ```

2. **SSL certificate issues**:
   ```bash
   docker-compose logs certbot
   docker-compose run --rm certbot certificates
   ```

3. **WebSocket connection fails**:
   ```bash
   docker-compose logs nginx
   curl -I https://your-domain.com/ws
   ```

4. **High memory usage**:
   ```bash
   docker stats
   docker-compose restart hyperswipe-server
   ```

### Reset Everything

If you need to start fresh:

```bash
# Stop and remove everything
docker-compose down --volumes --rmi all

# Remove all containers and images
docker system prune -a

# Start fresh
docker-compose up -d
```

## 📱 Frontend Integration

Update your frontend to use the new WebSocket URL:

```javascript
// In your frontend code
const wsUrl = 'wss://your-domain.com/ws'

// Example WebSocket connection
const ws = new WebSocket(wsUrl)
ws.onopen = () => console.log('Connected to HyperSwipe server')
ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    // Handle real-time data
}
```

## 🔧 Configuration Files

### docker-compose.yml
```yaml
version: '3.8'
services:
  hyperswipe-server:
    build: .
    ports:
      - "8081:8081"
    environment:
      - ENVIRONMENT=production
    restart: unless-stopped
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - hyperswipe-server
    restart: unless-stopped
```

### Environment Variables (.env)
```bash
DOMAIN=your-domain.com
EMAIL=admin@your-domain.com
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-frontend.com
```

## 🎯 Production Checklist

Before going live:

- [ ] Domain DNS points to your server IP
- [ ] SSL certificate is working (`https://` shows green lock)
- [ ] Health endpoint responds: `curl https://your-domain.com/health`
- [ ] WebSocket connects successfully
- [ ] Frontend can communicate with backend
- [ ] Logs are clean (no errors)
- [ ] Firewall is configured
- [ ] Monitoring/alerts set up
- [ ] Backup strategy implemented

## 📞 Getting Help

If you encounter issues:

1. **Check logs**: `docker-compose logs -f`
2. **Check status**: `docker-compose ps`
3. **Restart services**: `docker-compose restart`
4. **Reset everything**: `docker-compose down && docker-compose up -d`

## 🎉 Success!

Your HyperSwipe server should now be running at:
- 🌐 **API Documentation**: `https://your-domain.com/docs`
- 💓 **Health Check**: `https://your-domain.com/health`
- 🔌 **WebSocket**: `wss://your-domain.com/ws`

Much easier than manual deployment! 🚀