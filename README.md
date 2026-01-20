# UIDAI Hackathon - Aadhaar Analytics Dashboard

An interactive district-level Aadhaar analytics dashboard with visualizations for enrolment, demographic updates, and biometric updates.

## Features

- 🗺️ Interactive India district map with D3.js
- 📊 Real-time charts with Chart.js (age distribution, updates comparison, trends)
- 🎨 Pastel color scheme for eye comfort
- 📱 Responsive design
- 🔍 District-level analytics with derived metrics
- ⚡ Fast performance with LRU caching

## Tech Stack

- **Backend**: Flask (Python 3.x)
- **Frontend**: HTML, CSS, JavaScript
- **Visualization**: D3.js, Chart.js
- **Icons**: Font Awesome 6.5.1
- **Data**: Pandas for processing CSV datasets

## Local Development

### Prerequisites

- Python 3.8+
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/natyavidhan/uidai-hackathon
cd uidai-hackathon
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the Flask app:
```bash
cd interface
python main.py
```

4. Open your browser at `http://127.0.0.1:5000`

## Deployment to Vercel

The application supports two modes:

1. **Local Mode**: Loads CSV datasets directly (for development)
2. **Production Mode**: Uses pre-computed JSON files (for Vercel deployment)

### Step 1: Pre-compute Data

Before deploying to Vercel, you need to pre-compute the aggregates since Vercel has size limits on serverless functions:

```bash
cd interface
python precompute_data.py
```

This will create JSON files in `interface/static/data/`:
- `district_aggregates.json` - Pre-computed metrics for all districts
- `time_series.json` - Monthly time series data
- `summary_stats.json` - Summary statistics

### Step 2: Deploy to Vercel

#### Option A: Using Vercel CLI

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Login to Vercel:
```bash
vercel login
```

3. Deploy:
```bash
vercel
```

4. Follow the prompts and deploy to production:
```bash
vercel --prod
```

#### Option B: Using Vercel Dashboard

1. Push your code to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Click "Import Project"
4. Select your GitHub repository
5. Vercel will automatically detect the configuration from `vercel.json`
6. Click "Deploy"

### Important Notes for Deployment

- The `datasets/` folder is excluded via `.vercelignore` (too large for Vercel)
- The app automatically detects if it's running on Vercel and uses pre-computed JSON files
- Make sure to run `precompute_data.py` before deployment
- Commit the generated `interface/static/data/*.json` files to your repository

## API Endpoints

- `GET /` - Main dashboard page
- `GET /api/geojson` - Get India district GeoJSON
- `GET /api/districts/all` - Get all district aggregates
- `GET /api/district/<name>` - Get specific district data with analytics
- `GET /api/stats/summary` - Get summary statistics

## Key Metrics

### Derived Metrics
- **Identity Volatility**: Ratio of demographic updates to enrolments
- **Adult Bio Compliance**: Adult biometric updates relative to adult enrolments
- **Child Bio Compliance**: Child biometric updates relative to child enrolments
- **Lifecycle Integrity**: Overall data maintenance health score
- **Maintenance Imbalance**: Imbalance between demographic and biometric updates

### District Typologies
- Adult-Heavy
- Child-Heavy
- High-Churn
- Well-Maintained
- Standard
- No Data

## Troubleshooting

### Vercel Deployment Issues

1. **Function size too large**: Make sure you ran `precompute_data.py` and the `datasets/` folder is excluded
2. **Import errors**: Check that all dependencies are in `requirements.txt`
3. **Static files not loading**: Verify the routes in `vercel.json`

### Local Development Issues

1. **Port already in use**: Change the port in `main.py` or kill the existing process
2. **Memory errors**: The datasets are large (~5M records total). Ensure you have sufficient RAM

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
