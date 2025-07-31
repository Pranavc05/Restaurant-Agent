# Deployment Guide - AI Restaurant Agent

This guide covers deploying the AI Restaurant Agent backend to various platforms.

## 🚀 Quick Start with Railway (Recommended)

Railway is the easiest way to deploy this application with minimal configuration.

### 1. Prerequisites
- GitHub account
- Railway account (free tier available)
- API keys for required services

### 2. Deploy to Railway

1. **Fork/Clone the Repository**
   ```bash
   git clone <your-repo-url>
   cd restaurant-agent-backend
   ```

2. **Connect to Railway**
   - Go to [Railway.app](https://railway.app)
   - Sign in with GitHub
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository

3. **Configure Environment Variables**
   In Railway dashboard, add these environment variables:
   ```
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_phone_number
   OPENAI_API_KEY=your_openai_api_key
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   DATABASE_URL=postgresql://... (Railway will provide this)
   RESTAURANT_NAME=Your Restaurant Name
   RESTAURANT_HOURS=Monday-Sunday: 11:00 AM - 10:00 PM
   ```

4. **Add PostgreSQL Database**
   - In Railway dashboard, click "New" → "Database" → "PostgreSQL"
   - Railway will automatically set the `DATABASE_URL` environment variable

5. **Deploy**
   - Railway will automatically deploy when you push to your main branch
   - Or click "Deploy" in the dashboard

### 3. Configure Twilio

1. **Get Twilio Credentials**
   - Sign up at [Twilio.com](https://twilio.com)
   - Get Account SID and Auth Token from dashboard
   - Purchase a phone number

2. **Configure Webhook**
   - In Twilio Console, go to Phone Numbers → Manage → Active numbers
   - Click on your number
   - Set Voice webhook URL to: `https://your-railway-app.railway.app/voice/`
   - Set Status callback URL to: `https://your-railway-app.railway.app/voice/status`

## 🐳 Docker Deployment

### 1. Build Docker Image
```bash
docker build -t restaurant-agent .
```

### 2. Run with Docker Compose
```bash
docker-compose up -d
```

### 3. Docker Compose Configuration
Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/restaurant_agent
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
    depends_on:
      - db
      - redis

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=restaurant_agent
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

## ☁️ AWS Deployment

### 1. EC2 Deployment
```bash
# Launch EC2 instance (Ubuntu 20.04 recommended)
# Install dependencies
sudo apt update
sudo apt install python3-pip postgresql redis-server nginx

# Clone repository
git clone <your-repo-url>
cd restaurant-agent-backend

# Install Python dependencies
pip3 install -r requirements.txt

# Setup PostgreSQL
sudo -u postgres createdb restaurant_agent
sudo -u postgres createuser restaurant_user

# Configure environment
cp env.example .env
# Edit .env with your credentials

# Run migrations
alembic upgrade head

# Start application
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. AWS ECS Deployment
```bash
# Build and push Docker image to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t restaurant-agent .
docker tag restaurant-agent:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/restaurant-agent:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/restaurant-agent:latest

# Create ECS cluster and service
# Use AWS Console or AWS CLI to create ECS service
```

## 🔧 Environment Variables

### Required Variables
```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# OpenAI Configuration
OPENAI_API_KEY=your_openai_key

# ElevenLabs Configuration
ELEVENLABS_API_KEY=your_elevenlabs_key

# Database Configuration
DATABASE_URL=postgresql://user:password@host:port/database
```

### Optional Variables
```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379

# Restaurant Configuration
RESTAURANT_NAME=Your Restaurant Name
RESTAURANT_HOURS=Monday-Sunday: 11:00 AM - 10:00 PM
HUMAN_FALLBACK_NUMBER=+1234567890

# AI Configuration
MAX_RETRY_ATTEMPTS=2
CALL_RECORDING_CONSENT_TEXT=This call may be recorded...
SMS_CONSENT_TEXT=Would you like to receive a text message...
```

## 🔒 Security Considerations

### 1. API Key Security
- Never commit API keys to version control
- Use environment variables for all sensitive data
- Rotate API keys regularly
- Use least-privilege access for API keys

### 2. Database Security
- Use strong passwords for database
- Enable SSL/TLS for database connections
- Restrict database access to application servers only
- Regular database backups

### 3. Network Security
- Use HTTPS for all external communications
- Configure firewall rules appropriately
- Use VPC for AWS deployments
- Enable rate limiting

### 4. Compliance
- Ensure TCPA compliance for SMS
- Implement proper consent logging
- Follow GDPR/privacy regulations
- Document data retention policies

## 📊 Monitoring and Logging

### 1. Application Monitoring
```bash
# Health check endpoint
curl https://your-app.com/health

# Analytics endpoint
curl https://your-app.com/analytics/
```

### 2. Logging
- Application logs are available in Railway dashboard
- For AWS, use CloudWatch for logging
- For Docker, use `docker logs`

### 3. Metrics to Monitor
- Call volume and success rates
- API response times
- Database connection pool usage
- Error rates and types
- Reservation conversion rates

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Check database URL
   echo $DATABASE_URL
   
   # Test connection
   psql $DATABASE_URL -c "SELECT 1;"
   ```

2. **Twilio Webhook Errors**
   - Verify webhook URLs are correct
   - Check Twilio logs in console
   - Ensure HTTPS is used for webhooks

3. **API Key Issues**
   ```bash
   # Test OpenAI API
   curl -H "Authorization: Bearer $OPENAI_API_KEY" \
        https://api.openai.com/v1/models
   
   # Test ElevenLabs API
   curl -H "xi-api-key: $ELEVENLABS_API_KEY" \
        https://api.elevenlabs.io/v1/voices
   ```

4. **Migration Issues**
   ```bash
   # Reset database
   alembic downgrade base
   alembic upgrade head
   ```

## 📞 Support

For deployment issues:
1. Check the logs in your deployment platform
2. Verify all environment variables are set correctly
3. Test API endpoints individually
4. Check service status pages for external APIs

## 🔄 Updates and Maintenance

### 1. Application Updates
```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Restart application
# (Platform-specific restart command)
```

### 2. Database Maintenance
```bash
# Backup database
pg_dump $DATABASE_URL > backup.sql

# Monitor database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size(current_database()));"
```

### 3. Security Updates
- Regularly update dependencies
- Monitor security advisories
- Rotate API keys periodically
- Review access logs 