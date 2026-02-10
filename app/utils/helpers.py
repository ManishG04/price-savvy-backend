"""
Helper utilities for Price Savvy Backend
"""

import re
from typing import Optional


def parse_price(price_str: str) -> Optional[float]:
    """
    Parse a price string and extract the numeric value.

    Args:
        price_str: The price string (e.g., "₹1,299.00", "$49.99")

    Returns:
        The numeric price value or None if parsing fails.
    """
    if not price_str:
        return None

    try:
        # Remove currency symbols and whitespace
        cleaned = re.sub(r"[₹$€£¥,\s]", "", price_str)
        # Extract numeric value
        match = re.search(r"[\d.]+", cleaned)
        if match:
            return float(match.group())
        return None
    except (ValueError, AttributeError):
        return None


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.

    Args:
        text: The text to clean.

    Returns:
        Cleaned text string.
    """
    if not text:
        return ""

    # Remove extra whitespace
    cleaned = " ".join(text.split())
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()

    return cleaned


def extract_asin_from_amazon_url(url: str) -> Optional[str]:
    """
    Extract ASIN (Amazon Standard Identification Number) from an Amazon URL.

    Args:
        url: Amazon product URL.

    Returns:
        ASIN string or None if not found.
    """
    if not url:
        return None

    # ASIN pattern (10 alphanumeric characters)
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/product/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"asin=([A-Z0-9]{10})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return None


def format_currency(amount: float, currency: str = "INR") -> str:
    """
    Format a numeric amount as currency string.

    Args:
        amount: The numeric amount.
        currency: Currency code (default: INR).

    Returns:
        Formatted currency string.
    """
    currency_symbols = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
    }

    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"
