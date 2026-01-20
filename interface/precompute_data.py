"""
Pre-compute district aggregates and save as JSON for Vercel deployment.
Run this script locally before deploying to Vercel.
"""
import os
import sys
import json
import pandas as pd
import glob

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATASETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'static', 'data')

def load_all_csv_files(folder_path):
    """Load and concatenate all CSV files from a folder"""
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

def compute_and_save_aggregates():
    print("Loading datasets...")
    
    # Load enrolment data
    enrolment_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_enrolment')
    enrolment_df = load_all_csv_files(enrolment_path)
    print(f"Loaded {len(enrolment_df)} enrolment records")
    
    # Load demographic data
    demographic_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_demographic')
    demographic_df = load_all_csv_files(demographic_path)
    print(f"Loaded {len(demographic_df)} demographic records")
    
    # Load biometric data
    biometric_path = os.path.join(DATASETS_PATH, 'api_data_aadhar_biometric')
    biometric_df = load_all_csv_files(biometric_path)
    print(f"Loaded {len(biometric_df)} biometric records")
    
    print("\nComputing district aggregates...")
    
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
    merged['identity_volatility'] = merged['total_demo_updates'] / merged['total_enrolments'].replace(0, 1)
    merged['adult_bio_compliance'] = (merged['bio_18_plus'] / merged['enrol_18_plus'].replace(0, 1)) * 100
    merged['child_bio_compliance'] = (merged['bio_5_17'] / (merged['enrol_5_17'] + merged['enrol_0_5']).replace(0, 1)) * 100
    merged['lifecycle_integrity'] = (merged['total_bio_updates'] + merged['total_demo_updates']) / (merged['total_enrolments'].replace(0, 1) * 2) * 100
    merged['maintenance_imbalance'] = abs(merged['total_demo_updates'] - merged['total_bio_updates']) / (merged['total_demo_updates'] + merged['total_bio_updates']).replace(0, 1)
    
    # Classify district typology
    def classify_typology(row):
        if row['total_enrolments'] == 0:
            return 'No Data'
        if row['adult_enrolment_share'] > 70:
            return 'Adult-Heavy'
        elif row['child_enrolment_share'] > 50:
            return 'Child-Heavy'
        elif row['identity_volatility'] > 0.5:
            return 'High-Churn'
        elif row['lifecycle_integrity'] > 50:
            return 'Well-Maintained'
        else:
            return 'Standard'
    
    merged['district_typology'] = merged.apply(classify_typology, axis=1)
    
    # Convert to dictionary format
    aggregates = {}
    for _, row in merged.iterrows():
        district_key = f"{row['state']}|{row['district']}"
        aggregates[district_key] = {
            'state': row['state'],
            'district': row['district'],
            'total_enrolments': int(row['total_enrolments']),
            'enrol_0_5': int(row['enrol_0_5']),
            'enrol_5_17': int(row['enrol_5_17']),
            'enrol_18_plus': int(row['enrol_18_plus']),
            'total_demo_updates': int(row['total_demo_updates']),
            'demo_5_17': int(row['demo_5_17']),
            'demo_18_plus': int(row['demo_18_plus']),
            'total_bio_updates': int(row['total_bio_updates']),
            'bio_5_17': int(row['bio_5_17']),
            'bio_18_plus': int(row['bio_18_plus']),
            'adult_enrolment_share': round(row['adult_enrolment_share'], 2),
            'child_enrolment_share': round(row['child_enrolment_share'], 2),
            'identity_volatility': round(row['identity_volatility'], 4),
            'adult_bio_compliance': round(row['adult_bio_compliance'], 2),
            'child_bio_compliance': round(row['child_bio_compliance'], 2),
            'lifecycle_integrity': round(row['lifecycle_integrity'], 2),
            'maintenance_imbalance': round(row['maintenance_imbalance'], 4),
            'district_typology': row['district_typology']
        }
    
    print(f"Computed aggregates for {len(aggregates)} districts")
    
    # Compute time series data
    print("\nComputing time series data...")
    time_series = {}
    
    # Enrolment time series
    if 'date' in enrolment_df.columns:
        enrol_ts = enrolment_df.groupby(['state', 'district', 'date']).agg({
            'age_0_5': 'sum',
            'age_5_17': 'sum',
            'age_18_greater': 'sum'
        }).reset_index()
        
        for (state, district), group in enrol_ts.groupby(['state', 'district']):
            district_key = f"{state}|{district}"
            if district_key not in time_series:
                time_series[district_key] = {'enrolment': {'months': [], 'values': []}}
            
            sorted_group = group.sort_values('date')
            time_series[district_key]['enrolment']['months'] = sorted_group['date'].tolist()
            time_series[district_key]['enrolment']['values'] = (
                sorted_group['age_0_5'] + sorted_group['age_5_17'] + sorted_group['age_18_greater']
            ).tolist()
    
    # Demographic time series
    if 'date' in demographic_df.columns:
        demo_ts = demographic_df.groupby(['state', 'district', 'date']).agg({
            'demo_age_5_17': 'sum',
            'demo_age_17_': 'sum'
        }).reset_index()
        
        for (state, district), group in demo_ts.groupby(['state', 'district']):
            district_key = f"{state}|{district}"
            if district_key not in time_series:
                time_series[district_key] = {}
            if 'demographic' not in time_series[district_key]:
                time_series[district_key]['demographic'] = {'months': [], 'values': []}
            
            sorted_group = group.sort_values('date')
            time_series[district_key]['demographic']['months'] = sorted_group['date'].tolist()
            time_series[district_key]['demographic']['values'] = (
                sorted_group['demo_age_5_17'] + sorted_group['demo_age_17_']
            ).tolist()
    
    # Biometric time series
    if 'date' in biometric_df.columns:
        bio_ts = biometric_df.groupby(['state', 'district', 'date']).agg({
            'bio_age_5_17': 'sum',
            'bio_age_17_': 'sum'
        }).reset_index()
        
        for (state, district), group in bio_ts.groupby(['state', 'district']):
            district_key = f"{state}|{district}"
            if district_key not in time_series:
                time_series[district_key] = {}
            if 'biometric' not in time_series[district_key]:
                time_series[district_key]['biometric'] = {'months': [], 'values': []}
            
            sorted_group = group.sort_values('date')
            time_series[district_key]['biometric']['months'] = sorted_group['date'].tolist()
            time_series[district_key]['biometric']['values'] = (
                sorted_group['bio_age_5_17'] + sorted_group['bio_age_17_']
            ).tolist()
    
    # Create output directory
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    
    # Save aggregates
    aggregates_file = os.path.join(OUTPUT_PATH, 'district_aggregates.json')
    with open(aggregates_file, 'w') as f:
        json.dump(aggregates, f)
    print(f"Saved district aggregates to {aggregates_file}")
    
    # Save time series
    time_series_file = os.path.join(OUTPUT_PATH, 'time_series.json')
    with open(time_series_file, 'w') as f:
        json.dump(time_series, f)
    print(f"Saved time series data to {time_series_file}")
    
    # Compute and save summary stats
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
    
    summary_file = os.path.join(OUTPUT_PATH, 'summary_stats.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f)
    print(f"Saved summary stats to {summary_file}")
    
    print("\n✅ Pre-computation complete! Files saved to interface/static/data/")
    print("You can now deploy to Vercel without the large CSV datasets.")

if __name__ == '__main__':
    compute_and_save_aggregates()
