# Price Savvy Backend

A Flask-based REST API for scraping, comparing, and tracking product prices across multiple e-commerce platforms. Built for price-savvy shoppers and small resellers.

## Features

- 🔍 **Product Search**: Search products across 9 major e-commerce sites simultaneously
- ⚖️ **Price Comparison**: Compare products with best-by metrics highlighted
- 📊 **Price Tracking**: Track price history over time
- 📝 **Data Normalization**: Unified price format and 0-5 scale ratings
- 🧹 **Deduplication**: Fuzzy matching (85% threshold) to merge near-duplicate listings
- ⚡ **Concurrent Scraping**: Fast multi-site scraping with ThreadPoolExecutor (max 5 workers)
- 🛡️ **Rate Limiting**: Polite scraping with per-IP rate limits (10 req/min)
- 📦 **Caching**: In-memory TTL cache (5 minutes) for recent queries
- 🗄️ **SQLite Storage**: Persistent product and price history storage
- 🌐 **Selenium Support**: JavaScript-rendered website scraping
- 🖥️ **Web Dashboard**: Simple frontend for testing and monitoring
- 📜 **Live Logs**: Real-time scraping activity logs

## Supported E-Commerce Sites

| Site         | Domain       | Scraper Type | Status       |
| ------------ | ------------ | ------------ | ------------ |
| Amazon India | amazon.in    | Requests     | ✅ Working   |
| Flipkart     | flipkart.com | Requests     | ✅ Working   |
| Snapdeal     | snapdeal.com | Requests     | ✅ Working   |
| Myntra       | myntra.com   | Selenium     | ✅ Working   |
| Croma        | croma.com    | Selenium     | ✅ Working   |
| Ajio         | ajio.com     | Selenium     | ⚠️ Blocked\* |
| TataCliq     | tatacliq.com | Selenium     | ⚠️ Blocked\* |
| JioMart      | jiomart.com  | Selenium     | ⚠️ Blocked\* |
| Meesho       | meesho.com   | Selenium     | ⚠️ Blocked\* |

> \*These sites have advanced bot detection. May require residential proxies to work reliably.

## Project Structure

```
price-savvy-backend/
├── app/
│   ├── __init__.py              # Flask app factory with CORS
│   ├── config.py                # Configuration settings
│   ├── database.py              # SQLite database handler
│   ├── api/
│   │   ├── __init__.py          # API blueprint
│   │   └── routes.py            # API endpoints (13+ routes)
│   ├── scrapers/
│   │   ├── __init__.py          # Scraper registry
│   │   ├── base_scraper.py      # Abstract base scraper
│   │   ├── selenium_driver.py   # WebDriver manager with anti-detection
│   │   ├── selenium_scraper.py  # Base class for Selenium scrapers
│   │   ├── amazon_scraper.py    # Amazon scraper (Requests)
│   │   ├── flipkart_scraper.py  # Flipkart scraper (Requests)
│   │   ├── snapdeal_scraper.py  # Snapdeal scraper (Requests)
│   │   ├── myntra_scraper.py    # Myntra scraper (Selenium)
│   │   ├── croma_scraper.py     # Croma scraper (Selenium)
│   │   ├── ajio_scraper.py      # Ajio scraper (Selenium)
│   │   ├── tatacliq_scraper.py  # TataCliq scraper (Selenium)
│   │   ├── jiomart_scraper.py   # JioMart scraper (Selenium)
│   │   └── meesho_scraper.py    # Meesho scraper (Selenium)
│   ├── services/
│   │   ├── __init__.py
│   │   └── scraper_service.py   # Concurrent scraping logic
│   ├── models/
│   │   ├── __init__.py
│   │   ├── product.py           # Product model
│   │   └── price_history.py     # Price history model
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cache.py             # TTL cache implementation
│   │   ├── rate_limiter.py      # Rate limiting
│   │   ├── normalizer.py        # Data normalization & deduplication
│   │   ├── validators.py        # Input validation
│   │   └── helpers.py           # Helper functions
│   └── errors/
│       └── __init__.py          # Error handlers
├── frontend/
│   └── index.html               # Web dashboard (single page app)
├── scripts/
│   ├── init_db.py               # Database initialization
│   └── test_db.py               # Database testing
├── main.py                      # Application entry point
├── pyproject.toml               # Project dependencies (uv/pip)
├── uv.lock                      # Locked dependencies
└── README.md                    # This file
```

## Requirements

- Python 3.10+
- Chrome/Chromium browser (for Selenium-based scrapers)
- uv package manager (recommended) or pip

## Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/ManishG04/price-savvy-backend.git
cd price-savvy-backend

# Install dependencies with uv
uv sync

# For Selenium support (optional but recommended)
uv add selenium webdriver-manager
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/ManishG04/price-savvy-backend.git
cd price-savvy-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# For Selenium support (optional but recommended)
pip install selenium webdriver-manager
```

## Running the Application

### Start the Server

```bash
# Using uv
uv run python main.py

# Or directly (if venv activated)
python main.py
```

The server will start at `http://localhost:5000`

### Access Points

