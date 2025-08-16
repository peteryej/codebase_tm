# AWS Lightsail Deployment Guide

## Quick Fix for "Network error" Issue

The "Network error. Please check your connection and try again." error occurs because the frontend is trying to connect to `localhost` instead of your actual server IP. This has been fixed with environment-aware configuration.

## What Was Fixed

1. **Frontend API Configuration**: Now automatically detects if running on localhost (development) or production server
2. **CORS Configuration**: Backend now allows requests from any origin in production mode
3. **Environment Configuration**: Proper production settings in `.env.production`

## Deployment Steps

### 1. Create AWS Lightsail Instance

1. Go to [AWS Lightsail Console](https://lightsail.aws.amazon.com/)
2. Click "Create instance"
3. Choose:
   - **Platform**: Linux/Unix
   - **Blueprint**: OS Only → Ubuntu 20.04 LTS
   - **Instance plan**: At least $10/month (1 GB RAM, 1 vCPU, 40 GB SSD)
4. Name your instance (e.g., "codebase-tm")
5. Click "Create instance"

### 2. Configure Networking

1. Go to your instance → Networking tab
2. Add firewall rule:
   - **Application**: HTTP
   - **Protocol**: TCP
   - **Port**: 80
   - **Source**: Anywhere (0.0.0.0/0)

### 3. Connect and Deploy

```bash
# Download your SSH key from Lightsail console
# Connect to your instance
ssh -i /path/to/your-key.pem ubuntu@YOUR_LIGHTSAIL_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt update
sudo apt install -y python3 python3-pip git curl

# Install the correct python3-venv package for your Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
sudo apt install -y python${PYTHON_VERSION}-venv

# Clone your repository
git clone https://github.com/your-username/your-repo.git
cd codebase_tm

# Set up environment
cp .env.production .env

# Edit environment file with your API keys
nano .env
# Update GITHUB_TOKEN and OPENAI_API_KEY with your actual keys

# Make deployment script executable and run (requires sudo for port 80)
chmod +x deploy.sh
sudo ./deploy.sh
```

### 4. Access Your Application

Your application will be available at: `http://YOUR_LIGHTSAIL_IP`

The deployment script will show you the exact URL when it starts.

## Environment Variables to Update

Edit your `.env` file with these values:

```env
# Required: Add your GitHub token for better API limits
GITHUB_TOKEN=ghp_your_actual_github_token_here

# Optional: Add OpenAI API key for enhanced features
OPENAI_API_KEY=sk-your_actual_openai_key_here

# Production settings (already configured)
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=your-secure-secret-key-here
```

## Troubleshooting

### Still Getting Network Error?

1. **Check if service is running**:
   ```bash
   ps aux | grep gunicorn
   ```

2. **Check application logs**:
   ```bash
   # If you see any errors, restart the service
   pkill gunicorn
   ./deploy.sh
   ```

3. **Test API directly**:
   ```bash
   curl http://YOUR_LIGHTSAIL_IP/health
   ```
   Should return: `{"status":"healthy","service":"Codebase Time Machine","version":"1.0.0"}`

4. **Check firewall**:
   ```bash
   sudo ufw status
   # If active, allow port 80
   sudo ufw allow 80
   ```

### Port Already in Use

```bash
# Find what's using port 80
sudo lsof -i :80

# Kill the process
sudo kill -9 PID_NUMBER

# Restart deployment
./deploy.sh
```

### Memory Issues

If you get memory errors with large repositories:

1. **Upgrade your Lightsail instance** to at least 2 GB RAM
2. **Or reduce concurrent analyses**:
   ```bash
   echo "MAX_CONCURRENT_ANALYSES=1" >> .env
   ```

## Running as a Service (Optional)

To keep the application running after you disconnect:

```bash
# Install screen
sudo apt install screen

# Start in screen session
screen -S codebase-tm
./deploy.sh

# Detach from screen: Ctrl+A, then D
# Reattach later: screen -r codebase-tm
```

## Security Considerations

1. **Change the secret key** in `.env`:
   ```bash
   python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" >> .env
   ```

2. **Keep your API keys secure** - never commit them to version control

3. **Consider using HTTPS** for production (requires domain name and SSL certificate)

## Cost Estimation

- **Minimum instance**: $10/month (1 GB RAM, 1 vCPU)
- **Recommended**: $20/month (2 GB RAM, 1 vCPU) for better performance
- **Data transfer**: First 1 TB free, then $0.09/GB

## Support

If you continue to experience issues:

1. Check the main deployment guide: `deployment-guide.md`
2. Verify all environment variables are set correctly
3. Ensure your GitHub token has proper permissions
4. Test with a small repository first

The application should now work correctly on AWS Lightsail without network errors!