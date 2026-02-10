"""
Data Normalizer for Price Savvy Backend
As per PRD: Normalize and deduplicate product data across sources
- Unified price format
- Standardized ratings (0-5 scale)
- Fuzzy name matching for deduplication
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher


# Common stopwords to remove during canonicalization
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'for', 'with', 'in', 'on', 'at',
    'new', 'latest', 'original', 'genuine', 'authentic', 'official',
    'pack', 'set', 'combo', 'bundle', 'piece', 'pcs', 'unit',
}

# Common brand names to preserve during canonicalization
BRAND_PATTERNS = [
    r'\bapple\b', r'\bsamsung\b', r'\bsony\b', r'\blg\b', r'\bhp\b',
    r'\bdell\b', r'\blenovo\b', r'\basus\b', r'\bacer\b', r'\bmsi\b',
    r'\bnike\b', r'\badidas\b', r'\bpuma\b', r'\breebok\b',
    r'\bboat\b', r'\bjbl\b', r'\bbose\b', r'\bsennheiser\b',
]


def normalize_price(price_str: str, source_currency: str = 'INR') -> Tuple[float, str]:
    """
    Convert price to a numeric format in a single currency.
    
    Args:
        price_str: Price string (e.g., "₹1,299.00", "$49.99")
        source_currency: Source currency code
        
    Returns:
        Tuple of (normalized price as float, currency code)
    """
    if not price_str:
        return 0.0, source_currency
    
    if isinstance(price_str, (int, float)):
        return float(price_str), source_currency
    
    # Detect currency from symbol
    currency_map = {
        '₹': 'INR',
        '$': 'USD',
        '€': 'EUR',
        '£': 'GBP',
        '¥': 'JPY',
    }
    
    detected_currency = source_currency
    for symbol, code in currency_map.items():
        if symbol in price_str:
            detected_currency = code
            break
    
    # Remove currency symbols, commas, and whitespace
    cleaned = re.sub(r'[₹$€£¥,\s]', '', str(price_str))
    
    # Extract numeric value
    match = re.search(r'[\d.]+', cleaned)
    if match:
        try:
            price = float(match.group())
            return price, detected_currency
        except ValueError:
            return 0.0, detected_currency
    
    return 0.0, detected_currency


def normalize_rating(rating_str: str, max_rating: float = 5.0) -> Optional[float]:
    """
    Standardize ratings to a 0-5 scale.
    
    Args:
        rating_str: Rating string (e.g., "4.2", "4.2 out of 5", "84%")
        max_rating: Maximum rating in source scale
        
    Returns:
        Normalized rating on 0-5 scale, or None if parsing fails
    """
    if not rating_str:
        return None
    
    if isinstance(rating_str, (int, float)):
        rating = float(rating_str)
        # Assume if > 5, it's a percentage or 10-point scale
        if rating > 5:
            if rating <= 10:
                return (rating / 10) * 5
            elif rating <= 100:
                return (rating / 100) * 5
        return min(5.0, max(0.0, rating))
    
    # Handle percentage ratings
    if '%' in str(rating_str):
        match = re.search(r'([\d.]+)%', str(rating_str))
        if match:
            return (float(match.group(1)) / 100) * 5
    
    # Handle "X out of Y" format
    match = re.search(r'([\d.]+)\s*(?:out of|/)\s*([\d.]+)', str(rating_str))
    if match:
        rating = float(match.group(1))
        max_val = float(match.group(2))
        return (rating / max_val) * 5 if max_val > 0 else None
    
    # Extract simple numeric rating
    match = re.search(r'[\d.]+', str(rating_str))
    if match:
        try:
            rating = float(match.group())
            # Normalize if on different scale
            if rating > 5 and rating <= 10:
                return (rating / 10) * 5
            return min(5.0, max(0.0, rating))
        except ValueError:
            return None
    
    return None


def canonicalize_title(title: str) -> str:
    """
    Canonicalize product title for comparison.
    - Convert to lowercase
    - Remove stopwords
    - Normalize whitespace
    
    Args:
        title: Original product title
        
    Returns:
        Canonicalized title
    """
    if not title:
        return ""
    
    # Convert to lowercase
    canonical = title.lower()
    
    # Remove special characters but keep alphanumeric and spaces
    canonical = re.sub(r'[^\w\s]', ' ', canonical)
    
    # Split into tokens
    tokens = canonical.split()
    
    # Remove stopwords (but keep brand names)
    filtered_tokens = []
    for token in tokens:
        if token not in STOPWORDS:
            filtered_tokens.append(token)
        elif any(re.match(pattern, token) for pattern in BRAND_PATTERNS):
            filtered_tokens.append(token)
    
    # Rejoin and normalize whitespace
    canonical = ' '.join(filtered_tokens)
    
    return canonical


def calculate_similarity(title1: str, title2: str) -> float:
    """
    Calculate fuzzy similarity between two titles.
    
    Args:
        title1: First title (should be canonicalized)
        title2: Second title (should be canonicalized)
        
    Returns:
        Similarity score between 0 and 1
    """
    if not title1 or not title2:
        return 0.0
    
    # Use SequenceMatcher for fuzzy matching
    return SequenceMatcher(None, title1, title2).ratio()


def normalize_product(product: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Normalize a product record.
    
    Args:
        product: Raw product data
        source: Source website name
        
    Returns:
        Normalized product dictionary
    """
    # Normalize price
    price_value = product.get('price') or product.get('current_price', 0)
    price, currency = normalize_price(price_value)
    
    original_price = product.get('original_price')
    if original_price:
        original_price, _ = normalize_price(original_price)
    
    # Normalize rating
    rating = normalize_rating(product.get('rating'))
    
    # Parse rating count
    rating_count = None
    rating_count_str = product.get('reviews') or product.get('rating_count')
    if rating_count_str:
        match = re.search(r'[\d,]+', str(rating_count_str).replace(',', ''))
        if match:
            try:
                rating_count = int(match.group().replace(',', ''))
            except ValueError:
                pass
    
    # Canonicalize title
    title = product.get('title', '')
    canonical_title = canonicalize_title(title)
    
    return {
        'url': product.get('url', ''),
        'title': title,
        'canonical_title': canonical_title,
        'source': source,
        'price': price,
        'original_price': original_price,
        'currency': currency,
        'rating': rating,
        'rating_count': rating_count,
        'image_url': product.get('image_url'),
        'availability': product.get('availability'),
        'description': product.get('description'),
    }


