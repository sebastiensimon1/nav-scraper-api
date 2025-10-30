from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import re
import time
import random
import os

app = Flask(__name__)
CORS(app)

ROUNDHILL_ETFS = ['TSLW', 'HOOW', 'PLTW', 'MSTY', 'NVDW', 'NVDY', 'YBTC', 'CONY', 'NVDL']

def extract_nav_from_html(html, ticker):
    """Extract NAV value from HTML using multiple patterns"""
    # Primary pattern: <td id="NetAssetValue">$45.72</td>
    primary_match = re.search(r'<td\s+id=["\']NetAssetValue["\'][^>]*>\s*\$?([\d,]+\.?\d*)', html, re.IGNORECASE)
    if primary_match:
        nav_value = float(primary_match.group(1).replace(',', ''))
        if nav_value > 0:
            print(f"✅ {ticker}: ${nav_value:.2f} (primary match)")
            return nav_value
    
    # Fallback 1: Look in panel2
    panel_match = re.search(r'id=["\']panel2["\'][^>]*>([\s\S]{0,3000})', html, re.IGNORECASE)
    if panel_match:
        panel_content = panel_match.group(1)
        nav_in_panel = re.search(r'Net Asset Value[\s\S]{0,200}?\$?([\d,]+\.?\d*)', panel_content, re.IGNORECASE)
        if nav_in_panel:
            nav_value = float(nav_in_panel.group(1).replace(',', ''))
            if nav_value > 0:
                print(f"✅ {ticker}: ${nav_value:.2f} (panel2 match)")
                return nav_value
    
    # Fallback 2: Generic Net Asset Value pattern
    generic_match = re.search(r'Net Asset Value[^$]{0,100}\$?([\d,]+\.?\d*)', html, re.IGNORECASE)
    if generic_match:
        nav_value = float(generic_match.group(1).replace(',', ''))
        if nav_value > 0:
            print(f"✅ {ticker}: ${nav_value:.2f} (generic match)")
            return nav_value
    
    print(f"❌ {ticker}: NAV not found in HTML")
    return None

def get_nav_for_ticker(ticker, retry_count=0):
    """Fetch NAV for a single ticker with retry logic"""
    url = f"https://www.roundhillinvestments.com/etf/{ticker.lower()}/"
    
    headers = {
        "Host": "www.roundhillinvestments.com",
        "Sec-Ch-Ua": '"Chromium";v="141", "Not?A_Brand";v="8"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Referer": "https://www.google.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Priority": "u=0, i",
        "Connection": "keep-alive"
    }
    
    try:
        print(f"📡 Fetching {ticker} from {url} (attempt {retry_count + 1})")
        
        # Add small random delay to mimic human behavior
        time.sleep(random.uniform(0.2, 0.8))
        
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        
        if response.status_code == 200:
            html = response.text
            
            if len(html) < 1000:
                print(f"⚠️ {ticker}: Response too short ({len(html)} bytes)")
                
                # Retry with exponential backoff
                if retry_count < 2:
                    backoff = (2 ** retry_count) * 2
                    print(f"🔄 Retrying {ticker} in {backoff}s...")
                    time.sleep(backoff)
                    return get_nav_for_ticker(ticker, retry_count + 1)
                
                return None
            
            return extract_nav_from_html(html, ticker)
        else:
            print(f"❌ {ticker}: HTTP {response.status_code}")
            
            # Retry with exponential backoff
            if retry_count < 2:
                backoff = (2 ** retry_count) * 2
                print(f"🔄 Retrying {ticker} in {backoff}s...")
                time.sleep(backoff)
                return get_nav_for_ticker(ticker, retry_count + 1)
            
            return None
            
    except Exception as e:
        print(f"❌ {ticker}: {str(e)}")
        
        # Retry with exponential backoff
        if retry_count < 2:
            backoff = (2 ** retry_count) * 2 + random.uniform(0, 1)
            print(f"🔄 Retrying {ticker} after error in {backoff:.1f}s...")
            time.sleep(backoff)
            return get_nav_for_ticker(ticker, retry_count + 1)
        
        return None

@app.route('/', methods=['GET'])
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'service': 'Roundhill NAV Scraper API',
        'version': '1.0.0',
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
        
        nav_data = {}
        
        # Process tickers with delays between requests
        for i, ticker in enumerate(roundhill_tickers):
            nav_data[ticker] = get_nav_for_ticker(ticker)
            
            # Add delay between requests (except for last one)
            if i < len(roundhill_tickers) - 1:
                delay = random.uniform(1, 2)
                print(f"⏳ Waiting {delay:.1f}s before next request...")
                time.sleep(delay)
        
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
    print(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
```

---

## `requirements.txt`
```
flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
```

---

## `Procfile`
```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

---

## `runtime.txt`
```
python-3.11.6
```

---

## `.gitignore`
```
__pycache__/
*.pyc
.env
venv/
*.log
.DS_Store
