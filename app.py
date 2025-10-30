from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import pandas as pd
from io import StringIO
import os

app = Flask(__name__)
CORS(app)

ROUNDHILL_ETFS = ['TSLW', 'HOOW', 'PLTW', 'MSTY', 'NVDW', 'NVDY', 'YBTC', 'CONY', 'NVDL']

def get_navs_from_csv(tickers):
    """Fetch NAV for Roundhill ETFs from single CSV file"""
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
        
        nav_data = {}
        
        for ticker in tickers:
            # Find the row where 'Fund Ticker' matches our ticker
            matching_rows = df[df['Fund Ticker'].str.upper() == ticker.upper()]
            
            if not matching_rows.empty:
                # Get the NAV value from the first matching row
                nav_value = matching_rows['NAV'].iloc[0]
                
                # Handle potential string values and convert to float
                if pd.notna(nav_value):
                    try:
                        nav_float = float(nav_value)
                        nav_data[ticker] = nav_float
                        print(f"✅ {ticker}: ${nav_float:.2f}")
                    except (ValueError, TypeError):
                        nav_data[ticker] = None
                        print(f"❌ {ticker}: Invalid NAV value '{nav_value}'")
                else:
                    nav_data[ticker] = None
                    print(f"❌ {ticker}: NAV is null")
            else:
                nav_data[ticker] = None
                print(f"❌ {ticker}: Not found in CSV")
        
        return nav_data
        
    except Exception as e:
        print(f"❌ Error fetching CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        return {ticker: None for ticker in tickers}

@app.route('/', methods=['GET'])
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'service': 'Roundhill NAV Scraper API',
        'version': '2.0.0',
        'method': 'CSV',
        'supported_tickers': ROUNDHILL_ETFS
    })

@app.route('/health', methods=['GET'])
def health():
    """Additional health check endpoint for Railway"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/get-nav', methods=['POST'])
def get_nav():
    """Main endpoint to fetch NAV data for multiple tickers"""
    try:
        data = request.json
        tickers = data.get('tickers', [])
        
        if not isinstance(tickers, list):
            return jsonify({'error': 'Tickers must be an array'}), 400
        
        print(f"\n=== NAV DATA FETCHING START ===")
        print(f"Requested tickers: {tickers}")
        
        # Filter to only Roundhill ETFs
        roundhill_tickers = [t for t in tickers if t.upper() in ROUNDHILL_ETFS]
        
        if not roundhill_tickers:
            print("ℹ️ No Roundhill ETFs requested")
            return jsonify({'navData': {}})
        
        print(f"📊 Processing {len(roundhill_tickers)} Roundhill ETFs: {', '.join(roundhill_tickers)}")
        
        # Fetch all NAVs from CSV (much faster than individual requests!)
        nav_data = get_navs_from_csv(roundhill_tickers)
        
        print(f"\n=== NAV DATA FETCHING COMPLETE ===")
        print(f"Results: {nav_data}")
        
        return jsonify({'navData': nav_data})
        
    except Exception as e:
        print(f"❌ Error in get-nav endpoint: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting Flask server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
