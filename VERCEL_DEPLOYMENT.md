# Vercel Deployment Guide

**Status:** Ready for Vercel deployment

## ✅ Frontend Setup
- Vite build configured
- React with Tailwind CSS
- Supabase integration
- Environment variables configured

## 📋 Deployment Checklist

### 1. **Connect GitHub to Vercel** (One-time setup)
```bash
# Visit: https://vercel.com/new
# Select GitHub repository: stevenstimo/wonderz-agentics
# Root directory: web_ui/frontend
# Build command: npm run build
# Output directory: dist
```

### 2. **Environment Variables on Vercel**
Set these in Vercel Project Settings > Environment Variables:
```
VITE_API_URL=https://your-api-domain.com
VITE_SUPABASE_URL=your-supabase-url
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### 3. **Automatic Deployments**
- Every push to `main` branch triggers deployment
- Preview deployments for PRs
- Rollback to previous deployments available

## 🚀 Manual Deployment (Alternative)

### Using Vercel CLI
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy from root directory
vercel --prod

# Deploy frontend only
cd web_ui/frontend
vercel --prod
```

## 📊 Current Deployment Status

| Component | Status | Location |
|-----------|--------|----------|
| Frontend (React) | ✅ Ready | Vercel |
| Backend (FastAPI) | ✅ Ready | Can deploy to Railway/Heroku/AWS |
| Database | ✅ Supabase | PostgreSQL with auto-scaling |
| API Integration | ✅ Configured | Environment variables |

## 🔗 URLs After Deployment
- **Frontend**: `https://wonderz-agentics.vercel.app`
- **Backend**: To be configured
- **Database**: Supabase (auto-managed)

## ⚙️ Build Configuration
- **Framework**: Vite + React
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Node Version**: 18.x (default)
- **Install Command**: `npm ci`

## 📝 Configuration Files
- `vercel.json` - Routing and build settings
- `.vercelignore` - Files to skip in deployment
- `vite.config.js` - Vite build configuration
- `package.json` - Dependencies and build script

## 🔑 Important Notes

1. **Frontend only on Vercel**: React SPA deployed to Vercel edge network
2. **Backend separately**: FastAPI needs different hosting (Railway, Heroku, AWS Lambda, etc.)
3. **API proxy**: Configure API URL in environment variables
4. **Supabase**: Already hosted and managed
5. **Auto-deploy**: Enabled when repo connected to Vercel

## ✨ Features Included in Deployment
- ✅ React 18 with Vite (fast builds)
- ✅ Tailwind CSS (optimized)
- ✅ React Router (client-side routing)
- ✅ Toast notifications
- ✅ Form validation
- ✅ Loading states
- ✅ Error handling
- ✅ Accessibility (WCAG AA)

## 📱 Pre-deployment Checklist
- ✅ All components tested locally
- ✅ Build succeeds: `npm run build`
- ✅ No console errors
- ✅ Environment variables ready
- ✅ GitHub repository up to date
- ✅ All code committed

---

**Next Step**: Connect your GitHub repository to Vercel via https://vercel.com/new
