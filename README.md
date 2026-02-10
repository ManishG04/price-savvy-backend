# Price Savvy Backend

A Flask-based REST API for scraping, comparing, and tracking product prices across multiple e-commerce platforms. Built for price-savvy shoppers and small resellers.

## Features

- 🔍 **Product Search**: Search products across Amazon and Flipkart simultaneously
- ⚖️ **Price Comparison**: Compare products with best-by metrics highlighted
- 📊 **Price Tracking**: Track price history over time
- � **Data Normalization**: Unified price format and 0-5 scale ratings
- 🧹 **Deduplication**: Fuzzy matching to merge near-duplicate listings
- ⚡ **Concurrent Scraping**: Fast multi-site scraping with ThreadPoolExecutor
- 🛡️ **Rate Limiting**: Polite scraping with per-IP rate limits
- � **Caching**: In-memory TTL cache for recent queries
- 🗄️ **SQLite Storage**: Persistent product and price history storage

## Project Structure

```
price-savvy-backend/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── config.py             # Configuration settings
│   ├── database.py           # SQLite database handler
│   ├── api/
│   │   ├── __init__.py       # API blueprint
│   │   └── routes.py         # API endpoints
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base_scraper.py   # Abstract base scraper
│   │   ├── amazon_scraper.py # Amazon scraper
│   │   └── flipkart_scraper.py # Flipkart scraper
│   ├── services/
│   │   ├── __init__.py
│   │   └── scraper_service.py # Concurrent scraping logic
│   ├── models/
│   │   ├── __init__.py
│   │   ├── product.py        # Product model
│   │   └── price_history.py  # Price history model
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cache.py          # TTL cache implementation
│   │   ├── rate_limiter.py   # Rate limiting
│   │   ├── normalizer.py     # Data normalization & deduplication
│   │   ├── validators.py     # Input validation
│   │   └── helpers.py        # Helper functions
│   └── errors/
│       └── __init__.py       # Error handlers
├── main.py                   # Application entry point
├── pyproject.toml            # Project dependencies
├── .env.example              # Environment variables template
└── README.md
```

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/ManishG04/price-savvy-backend.git
   cd price-savvy-backend
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -e .
   # Or using uv:
   uv sync
   ```

4. **Set up environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application**

   ```bash
   python main.py
   ```

   The API will be available at `http://localhost:5000`

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

| Endpoint                       | Method | Description                     |
| ------------------------------ | ------ | ------------------------------- |
| `/api/v1/products/{id}/prices` | GET    | Get price history               |
| `/api/v1/supported-sites`      | GET    | List supported e-commerce sites |
| `/api/v1/scrape`               | POST   | Scrape single product URL       |
| `/api/v1/scrape/batch`         | POST   | Scrape multiple URLs            |

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

Key environment variables (see `.env.example`):

| Variable                | Default | Description                            |
| ----------------------- | ------- | -------------------------------------- |
| `SCRAPER_TIMEOUT`       | 5       | Request timeout in seconds             |
| `MAX_WORKERS`           | 5       | Maximum concurrent scrapers            |
| `RATE_LIMIT_PER_MINUTE` | 10      | Requests per minute per IP             |
| `CACHE_TTL_SECONDS`     | 300     | Cache time-to-live                     |
| `FUZZY_MATCH_THRESHOLD` | 0.85    | Similarity threshold for deduplication |

## Supported Sites

| Site         | Domain       | Status    |
| ------------ | ------------ | --------- |
| Amazon India | amazon.in    | ✅ Active |
| Amazon       | amazon.com   | ✅ Active |
| Flipkart     | flipkart.com | ✅ Active |

## Technical Specifications

- **Language**: Python 3.10+
- **Framework**: Flask with Blueprints
- **Parsing**: BeautifulSoup4 with lxml
- **HTTP Client**: Requests with retries and timeouts
- **Database**: SQLite
- **Concurrency**: concurrent.futures.ThreadPoolExecutor
- **Fuzzy Matching**: difflib.SequenceMatcher
- **Caching**: Custom in-memory TTL cache

## Development

### Run in development mode

```bash
FLASK_DEBUG=1 python main.py
```

### Run tests

```bash
pytest
pytest --cov=app  # With coverage
```

### Code formatting

```bash
black app/
flake8 app/
```

## License

MIT License
