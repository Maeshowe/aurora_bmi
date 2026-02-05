# AURORA BMI - Linux Server Deployment

## Quick Start

```bash
# Clone repository
cd /home/safrtam
git clone https://github.com/Maeshowe/aurora_bmi.git
cd aurora_bmi

# Run deployment script
chmod +x scripts/deploy_linux.sh
./scripts/deploy_linux.sh

# Configure API keys
nano .env
```

## Systemd Setup

### 1. Install systemd files

```bash
# Daily data collection
sudo cp scripts/aurora-daily.service /etc/systemd/system/
sudo cp scripts/aurora-daily.timer /etc/systemd/system/

# Dashboard web service (port 8503)
sudo cp scripts/aurora-dashboard.service /etc/systemd/system/

sudo systemctl daemon-reload
```

### 2. Enable and start services

```bash
# Enable daily data collection timer
sudo systemctl enable aurora-daily.timer
sudo systemctl start aurora-daily.timer

# Enable and start dashboard
sudo systemctl enable aurora-dashboard
sudo systemctl start aurora-dashboard
```

### 3. Verify

```bash
# Check timer status
sudo systemctl status aurora-daily.timer
sudo systemctl list-timers --all | grep aurora

# Check dashboard status
sudo systemctl status aurora-dashboard

# Check logs
journalctl -u aurora-daily.service -f
journalctl -u aurora-dashboard.service -f
```

## Nginx Configuration

Add to `/etc/nginx/sites-available/aurora.ssh.services`:

```nginx
server {
    listen 80;
    server_name aurora.ssh.services;

    location / {
        proxy_pass http://127.0.0.1:8503;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/aurora.ssh.services /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# SSL with certbot
sudo certbot --nginx -d aurora.ssh.services
```

## Port Allocation

| Service | Port | Domain |
|---------|------|--------|
| moneyflows | 8501 | https://moneyflows.ssh.services |
| obsidian | 8502 | https://obsidian.ssh.services |
| aurora | 8503 | https://aurora.ssh.services |

## Schedule

Daily data collection runs **Mon-Fri at 21:05 UTC** (22:05 CET), after US market close.

## Manual Commands

```bash
cd /home/safrtam/aurora_bmi
source .venv/bin/activate

# Run daily pipeline manually
python scripts/run_daily.py

# Run dashboard manually (for testing)
streamlit run aurora/dashboard/app.py --server.port 8503
```

## Systemd Service Files

### aurora-daily.service

```ini
[Unit]
Description=AURORA BMI Daily Data Collection
After=network.target

[Service]
Type=oneshot
User=safrtam
WorkingDirectory=/home/safrtam/aurora_bmi
ExecStart=/home/safrtam/aurora_bmi/.venv/bin/python scripts/run_daily.py
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### aurora-daily.timer

```ini
[Unit]
Description=AURORA BMI Daily Timer

[Timer]
OnCalendar=Mon-Fri 21:05 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

### aurora-dashboard.service

```ini
[Unit]
Description=AURORA BMI Dashboard
After=network.target

[Service]
Type=simple
User=safrtam
WorkingDirectory=/home/safrtam/aurora_bmi
ExecStart=/home/safrtam/aurora_bmi/.venv/bin/streamlit run aurora/dashboard/app.py --server.port 8503 --server.address 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

```bash
# Check logs
journalctl -u aurora-daily.service --since "1 hour ago"
journalctl -u aurora-dashboard.service -f

# Test API keys
cd /home/safrtam/aurora_bmi
source .venv/bin/activate
python -c "from aurora.core.config import get_settings; s = get_settings(); print(f'Polygon: {bool(s.polygon_api_key)}'); print(f'FMP: {bool(s.fmp_api_key)}'); print(f'UW: {bool(s.uw_api_key)}')"

# Force run data collection now
sudo systemctl start aurora-daily.service

# Restart dashboard
sudo systemctl restart aurora-dashboard
```

## Git Pull Updates

```bash
cd /home/safrtam/aurora_bmi
git pull origin main
sudo systemctl restart aurora-dashboard
```

## Environment Variables (.env)

```bash
# Required API Keys
POLYGON_API_KEY=your_polygon_key
FMP_API_KEY=your_fmp_key
UW_API_KEY=your_unusual_whales_key

# Optional
LOG_LEVEL=INFO
```
