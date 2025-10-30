# Roundhill NAV Scraper API

Flask API to fetch NAV data for Roundhill ETFs.

## Supported ETFs
TSLW, HOOW, PLTW, MSTY, NVDW, NVDY, YBTC, CONY, NVDL

## Endpoints

### GET /
Health check

### POST /get-nav
Fetch NAV data

**Request:**
```json
{
  "tickers": ["TSLW", "HOOW", "MSTY"]
}
```

**Response:**
```json
{
  "navData": {
    "TSLW": 45.72,
    "HOOW": 32.18,
    "MSTY": 28.45
  }
}
```
