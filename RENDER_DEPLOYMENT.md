# LQOA Render Deployment Configuration

## 🔧 Environment Variables for Render Services

### 📊 PostgreSQL Database Service
**Service Name**: `lqoa-postgres`
- **Database Name**: `lqoa`
- **User**: `lqoa_user`  
- **Region**: Oregon (US West)
- **Plan**: Free

After creation, copy the **Internal Database URL** for use in both services.

### 🚀 API Service Environment Variables
**Service Name**: `lqoa-api`

#### Required Variables:
```
DATABASE_URL = postgresql://[auto-provided-by-render-postgres-service]
JWT_SECRET_KEY = [generate-secure-32-char-string]
DEBUG = false
LOG_LEVEL = INFO
API_HOST = 0.0.0.0
JWT_ALGORITHM = HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 720
ENRICHMENT_PROVIDER = mock
STRUCTURED_LOGGING = true
ENVIRONMENT = production
```

#### Optional Variables:
```
OPENAI_API_KEY = sk-[your-openai-key]
CLEARBIT_API_KEY = sk-[your-clearbit-key]
PDL_API_KEY = [your-pdl-key]
REDIS_URL = redis://[redis-service-url]
```

### 🎨 Streamlit Service Environment Variables
**Service Name**: `lqoa-streamlit`

#### Required Variables:
```
DATABASE_URL = [same-as-api-service]
JWT_SECRET_KEY = [same-as-api-service]
DEBUG = false
LOG_LEVEL = INFO
ENRICHMENT_PROVIDER = mock
STRUCTURED_LOGGING = true
ENVIRONMENT = production
API_BASE_URL = https://lqoa-api.onrender.com
```

#### Optional Variables:
```
OPENAI_API_KEY = [same-as-api-service]
CLEARBIT_API_KEY = [same-as-api-service]
PDL_API_KEY = [same-as-api-service]
```

## 🔐 Generate JWT Secret Key

Run this command to generate a secure JWT secret:

```bash
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

## 📝 Service Configuration Summary

### API Service (`lqoa-api`):
- **Build Command**: `python -m pip install --upgrade pip setuptools wheel && python -m pip install -r requirements.txt`
- **Start Command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Pre-Deploy**: `python -m database.init_db`

### Streamlit Service (`lqoa-streamlit`):
- **Build Command**: `python -m pip install --upgrade pip setuptools wheel && python -m pip install -r requirements.txt`
- **Start Command**: `streamlit run gate/enhanced_streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --server.runOnSave false --browser.gatherUsageStats false`

## 🎯 Deployment Order

1. **PostgreSQL Database** → Wait for completion
2. **API Service** → Copy DATABASE_URL, configure variables, deploy
3. **Streamlit Service** → Use API_BASE_URL from deployed API service
4. **Test & Verify** → Check both services are running

## ✅ Default Login Credentials

After deployment, use these credentials to test:

- **Admin**: `admin` / `admin123`
- **Reviewer**: `reviewer` / `review123`
- **Viewer**: `viewer` / `view123`

**⚠️ IMPORTANT**: Change these passwords immediately after first login!

## 🔍 Health Check URLs

- **API Health**: `https://lqoa-api.onrender.com/`
- **API Docs**: `https://lqoa-api.onrender.com/api/docs`
- **Streamlit App**: `https://lqoa-streamlit.onrender.com/`

## 🚨 Troubleshooting

### Build Failures:
- Check `requirements.txt` is in project root
- Ensure Python 3.11+ is specified in environment

### Database Errors:
- Verify `DATABASE_URL` is identical in both services
- Check PostgreSQL service is running and healthy

### Authentication Issues:
- Ensure `JWT_SECRET_KEY` is identical in both services
- Verify the key is properly URL-safe encoded

### Service Communication:
- Confirm `API_BASE_URL` in Streamlit service matches deployed API URL
- Check CORS configuration if needed