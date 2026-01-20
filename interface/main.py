from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

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

# Route to get district data (you can customize this with your actual data)
@app.route('/api/district/<district_name>')
def get_district_data(district_name):
    # Sample data - replace with your actual data from CSV files
    sample_data = {
        'district': district_name,
        'population': 1500000,
        'aadhar_enrolled': 1350000,
        'biometric_completed': 1200000,
        'demographic_updated': 1400000,
        'enrollment_rate': 90.0
    }
    return jsonify(sample_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)