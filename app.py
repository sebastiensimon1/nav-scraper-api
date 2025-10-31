from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import pandas as pd
from io import StringIO
import os

app = Flask(__name__)
CORS(app)

def get_navs_from_csv(tickers):
    """Fetch NAV for any tickers from Roundhill CSV file"""
    csv_url = "https://www.roundhillinvestments.com/assets/data/FilepointRoundhill.40RU.RU_DailyNAV.csv"
    
    headers = {
        "Host": "www.roundhillinvestments.com",
        "Sec-Ch-Ua": '"Chromium";v="141", "Not?A_Brand";v="8"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "Accept": "text/csv,text/plain,*/*",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.roundhillinvestments.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }
    
    try:
        print(f"📡 Fetching NAV CSV from: {csv_url}")
        
        response = requests.get(csv_url, headers=headers, verify=False, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            return {ticker: None for ticker in tickers}
        
        print(f"✅ CSV downloaded successfully ({len(response.text)} bytes)")
        
        # Parse CSV
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data)
        
        print(f"📊 CSV has {len(df)} rows")
        
        # Get list of all available tickers in the CSV
        available_tickers = df['Fund Ticker'].str.upper().unique().tolist()
        print(f"📋 Available tickers in CSV: {', '.join(available_tickers)}")
        
        nav_data = {}
        
        for ticker in tickers:
            ticker_upper = ticker.upper()
            
            # Find the row where 'Fund Ticker' matches our ticker
            matching_rows = df[df['Fund Ticker'].str.upper() == ticker_upper]
            
            if not matching_rows.empty:
                # Get the NAV value from the first matching row
                nav_value = matching_rows['NAV'].iloc[0]
                
                # Handle potential string values and convert to float
                if pd.notna(nav_value):
                    try:
                        nav_float = float(nav_value)
                        nav_data[ticker_upper] = nav_float
                        print(f"✅ {ticker_upper}: ${nav_float:.2f}")
                    except (ValueError, TypeError):
                        nav_data[ticker_upper] = None
                        print(f"❌ {ticker_upper}: Invalid NAV value '{nav_value}'")
                else:
                    nav_data[ticker_upper] = None
                    print(f"❌ {ticker_upper}: NAV is null")
            else:
                nav_data[ticker_upper] = None
                print(f"❌ {ticker_upper}: Not found in CSV")
        
        return nav_data, available_tickers
        
    except Exception as e:
        print(f"❌ Error fetching CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        return {ticker: None for ticker in tickers}, []

@app.route('/', methods=['GET'])
def home():
    """Health check endpoint"""
    # Get available tickers dynamically
    try:
        _, available_tickers = get_navs_from_csv([])
        supported_tickers = available_tickers if available_tickers else []
    except:
        supported_tickers = []
    
    return jsonify({
        'status': 'online',
        'service': 'NAV Scraper API',
        'version': '3.0.0',
        'method': 'CSV',
        'note': 'Enter any ticker to check if NAV data is available',
        'available_tickers': supported_tickers if supported_tickers else 'Could not fetch at this time'
    })

@app.route('/health', methods=['GET'])
def health():
    """Additional health check endpoint for Railway"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/get-nav', methods=['POST'])
def get_nav():
    """Main endpoint to fetch NAV data for any tickers
    
    Accepts multiple formats:
    - {"tickers": ["TSLW", "HOOW"]} - Array of tickers
    - {"ticker": "TSLW"} - Single ticker string
    - {"tickers": "TSLW,HOOW,MSTY"} - Comma-separated string
    """
    try:
        data = request.json
        
        # Handle different input formats
        tickers = None
        
        # Format 1: Array of tickers {"tickers": ["TSLW", "HOOW"]}
        if 'tickers' in data:
            if isinstance(data['tickers'], list):
                tickers = data['tickers']
            # Format 2: Comma-separated string {"tickers": "TSLW,HOOW,MSTY"}
            elif isinstance(data['tickers'], str):
                tickers = [t.strip().upper() for t in data['tickers'].split(',') if t.strip()]
            else:
                return jsonify({
                    'error': 'Invalid format',
                    'message': 'tickers must be an array or comma-separated string'
                }), 400
        
        # Format 3: Single ticker {"ticker": "TSLW"}
        elif 'ticker' in data:
            if isinstance(data['ticker'], str):
                tickers = [data['ticker'].strip().upper()]
            else:
                return jsonify({
                    'error': 'Invalid format',
                    'message': 'ticker must be a string'
                }), 400
        
        else:
            return jsonify({
                'error': 'Missing parameter',
                'message': 'Request must include either "ticker" or "tickers"',
                'examples': [
                    {'tickers': ['TSLW', 'HOOW']},
                    {'ticker': 'TSLW'},
                    {'tickers': 'TSLW,HOOW,MSTY'}
                ]
            }), 400
        
        if not tickers:
            return jsonify({
                'error': 'Empty tickers',
                'message': 'No tickers provided'
            }), 400
        
        print(f"\n=== NAV DATA FETCHING START ===")
        print(f"Requested tickers: {tickers}")
        
        # Fetch NAV data for ALL requested tickers (no filtering)
        nav_data, available_tickers = get_navs_from_csv(tickers)
        
        print(f"\n=== NAV DATA FETCHING COMPLETE ===")
        print(f"Results: {nav_data}")
        
        # Build response
        response_data = {
            'navData': nav_data
        }
        
        # Check if any tickers were not found
        not_found = [t.upper() for t in tickers if nav_data.get(t.upper()) is None]
        
        if not_found:
            response_data['message'] = f"Some tickers not found: {', '.join(not_found)}"
            response_data['available_tickers'] = available_tickers
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error in get-nav endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting Flask server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
