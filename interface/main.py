from flask import Flask, render_template, request, jsonify
import json
import os
import glob
from functools import lru_cache

app = Flask(__name__)

# Dataset paths
DATASETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets')
PRECOMPUTED_DATA_PATH = os.path.join(os.path.dirname(__file__), 'static', 'data')

# Check if running in Vercel (serverless) environment or with pre-computed data
USE_PRECOMPUTED = os.environ.get('VERCEL') or os.path.exists(os.path.join(PRECOMPUTED_DATA_PATH, 'district_aggregates.json'))

if not USE_PRECOMPUTED:
    import pandas as pd

def load_all_csv_files(folder_path):
    """Load and concatenate all CSV files from a folder"""
    if USE_PRECOMPUTED:
        return None
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
def load_precomputed_aggregates():
    """Load pre-computed aggregates from JSON file"""
    aggregates_file = os.path.join(PRECOMPUTED_DATA_PATH, 'district_aggregates.json')
    with open(aggregates_file, 'r') as f:
        return json.load(f)

@lru_cache(maxsize=1)
def load_precomputed_time_series():
    """Load pre-computed time series from JSON file"""
    time_series_file = os.path.join(PRECOMPUTED_DATA_PATH, 'time_series.json')
    if os.path.exists(time_series_file):
        with open(time_series_file, 'r') as f:
            return json.load(f)
    return {}

@lru_cache(maxsize=1)
def load_precomputed_summary():
    """Load pre-computed summary stats from JSON file"""
    summary_file = os.path.join(PRECOMPUTED_DATA_PATH, 'summary_stats.json')
    if os.path.exists(summary_file):
        with open(summary_file, 'r') as f:
            return json.load(f)
    return {}

@lru_cache(maxsize=1)
def load_datasets():
    """Load all datasets and return as a dictionary"""
    if USE_PRECOMPUTED:
        return None
    
    print("Loading datasets...")
    
    # Load enrolment data
    enrolment_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_enrolment')
    enrolment_df = load_all_csv_files(enrolment_path)
    
    # Load demographic data
    demographic_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_demographic')
    demographic_df = load_all_csv_files(demographic_path)
    
    # Load biometric data
    biometric_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_biometric')
    biometric_df = load_all_csv_files(biometric_path)
    
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
    if USE_PRECOMPUTED:
        return load_precomputed_aggregates()
    
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

def get_time_series_for_district(district_key):
    """Get time series data for a specific district"""
    if USE_PRECOMPUTED:
        all_ts = load_precomputed_time_series()
        # Try different key formats
        for key in [district_key, district_key.lower().strip()]:
            if key in all_ts:
                return all_ts[key]
        # Try matching by district name in key
        for k, v in all_ts.items():
            if '|' in k and k.split('|')[1].lower().strip() == district_key.lower().strip():
                return v
        return {}
    else:
        all_ts = compute_time_series_data()
        return all_ts.get(district_key.lower().strip(), {})

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
        
        district_key = district_name.lower().strip()
        
        # For precomputed data, try to match with state|district key format
        matching_data = None
        if USE_PRECOMPUTED:
            for key, val in aggregates.items():
                if '|' in key and key.split('|')[1].lower().strip() == district_key:
                    matching_data = val
                    break
                elif key.lower().strip() == district_key:
                    matching_data = val
                    break
        else:
            matching_data = aggregates.get(district_key)
        
        if matching_data:
            data = matching_data
            ts_data = get_time_series_for_district(district_key)
            
            response = {
                'district': data.get('district', district_name),
                'state': data.get('state', 'Unknown'),
                
                # Enrolment metrics
                'total_enrolments': int(data.get('total_enrolments', 0)),
                'enrol_0_5': int(data.get('enrol_0_5', 0)),
                'enrol_5_17': int(data.get('enrol_5_17', 0)),
                'enrol_18_plus': int(data.get('enrol_18_plus', 0)),
                'adult_enrolment_share': round(data.get('adult_enrolment_share', 0), 2),
                'child_enrolment_share': round(data.get('child_enrolment_share', 0), 2),
                
                # Demographic metrics
                'total_demo_updates': int(data.get('total_demo_updates', 0)),
                'demo_5_17': int(data.get('demo_5_17', 0)),
                'demo_18_plus': int(data.get('demo_18_plus', 0)),
                
                # Biometric metrics
                'total_bio_updates': int(data.get('total_bio_updates', 0)),
                'bio_5_17': int(data.get('bio_5_17', 0)),
                'bio_18_plus': int(data.get('bio_18_plus', 0)),
                
                # Derived metrics
                'identity_volatility': round(data.get('identity_volatility', 0), 4),
                'adult_bio_compliance': round(min(data.get('adult_bio_compliance', 0), 100), 2),
                'child_bio_compliance': round(min(data.get('child_bio_compliance', 0), 100), 2),
                'lifecycle_integrity': round(data.get('lifecycle_integrity', 0), 4),
                'maintenance_imbalance': round(data.get('maintenance_imbalance', 0), 4),
                'district_typology': data.get('district_typology', 'Unknown'),
                
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
        if USE_PRECOMPUTED:
            return jsonify(load_precomputed_summary())
        
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

# Vercel serverless handler
app_handler = app

if __name__ == '__main__':
    # Pre-load datasets on startup for local development
    if not USE_PRECOMPUTED:
        print("Starting server and loading datasets...")
        load_datasets()
        compute_district_aggregates()
        compute_time_series_data()
        print("Datasets loaded. Starting Flask server...")
    else:
        print("Starting server with pre-computed data...")
    app.run(debug=True, port=5000)