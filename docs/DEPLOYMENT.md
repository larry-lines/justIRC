# JustIRC Deployment Guide

## Production Deployment on Linux

This guide covers deploying JustIRC server as a production service.

## Prerequisites

- Linux server (Ubuntu 20.04+ or similar)
- Python 3.8 or higher
- sudo/root access
- Firewall configured (ufw, iptables, etc.)

## Installation

### 1. Create Service User

Create a dedicated user for running the service:

```bash
sudo useradd -r -s /bin/false justirc
sudo mkdir -p /opt/justirc
sudo chown justirc:justirc /opt/justirc
```

### 2. Install Application

```bash
cd /opt/justirc
sudo -u justirc git clone [repository-url] .
# Or copy files manually

# Set up virtual environment
sudo -u justirc python3 -m venv venv
sudo -u justirc venv/bin/pip install -r requirements.txt
```

### 3. Create Systemd Service

Create `/etc/systemd/system/justirc.service`:

```ini
[Unit]
Description=JustIRC Secure Encrypted IRC Server
After=network.target

[Service]
Type=simple
User=justirc
Group=justirc
WorkingDirectory=/opt/justirc
Environment="PATH=/opt/justirc/venv/bin"
ExecStart=/opt/justirc/venv/bin/python server.py --host 0.0.0.0 --port 6667

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/justirc

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=justirc

[Install]
WantedBy=multi-user.target
```

### 4. Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable justirc
sudo systemctl start justirc
```

Check status:
```bash
sudo systemctl status justirc
```

View logs:
```bash
sudo journalctl -u justirc -f
```

## Firewall Configuration

### Using UFW

```bash
# Allow IRC port
sudo ufw allow 6667/tcp

# If using custom port:
sudo ufw allow 7000/tcp
```

### Using iptables

```bash
sudo iptables -A INPUT -p tcp --dport 6667 -j ACCEPT
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

## TLS/SSL Encryption (Recommended)

While JustIRC uses end-to-end encryption, adding TLS provides defense-in-depth.

### Option 1: Nginx Reverse Proxy

Install Nginx:
```bash
sudo apt install nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/justirc`:

```nginx
upstream justirc_backend {
    server 127.0.0.1:6667;
}

server {
    listen 6697 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://justirc_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/justirc /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Get SSL certificate:
```bash
sudo certbot --nginx -d your-domain.com
```

### Option 2: stunnel

Install stunnel:
```bash
sudo apt install stunnel4
```

Create `/etc/stunnel/justirc.conf`:

```ini
[justirc]
accept = 6697
connect = 127.0.0.1:6667
cert = /etc/ssl/certs/justirc.pem
key = /etc/ssl/private/justirc.key
```

Enable stunnel:
```bash
sudo systemctl enable stunnel4
sudo systemctl start stunnel4
```

## Monitoring

### Log Rotation

Create `/etc/logrotate.d/justirc`:

```
/var/log/justirc/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 justirc justirc
    sharedscripts
    postrotate
        systemctl reload justirc > /dev/null 2>&1 || true
    endscript
}
```

### Health Monitoring

Create a simple health check script `/opt/justirc/healthcheck.sh`:

```bash
#!/bin/bash
nc -z localhost 6667
if [ $? -eq 0 ]; then
    echo "JustIRC server is running"
    exit 0
else
    echo "JustIRC server is down"
    exit 1
