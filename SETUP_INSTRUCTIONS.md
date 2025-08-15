# 🚀 HyperSwipe Server Setup Instructions

## Step-by-Step Setup

### 1. **Prepare Your Files on EC2**

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-server-ip

# Create the project directory
sudo mkdir -p /home/ubuntu/projects/hyperswipe-server
sudo chown ubuntu:ubuntu /home/ubuntu/projects/hyperswipe-server
cd /home/ubuntu/projects/hyperswipe-server
```

### 2. **Upload Your Files**

**Option A: Using SCP from your local machine**
```bash
# From your local machine (where you have the hyperswipe-server folder)
scp -r -i your-key.pem ./hyperswipe-server/* ubuntu@your-server-ip:/home/ubuntu/projects/hyperswipe-server/
```

**Option B: Using Git**
```bash
# On the server
git clone https://github.com/adilhusain01/hyperswipe-server.git /tmp/hyperswipe-temp
cp -r /tmp/hyperswipe-temp/* /home/ubuntu/projects/hyperswipe-server/
rm -rf /tmp/hyperswipe-temp
```

### 3. **Verify Files Are Present**

```bash
cd /home/ubuntu/projects/hyperswipe-server
ls -la

# You should see these files:
# - Dockerfile
# - docker-compose.yml
# - requirements.txt
# - app/ (directory)
# - run.py
# - deploy-docker.sh
# - nginx/ (directory)
```

### 4. **Run the Deployment Script**

```bash
# Make the deployment script executable
chmod +x deploy-docker.sh

# Run the deployment
./deploy-docker.sh
```

### 5. **What the Script Does**

The deployment script will automatically:
- ✅ Install Docker and Docker Compose
- ✅ Create necessary directories
- ✅ Build your application container
- ✅ Setup Nginx with SSL certificates
- ✅ Start all services
- ✅ Create management scripts

### 6. **Test Your Deployment**

After deployment completes:

```bash
# Check if services are running
cd /home/ubuntu/projects/hyperswipe-server
docker-compose ps

# Test the API
curl -f https://app.hyperswipe.rizzmo.site/health

# Test WebSocket (install websocat first: cargo install websocat)
echo '{"type":"ping"}' | websocat wss://app.hyperswipe.rizzmo.site/ws
```

### 7. **Management Commands**

After deployment, you'll have these management scripts:

```bash
# Start all services
~/start-hyperswipe.sh

# Stop all services  
~/stop-hyperswipe.sh

# View logs
~/logs-hyperswipe.sh

# Update and restart (after code changes)
~/update-hyperswipe.sh
```

## 🔧 Configuration Details

### Environment Variables
Located at: `/home/ubuntu/projects/hyperswipe-server/.env`

```bash
DOMAIN=app.hyperswipe.rizzmo.site
EMAIL=admin@hyperswipe.rizzmo.site
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://app.hyperswipe.rizzmo.site
```

### Project Structure
```
/home/ubuntu/projects/hyperswipe-server/
├── app/                          # Your FastAPI application
├── nginx/                        # Nginx configuration
│   ├── sites-available/
│   ├── logs/
│   └── nginx.conf
├── logs/                         # Application logs
├── Dockerfile                    # Container build instructions
├── docker-compose.yml           # Service orchestration
├── requirements.txt             # Python dependencies
├── run.py                       # Application entry point
├── deploy-docker.sh             # Deployment script
└── .env                         # Environment configuration
```

## 🚨 Troubleshooting

### If Deployment Fails

1. **Check Docker is installed**:
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Check file permissions**:
   ```bash
   cd /home/ubuntu/projects/hyperswipe-server
   ls -la
   # All files should be owned by ubuntu:ubuntu
   ```

3. **Check logs**:
   ```bash
   ~/logs-hyperswipe.sh
   # or
   cd /home/ubuntu/projects/hyperswipe-server
   docker-compose logs -f
   ```

4. **Restart services**:
   ```bash
   ~/stop-hyperswipe.sh
   ~/start-hyperswipe.sh
   ```

### If SSL Certificate Fails

```bash
# Check domain DNS
nslookup app.hyperswipe.rizzmo.site

# Manual certificate request
cd /home/ubuntu/projects/hyperswipe-server
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/html \
    --email admin@hyperswipe.rizzmo.site \
    --agree-tos \
    --no-eff-email \
    -d app.hyperswipe.rizzmo.site
```

## 🎯 Success Checklist

- [ ] Files are in `/home/ubuntu/projects/hyperswipe-server/`
- [ ] `deploy-docker.sh` runs without errors
- [ ] `docker-compose ps` shows all services running
- [ ] `https://app.hyperswipe.rizzmo.site/health` returns success
- [ ] `https://app.hyperswipe.rizzmo.site/docs` shows API documentation
- [ ] WebSocket connection works at `wss://app.hyperswipe.rizzmo.site/ws`

## 🔄 Updates and Maintenance

### To Update Your Application

1. **Upload new code** to `/home/ubuntu/projects/hyperswipe-server/`
2. **Run the update script**: `~/update-hyperswipe.sh`
3. **Check status**: `docker-compose ps`

### Regular Maintenance

```bash
# View logs
~/logs-hyperswipe.sh

# Check system resources
htop

# Check disk space
df -h

# Check SSL certificate status
cd /home/ubuntu/projects/hyperswipe-server
docker-compose run --rm certbot certificates
```

That's it! Your HyperSwipe server will be running at `https://app.hyperswipe.rizzmo.site` 🚀