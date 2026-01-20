# Aadhaar Atlas - Deployment Guide

## Vercel Deployment Setup

This project is configured to deploy on Vercel with data loaded dynamically from GitHub.

### Prerequisites
- GitHub account with this repository
- Vercel account (free tier works)

### Deployment Steps

1. **Push to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Setup Vercel deployment"
   git push origin master
   ```

2. **Deploy to Vercel**:
   - Go to [vercel.com](https://vercel.com)
   - Click "Add New Project"
   - Import your GitHub repository: `natyavidhan/uidai-hackathon`
   - Vercel will auto-detect the configuration from `vercel.json`
   - Click "Deploy"

3. **Environment Variables** (Optional):
   - In Vercel dashboard, go to Settings → Environment Variables
   - Add: `USE_REMOTE=true` (though it's auto-detected on Vercel)

### How It Works

- **Data Loading**: CSV files are loaded from GitHub raw URLs on-the-fly
- **Caching**: LRU cache prevents repeated downloads within the same session
- **Local Development**: Set `USE_REMOTE=false` or omit it to use local files
- **Production**: Vercel automatically sets `VERCEL=true`, triggering remote loading

### Local Development

To test the remote loading locally:
```bash
export USE_REMOTE=true
cd interface
python main.py
```

To use local files (default):
```bash
cd interface
python main.py
```

### Files Structure

```
uidai-hackathon/
├── vercel.json          # Vercel configuration
├── requirements.txt     # Python dependencies
├── .vercelignore       # Files to exclude from deployment
├── interface/
│   ├── main.py         # Flask app (loads data remotely on Vercel)
│   ├── static/         # CSS, JS, GeoJSON
│   └── templates/      # HTML templates
└── datasets/           # CSV files (excluded from deployment, loaded from GitHub)
```

### Important Notes

1. **First Load**: Initial page load will be slow (~30-60s) as data is fetched from GitHub
2. **Cold Starts**: Vercel serverless functions have cold starts; subsequent requests are faster
3. **Timeouts**: If you hit timeout issues, consider:
   - Using a CDN for CSV files
   - Pre-processing data and hosting aggregated JSON
   - Upgrading to Vercel Pro for longer timeout limits

### Troubleshooting

**Issue**: Deployment fails
- Check Vercel logs for errors
- Ensure `requirements.txt` has correct versions
- Verify GitHub repo is public

**Issue**: Data loading is too slow
- Consider hosting CSVs on a faster CDN (Cloudflare R2, BunnyCDN)
- Pre-aggregate data and host JSON files instead

**Issue**: Timeout errors
- Vercel hobby plan has 10s timeout, Pro has 60s
- Consider switching to Cloudflare Pages + Workers for unlimited timeout
