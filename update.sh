#!/bin/bash
set -e

echo "🔄 Pulling latest changes..."
git pull

echo "🛑 Stopping containers..."
docker-compose down

echo "🗑 Removing old image..."
docker rmi tgbot_tgbot 2>/dev/null || true

echo "🔨 Building and starting..."
docker-compose up -d --build

echo "📋 Logs (Ctrl+C to exit):"
docker-compose logs -f tgbot