def find_duplicates(
    products: List[Dict[str, Any]],
    threshold: float = 0.85
) -> List[List[int]]:
    """
    Find groups of duplicate products based on fuzzy title matching.
    
    Args:
        products: List of normalized products
        threshold: Similarity threshold for considering duplicates
        
    Returns:
        List of duplicate groups (each group is a list of indices)
    """
    n = len(products)
    visited = set()
    duplicate_groups = []
    
    for i in range(n):
        if i in visited:
            continue
        
        group = [i]
        visited.add(i)
        
        title_i = products[i].get('canonical_title', '')
        
        for j in range(i + 1, n):
            if j in visited:
                continue
            
            title_j = products[j].get('canonical_title', '')
            similarity = calculate_similarity(title_i, title_j)
            
            if similarity >= threshold:
                group.append(j)
                visited.add(j)
        
        if len(group) > 1:
            duplicate_groups.append(group)
    
    return duplicate_groups


def merge_duplicates(
    products: List[Dict[str, Any]],
    threshold: float = 0.85
) -> List[Dict[str, Any]]:
    """
    Merge duplicate products, keeping the best information from each.
    
    Args:
        products: List of normalized products
        threshold: Similarity threshold for considering duplicates
        
    Returns:
        List of deduplicated products with merged information
    """
    if not products:
        return []
    
    duplicate_groups = find_duplicates(products, threshold)
    merged_indices = set()
    
    result = []
    
    # Process duplicate groups
    for group in duplicate_groups:
        group_products = [products[i] for i in group]
        
        # Select the product with the best data quality as base
        # (prefer one with more fields filled, better rating count)
        best_product = max(
            group_products,
            key=lambda p: (
                sum(1 for v in p.values() if v is not None and v != ''),
                p.get('rating_count') or 0
            )
        )
        
        # Merge: collect all sources and prices
        merged = best_product.copy()
        merged['sources'] = [
            {
                'source': p.get('source'),
                'url': p.get('url'),
                'price': p.get('price'),
                'availability': p.get('availability')
            }
            for p in group_products
        ]
        merged['best_price'] = min(p.get('price', float('inf')) for p in group_products)
        
        result.append(merged)
        merged_indices.update(group)
    
    # Add non-duplicate products
    for i, product in enumerate(products):
        if i not in merged_indices:
            product['sources'] = [{
                'source': product.get('source'),
                'url': product.get('url'),
                'price': product.get('price'),
                'availability': product.get('availability')
            }]
            product['best_price'] = product.get('price', 0)
            result.append(product)
    
    return result


def compare_products(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare products and highlight best-by metrics.
    
    Args:
        products: List of products to compare
        
    Returns:
        Comparison result with aligned fields and best indicators
    """
    if not products:
        return {'products': [], 'best': {}}
    
    # Find best values
    prices = [p.get('price', float('inf')) for p in products if p.get('price')]
    ratings = [p.get('rating', 0) for p in products if p.get('rating')]
    
    best = {}
    
    if prices:
        min_price = min(prices)
        best['price'] = {
            'value': min_price,
            'product_ids': [
                p.get('id') or i for i, p in enumerate(products)
                if p.get('price') == min_price
            ]
        }
    
    if ratings:
        max_rating = max(ratings)
        best['rating'] = {
            'value': max_rating,
            'product_ids': [
                p.get('id') or i for i, p in enumerate(products)
                if p.get('rating') == max_rating
            ]
        }
    
    # Align product fields for comparison
    aligned_products = []
    for i, product in enumerate(products):
        aligned = {
            'id': product.get('id') or i,
            'title': product.get('title'),
            'source': product.get('source'),
            'url': product.get('url'),
            'price': product.get('price'),
            'original_price': product.get('original_price'),
            'currency': product.get('currency'),
            'rating': product.get('rating'),
            'rating_count': product.get('rating_count'),
            'availability': product.get('availability'),
            'is_best_price': product.get('price') == best.get('price', {}).get('value'),
            'is_best_rating': product.get('rating') == best.get('rating', {}).get('value'),
        }
        
        # Calculate discount percentage
        if aligned['original_price'] and aligned['price']:
            discount = ((aligned['original_price'] - aligned['price']) / aligned['original_price']) * 100
            aligned['discount_percent'] = round(discount, 1)
        else:
            aligned['discount_percent'] = None
        
        aligned_products.append(aligned)
    
    return {
        'products': aligned_products,
        'best': best,
        'count': len(products)
    }
