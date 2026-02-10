"""
Validation utilities for Price Savvy Backend
"""

import re
from urllib.parse import urlparse


def validate_url(url: str) -> bool:
    """
    Validate if a string is a valid URL.

    Args:
        url: The URL string to validate.

    Returns:
        True if valid URL, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def validate_product_id(product_id: any) -> bool:
    """
    Validate if a product ID is valid.

    Args:
        product_id: The product ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    if product_id is None:
        return False

    try:
        int_id = int(product_id)
        return int_id > 0
    except (ValueError, TypeError):
        return False


def validate_email(email: str) -> bool:
    """
    Validate if a string is a valid email address.

    Args:
        email: The email string to validate.

    Returns:
        True if valid email, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))
