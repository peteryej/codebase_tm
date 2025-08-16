# Codebase Time Machine - Deployment Guide

## Quick Start

### Prerequisites
- Python 3.9 or higher
- Git
- 10GB free disk space
- 2GB RAM minimum

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd codebase_tm

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
nano .env
```

Required environment variables:
```env
# GitHub Configuration (optional but recommended)
GITHUB_TOKEN=your_github_token_here

# LLM Configuration (optional for basic functionality)
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key_here

# Database Configuration
DATABASE_PATH=./data/cache/cache.db
REPOS_PATH=./data/repos

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here
FLASK_PORT=5000

# Analysis Configuration
MAX_REPO_SIZE=10000
CACHE_DURATION=86400
MAX_CONCURRENT_ANALYSES=3
```

### 3. Initialize Database

```bash
# Initialize the database
python backend/database/init_db.py
```

### 4. Run the Application

```bash
# Start the Flask backend
python backend/app.py
```

The application will be available at: http://localhost:5000

### 5. Test with Sample Repository

1. Open http://localhost:5000 in your browser
2. Enter: `https://github.com/peteryej/personal_assistant`
3. Click "Analyze" and wait for the analysis to complete
4. Explore the dashboard and ask questions in the chat interface

## Detailed Setup Instructions

### GitHub Token Setup (Recommended)

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with `public_repo` scope
3. Add the token to your `.env` file as `GITHUB_TOKEN`

This increases API rate limits and improves analysis reliability.

### LLM Integration Setup (Optional)

For enhanced natural language processing:

#### OpenAI Setup
1. Get an API key from https://platform.openai.com/
2. Add to `.env`:
   ```env
   LLM_PROVIDER=openai
   OPENAI_API_KEY=your_key_here
   ```

#### Anthropic Claude Setup
1. Get an API key from https://console.anthropic.com/
2. Add to `.env`:
   ```env
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=your_key_here
   ```

### Directory Structure

After setup, your directory structure should look like:

```
codebase_tm/
├── backend/
│   ├── api/
│   │   ├── repository.py
│   │   ├── chat.py
│   │   └── visualization.py
│   ├── analyzers/
│   │   ├── commit_analyzer.py
│   │   └── ownership_analyzer.py
│   ├── database/
│   │   ├── models.py
│   │   └── init_db.py
│   ├── git_ops/
│   │   ├── github_client.py
│   │   └── repo_manager.py
│   └── app.py
├── frontend/
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   ├── config.js
│   │   ├── api.js
│   │   └── main.js
│   └── index.html
├── data/
│   ├── cache/
│   │   └── cache.db
│   └── repos/
├── .env
├── requirements.txt
└── README.md
```

## Production Deployment

### Using Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app
```

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/cache data/repos

# Initialize database
RUN python backend/database/init_db.py

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "backend.app:app"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  codebase-tm:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
```

Deploy with Docker:

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

### Nginx Reverse Proxy

