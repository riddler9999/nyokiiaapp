#!/bin/bash
# Deploy Dhamma Audio-to-Video Converter on Hostinger Docker VPS
# Usage: ssh into your VPS, clone the repo, and run this script

set -e

echo "=== Dhamma Audio-to-Video Converter - Deploy ==="

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo "Docker Compose plugin required. Install it with:"
    echo "  apt-get install docker-compose-plugin"
    exit 1
fi

# Create .env if missing
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo ">>> Created .env from .env.example"
    echo ">>> Edit .env with your API keys before starting:"
    echo "    nano .env"
    echo ""
    echo "Required keys:"
    echo "  PEXELS_API_KEY   - Get from https://www.pexels.com/api/"
    echo "  TELEGRAM_BOT_TOKEN - Get from @BotFather on Telegram"
    echo "  TELEGRAM_CHAT_ID   - Your channel/group ID"
    echo ""
    echo "Optional (for YouTube):"
    echo "  YOUTUBE_CLIENT_ID     - Google Cloud Console"
    echo "  YOUTUBE_CLIENT_SECRET - Google Cloud Console"
    echo ""
    echo "After editing .env, run this script again."
    exit 0
fi

# Create media directory on host
mkdir -p /media/dhamma

# Build and start
echo "Building and starting containers..."
docker compose up -d --build

echo ""
echo "=== Deployment Complete ==="
echo "App running at: http://$(hostname -I | awk '{print $1}'):80"
echo ""
echo "To view logs:  docker compose logs -f"
echo "To stop:       docker compose down"
echo ""
echo "For SSL, update nginx.conf with your domain, then run:"
echo "  docker compose run --rm certbot certonly --webroot -w /var/lib/letsencrypt -d your-domain.com"