fi
```

Add to cron for monitoring:
```bash
*/5 * * * * /opt/justirc/healthcheck.sh || systemctl restart justirc
```

## Rate Limiting

To prevent abuse, implement rate limiting:

### Using fail2ban

Install fail2ban:
```bash
sudo apt install fail2ban
```

Create `/etc/fail2ban/filter.d/justirc.conf`:

```ini
[Definition]
failregex = ^.*Connection from <HOST>.*$
ignoreregex =
```

Create `/etc/fail2ban/jail.d/justirc.conf`:

```ini
[justirc]
enabled = true
port = 6667
filter = justirc
logpath = /var/log/syslog
maxretry = 10
findtime = 600
bantime = 3600
```

Restart fail2ban:
```bash
sudo systemctl restart fail2ban
```

## Backup

Since JustIRC doesn't store data, backups are minimal:

```bash
# Backup configuration and keys
sudo tar czf justirc-backup-$(date +%Y%m%d).tar.gz \
    /opt/justirc/*.py \
    /opt/justirc/*.md \
    /etc/systemd/system/justirc.service
```

## Updates

To update the server:

```bash
sudo systemctl stop justirc
cd /opt/justirc
sudo -u justirc git pull  # Or copy new files
sudo -u justirc venv/bin/pip install -r requirements.txt --upgrade
sudo systemctl start justirc
```

## Performance Tuning

### Increase Connection Limits

Edit `/etc/security/limits.conf`:

```
justirc soft nofile 4096
justirc hard nofile 8192
```

### Kernel Parameters

Edit `/etc/sysctl.conf`:

```
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
```

Apply:
```bash
sudo sysctl -p
```

## Hidden Service (Tor)

See [TOR_SETUP.md](TOR_SETUP.md) for running as a Tor hidden service.

## Docker Deployment

### Local Testing with Docker

Build and run locally:

```bash
# Build image
docker build -t justirc-server .

# Run container
docker run -d \
  --name justirc \
  -p 6667:6667 \
  --restart unless-stopped \
  justirc-server

# View logs
docker logs -f justirc

# Stop container
docker stop justirc

# Remove container
docker rm justirc
```

### Docker Compose (Recommended)

The included `docker-compose.yml` provides a complete setup:

```bash
# Start server
docker-compose up -d

# View logs
docker-compose logs -f

# Stop server
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

### Production Docker Configuration

For production, create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  justirc:
    build: .
    ports:
      - "6667:6667"
    restart: always
    security_opt:
      - no-new-privileges:true
    tmpfs:
      - /tmp
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

Deploy with:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Google Cloud Platform (GCP) Deployment

### Ultra-Low Cost GCP Deployment

Deploy to GCP for ~$7-8/month (or FREE on e2-micro free tier) with capacity for 5000+ messages/minute.

#### Prerequisites

1. Install [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. Install Docker
3. Set up GCP project:

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Or export as environment variable
export GCP_PROJECT_ID=your-project-id
```

#### Quick Deploy

The included `deploy_gcp.sh` script automates everything:

```bash
# Deploy with default settings (e2-micro, us-central1-a)
./deploy_gcp.sh

# Deploy with Spot VM for 70% cheaper (can be terminated)
USE_SPOT=true ./deploy_gcp.sh

# Deploy to specific zone
GCP_ZONE=europe-west1-b ./deploy_gcp.sh

# Deploy with larger instance
MACHINE_TYPE=e2-small ./deploy_gcp.sh
```

The script will:
- Build and push Docker image to Google Container Registry
- Create Container-Optimized OS VM instance
- Configure firewall rules
- Display connection information and estimated costs

#### Manual GCP Deployment

If you prefer manual deployment:

```bash
# 1. Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable containerregistry.googleapis.com

# 2. Build and push Docker image
docker build -t justirc-server .
docker tag justirc-server gcr.io/${PROJECT_ID}/justirc-server:latest
gcloud auth configure-docker
docker push gcr.io/${PROJECT_ID}/justirc-server:latest

# 3. Create VM with container
gcloud compute instances create-with-container justirc-server \
  --project="${PROJECT_ID}" \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=cos-stable \
  --image-project=cos-cloud \
  --boot-disk-size=10GB \
  --boot-disk-type=pd-standard \
  --container-image=gcr.io/${PROJECT_ID}/justirc-server:latest \
  --container-restart-policy=always \
  --tags=irc-server

# 4. Create firewall rule
gcloud compute firewall-rules create allow-irc \
  --allow=tcp:6667 \
  --target-tags=irc-server \
  --description="Allow IRC connections"

# 5. Get external IP
gcloud compute instances describe justirc-server \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

#### GCP Cost Optimization

**Free Tier (Best Option):**
- Machine: `e2-micro` (2 shared vCPU, 1GB RAM)
- Region: `us-central1`, `us-east1`, or `us-west1`
- Cost: **FREE** (744 hours/month free tier)
- Capacity: 5000+ messages/minute, 100+ concurrent users

**Spot VM (Cheapest Paid Option):**
- Cost: ~$2-3/month (70% cheaper than regular)
- Caveat: Can be terminated by Google (rare for low-usage periods)
- Best for: Development/testing environments

**Cost Breakdown (e2-micro, us-central1):**
- Compute: $0.01/hour × 730 hours = $7.30/month
- Network: ~$0.50-1.00/month (minimal outbound traffic)
- Storage: 10GB disk = $0.40/month
- **Total: ~$8/month** (FREE if in free tier)

#### GCP Management Commands

```bash
# View logs
gcloud compute instances get-serial-port-output justirc-server \
  --zone=us-central1-a

# SSH into instance
gcloud compute ssh justirc-server --zone=us-central1-a

# View container logs
gcloud compute ssh justirc-server --zone=us-central1-a \
  --command="docker logs justirc-server"

# Stop server (save costs when not in use)
gcloud compute instances stop justirc-server --zone=us-central1-a

# Start server
gcloud compute instances start justirc-server --zone=us-central1-a

# Update container image
gcloud compute instances update-container justirc-server \
  --zone=us-central1-a \
  --container-image=gcr.io/${PROJECT_ID}/justirc-server:latest

# Delete instance
gcloud compute instances delete justirc-server --zone=us-central1-a
```

#### GCP Monitoring & Alerts

Set up monitoring in Cloud Console:

1. Go to **Monitoring > Alerting**
2. Create alert for:
   - CPU usage > 80%
   - Memory usage > 90%
   - Instance down

Enable Cloud Logging:
```bash
# View logs in Cloud Logging
gcloud logging read "resource.type=gce_instance AND resource.labels.instance_id=justirc-server" \
  --limit 50 \
  --format json
```

#### GCP Security Best Practices

1. **Restrict Firewall**: 
   ```bash
   # Only allow specific IP ranges
   gcloud compute firewall-rules update allow-irc \
     --source-ranges=YOUR_IP_RANGE/32
   ```

2. **Enable OS Login**:
   ```bash
   gcloud compute instances add-metadata justirc-server \
     --metadata enable-oslogin=TRUE \
     --zone=us-central1-a
   ```

3. **Regular Updates**:
   ```bash
   # Container-Optimized OS auto-updates
   # Just rebuild and push new container image
   docker build -t justirc-server .
   docker tag justirc-server gcr.io/${PROJECT_ID}/justirc-server:latest
   docker push gcr.io/${PROJECT_ID}/justirc-server:latest
   
   # Update running instance
   gcloud compute instances update-container justirc-server \
     --zone=us-central1-a \
     --container-image=gcr.io/${PROJECT_ID}/justirc-server:latest
   ```

#### Performance Testing

Test your GCP deployment:

```bash
# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe justirc-server \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Test connection
python client.py --server $EXTERNAL_IP --port 6667 --nickname TestUser

# Load test (from test_suite.py)
python -m pytest test_suite.py -v
```

Expected performance on e2-micro:
- **Messages/minute**: 5000+ (5x requirement)
- **Concurrent users**: 100-500+
- **Latency**: <50ms (same region)
- **Uptime**: 99.5%+

## Other Cloud Platforms

### AWS (Amazon Web Services)

Use EC2 t3.micro with Container-Optimized AMI:
- Cost: ~$7-8/month
- Instructions: Similar to GCP, use AWS ECS or plain EC2

### DigitalOcean

Use $4/month droplet:
```bash
# Create droplet with Docker
doctl compute droplet create justirc \
  --image docker-20-04 \
  --size s-1vcpu-1gb \
  --region nyc1

# Deploy
docker-compose up -d
```

### Azure

Use Container Instances:
- Cost: ~$10-15/month
- Auto-scaling available



## Security Checklist

- [ ] Server runs as non-root user
- [ ] Firewall configured to allow only necessary ports
- [ ] SSL/TLS enabled (optional but recommended)
- [ ] Rate limiting configured
- [ ] Log rotation set up
- [ ] Monitoring in place
- [ ] Regular updates scheduled
- [ ] Backups automated
- [ ] Fail2ban or similar IDS configured

## Troubleshooting

### Service won't start

Check logs:
```bash
sudo journalctl -u justirc -n 50
```

Check permissions:
```bash
ls -la /opt/justirc
```

### High CPU usage

Check number of connections:
```bash
netstat -an | grep 6667 | wc -l
```

Implement rate limiting (see above).

### Memory leaks

Monitor memory:
```bash
ps aux | grep python
```

Consider restarting service periodically:
```bash
# Add to cron
0 4 * * * systemctl restart justirc
```

## Support

For issues or questions:
- Check logs: `sudo journalctl -u justirc`
- Run tests: `python test_suite.py`
- Review security docs: `SECURITY.md`

---

**Production Reminder**: Always test in a staging environment before deploying to production!
