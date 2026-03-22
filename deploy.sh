#!/bin/bash
# deploy.sh — Deploy latest tainment-bot to Raspberry Pi
# Usage: bash deploy.sh

PI_USER="tribs"
PI_HOST="192.168.1.19"
BOT_DIR="/home/tribs/tainment-bot"
SERVICE="tainment-bot"

echo "==> Stopping bot service on Pi..."
ssh "$PI_USER@$PI_HOST" "sudo systemctl stop $SERVICE 2>/dev/null || true"

echo "==> Pulling latest code on Pi..."
ssh "$PI_USER@$PI_HOST" "cd $BOT_DIR && git pull origin master"

echo "==> Installing/updating dependencies..."
ssh "$PI_USER@$PI_HOST" "cd $BOT_DIR && pip3 install -r requirements.txt -q"

echo "==> Copying systemd service file..."
ssh "$PI_USER@$PI_HOST" "sudo cp $BOT_DIR/tainment-bot.service /etc/systemd/system/$SERVICE.service && sudo systemctl daemon-reload"

echo "==> Starting bot service..."
ssh "$PI_USER@$PI_HOST" "sudo systemctl enable $SERVICE && sudo systemctl start $SERVICE"

echo "==> Waiting 5s then checking status..."
sleep 5
ssh "$PI_USER@$PI_HOST" "sudo systemctl status $SERVICE --no-pager -l"

echo ""
echo "==> Setting up Nginx vhost for tainment.trijbsworlds.nl..."
NGINX_CONF="/etc/nginx/sites-available/tainment.trijbsworlds.nl"
NGINX_ENABLED="/etc/nginx/sites-enabled/tainment.trijbsworlds.nl"
ssh "$PI_USER@$PI_HOST" "
  # Install nginx if not present
  if ! command -v nginx &>/dev/null; then
    sudo apt-get install -y nginx
  fi

  # Copy vhost config
  sudo cp $BOT_DIR/web/nginx/tainment.trijbsworlds.nl.conf $NGINX_CONF

  # Enable site
  sudo ln -sf $NGINX_CONF $NGINX_ENABLED

  # Test config
  sudo nginx -t && sudo systemctl reload nginx && echo 'Nginx reloaded OK'

  # Enable nginx on boot
  sudo systemctl enable nginx
"

echo ""
echo "==> Deploy complete."
echo ""
echo "    Bot logs:  ssh $PI_USER@$PI_HOST 'tail -f $BOT_DIR/tainment_bot.log'"
echo "    Web logs:  ssh $PI_USER@$PI_HOST 'tail -f /var/log/nginx/tainment.trijbsworlds.nl.access.log'"
echo ""
echo "    DNS step:  Add a DNS A record (or CNAME) for tainment.trijbsworlds.nl"
echo "               pointing to your Pi's public IP."
echo "               (Check public IP: curl ifconfig.me on the Pi)"