Create `/etc/nginx/sites-available/codebase-tm`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files (if serving separately)
    location /static {
        alias /path/to/codebase_tm/frontend;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/codebase-tm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Systemd Service

Create `/etc/systemd/system/codebase-tm.service`:

```ini
[Unit]
Description=Codebase Time Machine
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/path/to/codebase_tm
Environment=PATH=/path/to/codebase_tm/venv/bin
ExecStart=/path/to/codebase_tm/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 backend.app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable codebase-tm
sudo systemctl start codebase-tm
sudo systemctl status codebase-tm
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GITHUB_TOKEN` | GitHub API token | None | No |
| `LLM_PROVIDER` | LLM provider (openai/anthropic) | None | No |
| `OPENAI_API_KEY` | OpenAI API key | None | No |
| `ANTHROPIC_API_KEY` | Anthropic API key | None | No |
| `DATABASE_PATH` | SQLite database path | `./data/cache/cache.db` | No |
| `REPOS_PATH` | Repository storage path | `./data/repos` | No |
| `FLASK_ENV` | Flask environment | `development` | No |
| `FLASK_DEBUG` | Enable Flask debug mode | `True` | No |
| `SECRET_KEY` | Flask secret key | `dev-secret-key` | Yes |
| `FLASK_PORT` | Flask port | `5000` | No |
| `MAX_REPO_SIZE` | Max commits to analyze | `10000` | No |
| `CACHE_DURATION` | Cache duration (seconds) | `86400` | No |
| `MAX_CONCURRENT_ANALYSES` | Max concurrent analyses | `3` | No |

### Performance Tuning

#### For Large Repositories
```env
MAX_REPO_SIZE=50000
MAX_CONCURRENT_ANALYSES=1
CACHE_DURATION=172800  # 48 hours
```

#### For High Traffic
```env
MAX_CONCURRENT_ANALYSES=5
CACHE_DURATION=3600    # 1 hour
```

## Monitoring and Maintenance

### Log Files

Application logs are written to stdout. In production, configure log rotation:

```bash
# Using systemd journal
journalctl -u codebase-tm -f

# Using Docker
docker-compose logs -f
```

### Database Maintenance

```bash
# Check database size
ls -lh data/cache/cache.db

# Clean old cache entries (if needed)
python -c "
from backend.database.models import get_session, QueryCache
from datetime import datetime, timedelta
session = get_session()
cutoff = datetime.utcnow() - timedelta(days=7)
session.query(QueryCache).filter(QueryCache.created_at < cutoff).delete()
session.commit()
print('Cleaned old cache entries')
"
```

### Repository Storage Cleanup

```bash
# Check repository storage usage
du -sh data/repos/

# Clean repositories older than 30 days
python -c "
from backend.git_ops.repo_manager import RepositoryManager
manager = RepositoryManager()
result = manager.cleanup_old_repositories(30)
print(f'Cleaned {result[\"cleaned_count\"]} repositories')
"
```

### Health Checks

Create a health check endpoint test:

```bash
# Check if application is running
curl -f http://localhost:5000/health || exit 1

# Check database connectivity
python -c "
from backend.database.models import get_session
try:
    session = get_session()
    session.execute('SELECT 1')
    print('Database OK')
except Exception as e:
    print(f'Database Error: {e}')
    exit(1)
"
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors
```bash
# Check database file permissions
ls -la data/cache/cache.db

# Reinitialize database
rm data/cache/cache.db
python backend/database/init_db.py
```

#### 2. Git Clone Failures
```bash
# Check disk space
df -h

# Check repository permissions
ls -la data/repos/

# Clear repository cache
rm -rf data/repos/*
```

#### 3. GitHub API Rate Limiting
- Add `GITHUB_TOKEN` to `.env`
- Reduce analysis frequency
- Check rate limit status in logs

#### 4. Memory Issues
```bash
# Check memory usage
free -h

# Reduce concurrent analyses
echo "MAX_CONCURRENT_ANALYSES=1" >> .env

# Restart application
sudo systemctl restart codebase-tm
```

#### 5. Port Already in Use
```bash
# Find process using port 5000
lsof -i :5000

# Kill process or change port
echo "FLASK_PORT=5001" >> .env
```

### Debug Mode

Enable debug logging:

```env
FLASK_DEBUG=True
FLASK_ENV=development
```

View detailed logs:

```bash
# Run in foreground with debug output
python backend/app.py
```

## Security Considerations

### Production Security

1. **Change default secret key**:
   ```env
   SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
   ```

2. **Disable debug mode**:
   ```env
   FLASK_DEBUG=False
   FLASK_ENV=production
   ```

3. **Use HTTPS** with proper SSL certificates

4. **Firewall configuration**:
   ```bash
   # Only allow HTTP/HTTPS
   sudo ufw allow 80
   sudo ufw allow 443
   sudo ufw deny 5000  # Don't expose Flask directly
   ```

5. **Regular updates**:
   ```bash
   pip install --upgrade -r requirements.txt
   ```

### API Key Security

- Store API keys in environment variables, never in code
- Use restricted API keys with minimal required permissions
- Rotate API keys regularly
- Monitor API usage for anomalies

## Backup and Recovery

### Database Backup

```bash
# Create backup
cp data/cache/cache.db data/cache/cache.db.backup.$(date +%Y%m%d)

# Automated backup script
#!/bin/bash
BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
cp data/cache/cache.db "$BACKUP_DIR/cache_$DATE.db"
find "$BACKUP_DIR" -name "cache_*.db" -mtime +7 -delete
```

### Repository Data Backup

```bash
# Backup repository data
tar -czf repos_backup_$(date +%Y%m%d).tar.gz data/repos/

# Restore from backup
tar -xzf repos_backup_YYYYMMDD.tar.gz
```

## Performance Optimization

### Database Optimization

```sql
-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_commits_repo_timestamp ON commits(repo_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ownership_file_percentage ON ownership(file_id, percentage);
CREATE INDEX IF NOT EXISTS idx_query_cache_hash ON query_cache(query_hash);
```

### Caching Strategy

- Enable query result caching
- Use appropriate cache durations
- Implement cache warming for popular repositories
- Monitor cache hit rates

### Resource Limits

```bash
# Set resource limits in systemd service
[Service]
MemoryLimit=2G
CPUQuota=200%
```

This deployment guide provides comprehensive instructions for setting up, configuring, and maintaining the Codebase Time Machine in various environments.