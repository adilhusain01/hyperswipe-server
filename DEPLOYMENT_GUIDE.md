# HyperSwipe Server AWS EC2 Deployment Guide

This guide provides step-by-step instructions for deploying the HyperSwipe FastAPI server to an AWS EC2 instance with production-ready configuration.

## 📋 Prerequisites

### AWS Requirements
- AWS account with EC2 access
- A registered domain name (for SSL certificates)
- Basic knowledge of Linux/Ubuntu server administration

### Local Requirements
- SSH client
- Git (if deploying from repository)
- Text editor for configuration

## 🚀 Quick Deployment (Automated)

### Step 1: Launch EC2 Instance

1. **Launch Ubuntu Server**:
   - AMI: Ubuntu Server 22.04 LTS (HVM)
   - Instance Type: t3.small or larger (minimum 2GB RAM)
   - Storage: 20GB gp3 SSD minimum
   - Security Group: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)

2. **Configure Security Group**:
   ```
   Type        Protocol    Port Range    Source
   SSH         TCP         22           Your IP/0.0.0.0/0
   HTTP        TCP         80           0.0.0.0/0
   HTTPS       TCP         443          0.0.0.0/0
   Custom TCP  TCP         8081         0.0.0.0/0 (optional, for testing)
   ```

### Step 2: Connect and Deploy

1. **Connect to your instance**:
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-public-ip
   ```

2. **Download and run deployment script**:
   ```bash
   # Switch to root
   sudo su -
   
   # Download the deployment script
   wget https://raw.githubusercontent.com/your-username/hyperswipe/main/hyperswipe-server/deploy.sh
   
   # Make it executable
   chmod +x deploy.sh
   
   # Edit the configuration variables
   nano deploy.sh
   # Update: DOMAIN, REPO_URL
   
   # Run the deployment
   ./deploy.sh
   ```

### Step 3: Configure DNS

Point your domain to your EC2 instance:
- Create an A record pointing `your-domain.com` to your EC2 public IP
- Create an A record pointing `www.your-domain.com` to your EC2 public IP

## 🔧 Manual Deployment (Step by Step)

### Step 1: System Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv git nginx ufw certbot python3-certbot-nginx supervisor
```

### Step 2: Create Application User

```bash
# Create dedicated user
sudo useradd -r -s /bin/bash -d /opt/hyperswipe hyperswipe
sudo mkdir -p /opt/hyperswipe
sudo chown hyperswipe:hyperswipe /opt/hyperswipe
```

### Step 3: Deploy Application Code

```bash
# Option A: From Git Repository
sudo -u hyperswipe git clone https://github.com/your-username/hyperswipe.git /tmp/hyperswipe-repo
sudo -u hyperswipe cp -r /tmp/hyperswipe-repo/hyperswipe-server/* /opt/hyperswipe/
sudo rm -rf /tmp/hyperswipe-repo

# Option B: Upload manually (using scp from local machine)
scp -r -i your-key.pem ./hyperswipe-server/* ubuntu@your-ec2-ip:/tmp/
sudo -u hyperswipe cp -r /tmp/* /opt/hyperswipe/
```

### Step 4: Setup Python Environment

```bash
# Switch to application user
sudo -u hyperswipe bash

# Setup Python environment
cd /opt/hyperswipe
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Exit back to root user
exit
```

### Step 5: Configure Environment

```bash
# Create production environment file
sudo -u hyperswipe tee /opt/hyperswipe/.env << EOF
# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8081
RELOAD=false

# CORS - Update with your domain
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Security
RATE_LIMIT_PER_MINUTE=100

# Hyperliquid
HYPERLIQUID_TESTNET=true
HYPERLIQUID_BASE_URL=https://api.hyperliquid-testnet.xyz
EOF
```

### Step 6: Setup Systemd Service

```bash
# Copy the systemd service file
sudo cp /opt/hyperswipe/hyperswipe-server.service /etc/systemd/system/

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable hyperswipe-server
sudo systemctl start hyperswipe-server

# Check status
sudo systemctl status hyperswipe-server
```

### Step 7: Configure Nginx

```bash
# Copy nginx configuration
sudo cp /opt/hyperswipe/nginx.conf /etc/nginx/sites-available/hyperswipe-server

# Update domain in nginx config
sudo sed -i 's/your-domain.com/actual-domain.com/g' /etc/nginx/sites-available/hyperswipe-server

# Enable site
sudo ln -sf /etc/nginx/sites-available/hyperswipe-server /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

### Step 8: Setup SSL Certificate

```bash
# Install SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### Step 9: Configure Firewall

```bash
# Enable UFW firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443

# Check status
sudo ufw status
```

## 🔍 Verification and Testing

### Test Local API Access

```bash
# Test health endpoint
curl -f http://localhost:8081/health

# Test WebSocket connection
curl -f http://localhost:8081/ws
```

### Test External Access

```bash
# From your local machine
curl -f https://your-domain.com/health
curl -f https://your-domain.com/docs
```

### Check WebSocket Connection

```javascript
// Test from browser console
const ws = new WebSocket('wss://your-domain.com/ws');
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Message:', e.data);
ws.onclose = () => console.log('Disconnected');
```

## 📊 Monitoring and Maintenance

### Service Management

