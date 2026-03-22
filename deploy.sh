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
echo "==> Deploy complete. Tail logs with:"
echo "    ssh $PI_USER@$PI_HOST 'tail -f $BOT_DIR/tainment_bot.log'"