| URL                               | Description                  |
| --------------------------------- | ---------------------------- |
| http://localhost:5000             | API root with endpoints info |
| http://localhost:5000/dashboard   | Web Dashboard (UI)           |
| http://localhost:5000/api/v1/docs | API Documentation            |
| http://localhost:5000/health      | Health check                 |

## API Endpoints

### Health & Info

| Endpoint  | Method | Description                             |
| --------- | ------ | --------------------------------------- |
| `/health` | GET    | Health check with service status        |
| `/`       | GET    | API information and available endpoints |

### Product Search (Primary Endpoints)

| Endpoint                     | Method | Description                      |
| ---------------------------- | ------ | -------------------------------- |
| `/api/v1/search`             | GET    | Search products across all sites |
| `/api/v1/compare`            | GET    | Compare products by IDs          |
| `/api/v1/products/{id}`      | GET    | Get product details by ID        |
| `/api/v1/products?url={url}` | GET    | Get product by URL               |

### Additional Endpoints

| Endpoint                       | Method | Description                       |
| ------------------------------ | ------ | --------------------------------- |
| `/api/v1/products/{id}/prices` | GET    | Get price history                 |
| `/api/v1/supported-sites`      | GET    | List supported e-commerce sites   |
| `/api/v1/scrape`               | POST   | Scrape single product URL         |
| `/api/v1/scrape/batch`         | POST   | Scrape multiple URLs              |
| `/api/v1/stats`                | GET    | Database and scraper statistics   |
| `/api/v1/logs`                 | GET    | Get recent scraping activity logs |
| `/api/v1/docs`                 | GET    | Full API documentation            |

## Usage Examples

### Search Products

```bash
# Basic search
curl "http://localhost:5000/api/v1/search?q=iphone"

# With pagination and sorting
curl "http://localhost:5000/api/v1/search?q=laptop&page=1&per_page=20&sort=price&order=asc"
```

### Compare Products

```bash
curl "http://localhost:5000/api/v1/compare?ids=1,2,3"
```

### Get Product Details

```bash
# By ID
curl "http://localhost:5000/api/v1/products/1"

# By URL
curl "http://localhost:5000/api/v1/products?url=https://www.amazon.in/dp/B0EXAMPLE"
```

### Scrape a Product

```bash
curl -X POST http://localhost:5000/api/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.amazon.in/dp/B0EXAMPLE"}'
```

## API Response Format

### Successful Response

```json
{
  "success": true,
  "data": { ... },
  "cached": false
}
```

### Error Response

```json
{
  "success": false,
  "error": "Error Type",
  "message": "Detailed error message"
}
```

### Search Response with Pagination

```json
{
  "success": true,
  "data": {
    "products": [...],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 45,
      "total_pages": 3,
      "has_next": true,
      "has_prev": false
    },
    "query": "laptop",
    "sort": {
      "by": "price",
      "order": "asc"
    }
  }
}
```

## Configuration

Key configuration settings (in `app/config.py`):

| Setting                 | Default | Description                            |
| ----------------------- | ------- | -------------------------------------- |
| `SCRAPER_TIMEOUT`       | 5       | Request timeout in seconds             |
| `SELENIUM_TIMEOUT`      | 15      | Selenium page load timeout             |
| `MAX_WORKERS`           | 5       | Maximum concurrent scrapers            |
| `RATE_LIMIT_PER_MINUTE` | 10      | Requests per minute per IP             |
| `CACHE_TTL_SECONDS`     | 300     | Cache time-to-live (5 minutes)         |
| `FUZZY_MATCH_THRESHOLD` | 0.85    | Similarity threshold for deduplication |
| `SELENIUM_HEADLESS`     | True    | Run Chrome in headless mode            |

## Technical Specifications

- **Language**: Python 3.10+
- **Framework**: Flask with Blueprints
- **HTML Parsing**: BeautifulSoup4 with lxml
- **HTTP Client**: Requests with retries and timeouts
- **Browser Automation**: Selenium WebDriver with webdriver-manager
- **Database**: SQLite (built-in)
- **Concurrency**: concurrent.futures.ThreadPoolExecutor (5 workers)
- **Fuzzy Matching**: difflib.SequenceMatcher
- **Caching**: Custom in-memory TTL cache

## Web Dashboard

The web dashboard provides a simple interface to interact with the API:

- **Search Tab**: Search products across all sites
- **Compare Tab**: Compare multiple products by ID
- **Stats Tab**: View database statistics
- **Logs Tab**: View real-time scraping activity
- **Docs Tab**: View embedded API documentation

Access it at: `http://localhost:5000/dashboard`

## Development

### Run in development mode

```bash
# With uv
FLASK_DEBUG=1 uv run python main.py

# With pip
FLASK_DEBUG=1 python main.py
```

### Run tests

```bash
pytest
pytest --cov=app  # With coverage
```

## Troubleshooting

### Selenium Issues

1. **Chrome not found**: Install Chrome/Chromium browser
2. **WebDriver issues**: The `webdriver-manager` package auto-downloads the correct driver
3. **Sites blocking**: Some sites may block even Selenium. Consider using residential proxies.

### Rate Limiting

If you get rate limited errors, wait a minute or adjust `RATE_LIMIT_PER_MINUTE` in config.

## License

MIT License
