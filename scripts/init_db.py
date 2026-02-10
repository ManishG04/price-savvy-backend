curl -s http://localhost:5000/ | python -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"#!/usr/bin/env python
"""
Database initialization script for Price Savvy Backend.
Run this script to create/reset the database.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Database


def init_database(db_path: str = "price_savvy.db", reset: bool = False):
    """
    Initialize the database.

    Args:
        db_path: Path to the database file
        reset: If True, delete existing database and create fresh
    """
    if reset and os.path.exists(db_path):
        print(f"Removing existing database: {db_path}")
        os.remove(db_path)

    print(f"Initializing database: {db_path}")
    db = Database(db_path)

    # Get stats to verify
    stats = db.get_stats()
    print(f"Database initialized successfully!")
    print(f"  - Products: {stats['total_products']}")
    print(f"  - Price history records: {stats['total_price_records']}")

    return db


def add_sample_data(db: Database):
    """Add sample data for testing."""
    sample_products = [
        {
            "url": "https://www.amazon.in/sample-product-1",
            "title": "Sample Wireless Headphones",
            "canonical_title": "sample wireless headphones",
            "source": "Amazon",
            "price": 1999.0,
            "original_price": 2999.0,
            "currency": "INR",
            "rating": 4.2,
            "rating_count": 1523,
            "availability": "In Stock",
            "image_url": "https://example.com/headphones.jpg",
            "description": "High quality wireless headphones with noise cancellation",
        },
        {
            "url": "https://www.flipkart.com/sample-product-1",
            "title": "Sample Wireless Headphones - Flipkart",
            "canonical_title": "sample wireless headphones flipkart",
            "source": "Flipkart",
            "price": 1899.0,
            "original_price": 2799.0,
            "currency": "INR",
            "rating": 4.3,
            "rating_count": 2341,
            "availability": "In Stock",
            "image_url": "https://example.com/headphones-fk.jpg",
            "description": "Premium wireless headphones with long battery life",
        },
        {
            "url": "https://www.amazon.in/sample-product-2",
            "title": "Smartphone Case Cover",
            "canonical_title": "smartphone case cover",
            "source": "Amazon",
            "price": 299.0,
            "original_price": 499.0,
            "currency": "INR",
            "rating": 3.8,
            "rating_count": 892,
            "availability": "In Stock",
            "image_url": "https://example.com/case.jpg",
            "description": "Durable smartphone case with premium finish",
        },
    ]

    print("\nAdding sample data...")
    for product in sample_products:
        product_id = db.upsert_product(product)
        print(f"  - Added: {product['title']} (ID: {product_id})")

    stats = db.get_stats()
    print(f"\nDatabase now has:")
    print(f"  - Products: {stats['total_products']}")
    print(f"  - Products by source: {stats['products_by_source']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize Price Savvy database")
    parser.add_argument(
        "--reset", action="store_true", help="Reset database (delete and recreate)"
    )
    parser.add_argument(
        "--sample-data", action="store_true", help="Add sample data for testing"
    )
    parser.add_argument(
        "--db-path",
        default="price_savvy.db",
        help="Path to database file (default: price_savvy.db)",
    )

    args = parser.parse_args()

    db = init_database(args.db_path, args.reset)

    if args.sample_data:
        add_sample_data(db)

    print("\nDone!")