```bash
# Check service status
sudo systemctl status hyperswipe-server

# View logs
sudo journalctl -u hyperswipe-server -f

# Restart service
sudo systemctl restart hyperswipe-server

# Check nginx status
sudo systemctl status nginx
sudo nginx -t
```

### Log Files

- **Application logs**: `sudo journalctl -u hyperswipe-server`
- **Nginx access logs**: `/var/log/nginx/hyperswipe_access.log`
- **Nginx error logs**: `/var/log/nginx/hyperswipe_error.log`
- **System logs**: `/var/log/syslog`

### Performance Monitoring

```bash
# Check system resources
htop

# Check disk usage
df -h

# Check memory usage
free -h

# Check network connections
netstat -tlnp | grep :8081
```

### Backup Strategy

The deployment script creates automatic backups:

```bash
# Manual backup
sudo /usr/local/bin/hyperswipe-backup.sh

# Check backups
ls -la /opt/backups/hyperswipe/

# Restore from backup
sudo systemctl stop hyperswipe-server
sudo tar -xzf /opt/backups/hyperswipe/backup_file.tar.gz -C /opt/
sudo systemctl start hyperswipe-server
```

## 🔧 Configuration Updates

### Environment Variables

Edit the environment file:
```bash
sudo -u hyperswipe nano /opt/hyperswipe/.env
sudo systemctl restart hyperswipe-server
```

### Application Updates

```bash
# Stop service
sudo systemctl stop hyperswipe-server

# Update code (if using git)
sudo -u hyperswipe bash -c "cd /opt/hyperswipe && git pull"

# Update dependencies if needed
sudo -u hyperswipe bash -c "cd /opt/hyperswipe && source venv/bin/activate && pip install -r requirements.txt"

# Start service
sudo systemctl start hyperswipe-server
```

### Nginx Configuration Updates

```bash
# Edit nginx config
sudo nano /etc/nginx/sites-available/hyperswipe-server

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

## 🚨 Troubleshooting

### Common Issues

1. **Service won't start**:
   ```bash
   sudo journalctl -u hyperswipe-server --no-pager
   sudo systemctl status hyperswipe-server
   ```

2. **WebSocket connection fails**:
   - Check firewall rules: `sudo ufw status`
   - Check nginx config: `sudo nginx -t`
   - Check service logs: `sudo journalctl -u hyperswipe-server -f`

3. **SSL certificate issues**:
   ```bash
   sudo certbot certificates
   sudo certbot renew --dry-run
   ```

4. **High memory usage**:
   ```bash
   # Restart service to clear memory
   sudo systemctl restart hyperswipe-server
   
   # Check for memory leaks
   sudo journalctl -u hyperswipe-server | grep -i memory
   ```

### Performance Tuning

For high-traffic deployments:

1. **Increase worker processes** (edit `/opt/hyperswipe/run.py`):
   ```python
   uvicorn.run(
       "app.main:app",
       host="0.0.0.0",
       port=8081,
       workers=4,  # Add this line
       log_level="info"
   )
   ```

2. **Configure nginx worker processes**:
   ```bash
   sudo nano /etc/nginx/nginx.conf
   # Set worker_processes to number of CPU cores
   ```

3. **Increase system limits**:
   ```bash
   # Add to /etc/security/limits.conf
   hyperswipe soft nofile 65536
   hyperswipe hard nofile 65536
   ```

## 🔒 Security Considerations

### Security Checklist

- ✅ Firewall configured (UFW)
- ✅ SSL/TLS certificates installed
- ✅ Regular security updates enabled
- ✅ Non-root user for application
- ✅ Rate limiting configured
- ✅ Security headers configured
- ✅ Sensitive files protected

### Additional Security Measures

1. **Enable automatic security updates**:
   ```bash
   sudo apt install unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```

2. **Configure fail2ban**:
   ```bash
   sudo apt install fail2ban
   sudo systemctl enable fail2ban
   ```

3. **Regular security audits**:
   ```bash
   # Check for vulnerable packages
   sudo apt list --upgradable
   
   # Check open ports
   sudo netstat -tlnp
   ```

## 📱 Frontend Configuration

Update your frontend to use the production server:

```javascript
// In hyperswipe-client/src/services/websocket.js
const serverUrl = import.meta.env.MODE === 'production' 
  ? 'wss://your-domain.com/ws' 
  : 'ws://localhost:8081/ws'
```

Deploy your frontend to a service like:
- **Vercel**: `vercel --prod`
- **Netlify**: `netlify deploy --prod`
- **AWS S3 + CloudFront**: Static website hosting

## 📞 Support and Maintenance

### Monitoring Setup

Consider setting up monitoring with:
- **CloudWatch**: AWS native monitoring
- **DataDog**: Application performance monitoring
- **Uptime Robot**: Simple uptime monitoring

### Scheduled Maintenance

- **Monthly**: Review logs for errors
- **Weekly**: Check SSL certificate status
- **Daily**: Monitor disk space and memory usage

---

## 🎉 Deployment Complete!

Your HyperSwipe server should now be running at:
- **API Documentation**: `https://your-domain.com/docs`
- **Health Check**: `https://your-domain.com/health`
- **WebSocket**: `wss://your-domain.com/ws`

For issues or questions, check the logs and troubleshooting section above.