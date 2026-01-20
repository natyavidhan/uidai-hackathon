from flask import Flask, render_template, request, jsonify
import json
import os
import pandas as pd
import glob
from functools import lru_cache
import requests
from io import StringIO

# Configure Flask with explicit static paths for Vercel
app = Flask(__name__,
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')

# GitHub raw URL base path
GITHUB_BASE_URL = "https://raw.githubusercontent.com/natyavidhan/uidai-hackathon/master/datasets"

# For local development, fallback to local files
DATASETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets')
USE_REMOTE = os.environ.get('VERCEL', False) or os.environ.get('USE_REMOTE', 'false').lower() == 'true'

def load_csv_from_url(url):
    """Load CSV from URL"""
    try:
        print(f"Fetching {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text))
    except Exception as e:
        print(f"Error loading {url}: {e}")
        return pd.DataFrame()

def load_all_csv_files_remote(folder_name, file_list):
    """Load and concatenate CSV files from GitHub raw URLs"""
    dfs = []
    for filename in file_list:
        url = f"{GITHUB_BASE_URL}/{folder_name}/{filename}"
        df = load_csv_from_url(url)
        if not df.empty:
            dfs.append(df)
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

def load_all_csv_files_local(folder_path):
    """Load and concatenate all CSV files from a local folder"""
    csv_files = glob.glob(os.path.join(folder_path, '*.csv'))
    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
        except Exception as e:
            print(f"Error loading {f}: {e}")
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

@lru_cache(maxsize=1)
def load_datasets():
    """Load all datasets from GitHub or local files"""
    print(f"Loading datasets... (USE_REMOTE={USE_REMOTE})")
    
    if USE_REMOTE:
        # Load from GitHub raw URLs
        enrolment_files = [
            'api_data_aadhar_enrolment_0_500000.csv',
            'api_data_aadhar_enrolment_500000_1000000.csv',
            'api_data_aadhar_enrolment_1000000_1006029.csv'
        ]
        demographic_files = [
            'api_data_aadhar_demographic_0_500000.csv',
            'api_data_aadhar_demographic_500000_1000000.csv',
            'api_data_aadhar_demographic_1000000_1500000.csv',
            'api_data_aadhar_demographic_1500000_2000000.csv',
            'api_data_aadhar_demographic_2000000_2071700.csv'
        ]
        biometric_files = [
            'api_data_aadhar_biometric_0_500000.csv',
            'api_data_aadhar_biometric_500000_1000000.csv',
            'api_data_aadhar_biometric_1000000_1500000.csv',
            'api_data_aadhar_biometric_1500000_1861108.csv'
        ]
        
        enrolment_df = load_all_csv_files_remote('api_data_aadhar_enrolment', enrolment_files)
        demographic_df = load_all_csv_files_remote('api_data_aadhar_demographic', demographic_files)
        biometric_df = load_all_csv_files_remote('api_data_aadhar_biometric', biometric_files)
    else:
        # Load from local files
        enrolment_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_enrolment')
        demographic_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_demographic')
        biometric_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_biometric')
        
        enrolment_df = load_all_csv_files_local(enrolment_path)
        demographic_df = load_all_csv_files_local(demographic_path)
        biometric_df = load_all_csv_files_local(biometric_path)
    
    print(f"Loaded {len(enrolment_df)} enrolment records")
    print(f"Loaded {len(demographic_df)} demographic records")
    print(f"Loaded {len(biometric_df)} biometric records")
    
    return {
        'enrolment': enrolment_df,
        'demographic': demographic_df,
        'biometric': biometric_df
    }

@lru_cache(maxsize=1)
def compute_district_aggregates():
    """Compute district-level aggregated metrics"""
    datasets = load_datasets()
    
    enrolment_df = datasets['enrolment']
    demographic_df = datasets['demographic']
    biometric_df = datasets['biometric']
    
    # Aggregate enrolment data by district
    enrolment_agg = enrolment_df.groupby(['state', 'district']).agg({
        'age_0_5': 'sum',
        'age_5_17': 'sum',
        'age_18_greater': 'sum'
    }).reset_index()
    enrolment_agg.columns = ['state', 'district', 'enrol_0_5', 'enrol_5_17', 'enrol_18_plus']
    enrolment_agg['total_enrolments'] = enrolment_agg['enrol_0_5'] + enrolment_agg['enrol_5_17'] + enrolment_agg['enrol_18_plus']
    
    # Aggregate demographic data by district
    demographic_agg = demographic_df.groupby(['state', 'district']).agg({
        'demo_age_5_17': 'sum',
        'demo_age_17_': 'sum'
    }).reset_index()
    demographic_agg.columns = ['state', 'district', 'demo_5_17', 'demo_18_plus']
    demographic_agg['total_demo_updates'] = demographic_agg['demo_5_17'] + demographic_agg['demo_18_plus']
    
    # Aggregate biometric data by district
    biometric_agg = biometric_df.groupby(['state', 'district']).agg({
        'bio_age_5_17': 'sum',
        'bio_age_17_': 'sum'
    }).reset_index()
    biometric_agg.columns = ['state', 'district', 'bio_5_17', 'bio_18_plus']
    biometric_agg['total_bio_updates'] = biometric_agg['bio_5_17'] + biometric_agg['bio_18_plus']
    
    # Merge all datasets
    merged = enrolment_agg.merge(demographic_agg, on=['state', 'district'], how='outer')
    merged = merged.merge(biometric_agg, on=['state', 'district'], how='outer')
    merged = merged.fillna(0)
    
    # Compute derived metrics
    merged['adult_enrolment_share'] = (merged['enrol_18_plus'] / merged['total_enrolments'].replace(0, 1)) * 100
    merged['child_enrolment_share'] = ((merged['enrol_0_5'] + merged['enrol_5_17']) / merged['total_enrolments'].replace(0, 1)) * 100
    
    # Identity volatility: demographic updates / enrolments
    merged['identity_volatility'] = merged['total_demo_updates'] / merged['total_enrolments'].replace(0, 1)
    
    # Adult biometric compliance: adult bio updates relative to adult enrolments
    merged['adult_bio_compliance'] = (merged['bio_18_plus'] / merged['enrol_18_plus'].replace(0, 1)) * 100
    
    # Child biometric compliance
    merged['child_bio_compliance'] = (merged['bio_5_17'] / (merged['enrol_5_17'] + merged['enrol_0_5']).replace(0, 1)) * 100
    
    # Lifecycle integrity ratio: bio updates relative to demo updates
    merged['lifecycle_integrity'] = merged['total_bio_updates'] / merged['total_demo_updates'].replace(0, 1)
    
    # Maintenance imbalance: high demo updates + low bio updates
    merged['maintenance_imbalance'] = (merged['total_demo_updates'] - merged['total_bio_updates']) / merged['total_demo_updates'].replace(0, 1)
    
    # Classify district typology
    def classify_district(row):
        volatility = row['identity_volatility']
        enrolment = row['total_enrolments']
        bio_compliance = row['adult_bio_compliance']
        
        median_enrolment = merged['total_enrolments'].median()
        median_volatility = merged['identity_volatility'].median()
        
        if volatility < median_volatility and enrolment < median_enrolment:
            return 'Stable & Saturated'
        elif volatility >= median_volatility:
            return 'Volatile'
        elif enrolment >= median_enrolment and volatility < median_volatility:
            return 'Growth-focused'
        elif bio_compliance < 50:
            return 'Under-maintained'
        else:
            return 'Balanced'
    
    merged['district_typology'] = merged.apply(classify_district, axis=1)
    
    # Convert to dictionary indexed by district name (lowercase for matching)
    result = {}
    for _, row in merged.iterrows():
        district_key = row['district'].lower().strip()
        result[district_key] = row.to_dict()
    
    return result

@lru_cache(maxsize=1)
def compute_time_series_data():
    """Compute time-series data for each district"""
    datasets = load_datasets()
    
    enrolment_df = datasets['enrolment'].copy()
    demographic_df = datasets['demographic'].copy()
    biometric_df = datasets['biometric'].copy()
    
    # Convert date columns
    enrolment_df['date'] = pd.to_datetime(enrolment_df['date'], format='%d-%m-%Y', errors='coerce')
    demographic_df['date'] = pd.to_datetime(demographic_df['date'], format='%d-%m-%Y', errors='coerce')
    biometric_df['date'] = pd.to_datetime(biometric_df['date'], format='%d-%m-%Y', errors='coerce')
    
    # Add month column
    enrolment_df['month'] = enrolment_df['date'].dt.to_period('M').astype(str)
    demographic_df['month'] = demographic_df['date'].dt.to_period('M').astype(str)
    biometric_df['month'] = biometric_df['date'].dt.to_period('M').astype(str)
    
    # Aggregate by district and month for enrolment
    enrol_ts = enrolment_df.groupby(['district', 'month']).agg({
        'age_0_5': 'sum',
        'age_5_17': 'sum', 
        'age_18_greater': 'sum'
    }).reset_index()
    enrol_ts['total_enrolments'] = enrol_ts['age_0_5'] + enrol_ts['age_5_17'] + enrol_ts['age_18_greater']
    
    # Aggregate by district and month for demographic
    demo_ts = demographic_df.groupby(['district', 'month']).agg({
        'demo_age_5_17': 'sum',
        'demo_age_17_': 'sum'
    }).reset_index()
    demo_ts['total_demo'] = demo_ts['demo_age_5_17'] + demo_ts['demo_age_17_']
    
    # Aggregate by district and month for biometric
    bio_ts = biometric_df.groupby(['district', 'month']).agg({
        'bio_age_5_17': 'sum',
        'bio_age_17_': 'sum'
    }).reset_index()
    bio_ts['total_bio'] = bio_ts['bio_age_5_17'] + bio_ts['bio_age_17_']
    
    # Build result dictionary
    result = {}
    for district in enrol_ts['district'].unique():
        district_key = district.lower().strip()
        
        enrol_data = enrol_ts[enrol_ts['district'] == district].sort_values('month')
        demo_data = demo_ts[demo_ts['district'] == district].sort_values('month')
        bio_data = bio_ts[bio_ts['district'] == district].sort_values('month')
        
        result[district_key] = {
            'enrolment': {
                'months': enrol_data['month'].tolist(),
                'total': enrol_data['total_enrolments'].tolist(),
                'children': (enrol_data['age_0_5'] + enrol_data['age_5_17']).tolist(),
                'adults': enrol_data['age_18_greater'].tolist()
            },
            'demographic': {
                'months': demo_data['month'].tolist(),
                'total': demo_data['total_demo'].tolist(),
                'children': demo_data['demo_age_5_17'].tolist(),
                'adults': demo_data['demo_age_17_'].tolist()
            },
            'biometric': {
                'months': bio_data['month'].tolist(),
                'total': bio_data['total_bio'].tolist(),
                'children': bio_data['bio_age_5_17'].tolist(),
                'adults': bio_data['bio_age_17_'].tolist()
            }
        }
    
    return result

# Route for the main page
@app.route('/')
def index():
    return render_template('index.html')

# Route to serve geojson data
@app.route('/api/geojson')
def get_geojson():
    try:
        geojson_path = os.path.join(app.static_folder, 'india_district.geojson')
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        return jsonify(geojson_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to get all district aggregates (for initial load)
@app.route('/api/districts/all')
def get_all_districts():
    try:
        aggregates = compute_district_aggregates()
        return jsonify(aggregates)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to get district data with full analytics
@app.route('/api/district/<district_name>')
def get_district_data(district_name):
    try:
        aggregates = compute_district_aggregates()
        time_series = compute_time_series_data()
        
        district_key = district_name.lower().strip()
        
        if district_key in aggregates:
            data = aggregates[district_key]
            ts_data = time_series.get(district_key, {})
            
            response = {
                'district': data['district'],
                'state': data['state'],
                
                # Enrolment metrics
                'total_enrolments': int(data['total_enrolments']),
                'enrol_0_5': int(data['enrol_0_5']),
                'enrol_5_17': int(data['enrol_5_17']),
                'enrol_18_plus': int(data['enrol_18_plus']),
                'adult_enrolment_share': round(data['adult_enrolment_share'], 2),
                'child_enrolment_share': round(data['child_enrolment_share'], 2),
                
                # Demographic metrics
                'total_demo_updates': int(data['total_demo_updates']),
                'demo_5_17': int(data['demo_5_17']),
                'demo_18_plus': int(data['demo_18_plus']),
                
                # Biometric metrics
                'total_bio_updates': int(data['total_bio_updates']),
                'bio_5_17': int(data['bio_5_17']),
                'bio_18_plus': int(data['bio_18_plus']),
                
                # Derived metrics
                'identity_volatility': round(data['identity_volatility'], 4),
                'adult_bio_compliance': round(min(data['adult_bio_compliance'], 100), 2),
                'child_bio_compliance': round(min(data['child_bio_compliance'], 100), 2),
                'lifecycle_integrity': round(data['lifecycle_integrity'], 4),
                'maintenance_imbalance': round(data['maintenance_imbalance'], 4),
                'district_typology': data['district_typology'],
                
                # Time series data
                'time_series': ts_data
            }
            return jsonify(response)
        else:
            # Return empty data for unknown districts
            return jsonify({
                'district': district_name,
                'state': 'Unknown',
                'total_enrolments': 0,
                'enrol_0_5': 0,
                'enrol_5_17': 0,
                'enrol_18_plus': 0,
                'adult_enrolment_share': 0,
                'child_enrolment_share': 0,
                'total_demo_updates': 0,
                'demo_5_17': 0,
                'demo_18_plus': 0,
                'total_bio_updates': 0,
                'bio_5_17': 0,
                'bio_18_plus': 0,
                'identity_volatility': 0,
                'adult_bio_compliance': 0,
                'child_bio_compliance': 0,
                'lifecycle_integrity': 0,
                'maintenance_imbalance': 0,
                'district_typology': 'Unknown',
                'time_series': {}
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Route to get summary statistics
@app.route('/api/stats/summary')
def get_summary_stats():
    try:
        aggregates = compute_district_aggregates()
        
        df = pd.DataFrame(aggregates.values())
        
        summary = {
            'total_districts': len(df),
            'total_enrolments': int(df['total_enrolments'].sum()),
            'total_demo_updates': int(df['total_demo_updates'].sum()),
            'total_bio_updates': int(df['total_bio_updates'].sum()),
            'avg_identity_volatility': round(df['identity_volatility'].mean(), 4),
            'avg_adult_bio_compliance': round(df['adult_bio_compliance'].mean(), 2),
            'typology_distribution': df['district_typology'].value_counts().to_dict()
        }
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Pre-load datasets on startup
    print("Starting server and loading datasets...")
    load_datasets()
    compute_district_aggregates()
    compute_time_series_data()
    print("Datasets loaded. Starting Flask server...")
    app.run(debug=True, port=5000)

# Vercel serverless handler
# This is required for Vercel deployment
app = app