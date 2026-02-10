#!/usr/bin/env python
"""
Test script to verify database functionality.
Run: python scripts/test_db.py
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Database


def test_database():
    """Test all database operations."""

    # Use a test database
    test_db_path = "test_price_savvy.db"

    # Clean up any existing test database
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    print("=" * 50)
    print("Testing Database Operations")
    print("=" * 50)

    try:
        # Initialize database
        print("\n1. Initializing database...")
        db = Database(test_db_path)
        print("   ✓ Database initialized")

        # Test insert
        print("\n2. Testing product insert...")
        product_data = {
            "url": "https://www.amazon.in/test-product",
            "title": "Test Product - Wireless Earbuds",
            "canonical_title": "test product wireless earbuds",
            "source": "Amazon",
            "price": 1499.0,
            "original_price": 2499.0,
            "currency": "INR",
            "rating": 4.5,
            "rating_count": 1000,
            "availability": "In Stock",
            "image_url": "https://example.com/image.jpg",
            "description": "Test product description",
        }
        product_id = db.upsert_product(product_data)
        print(f"   ✓ Product inserted with ID: {product_id}")

        # Test get by ID
        print("\n3. Testing get product by ID...")
        product = db.get_product_by_id(product_id)
        assert product is not None, "Product not found"
        assert product["title"] == product_data["title"], "Title mismatch"
        print(f"   ✓ Retrieved: {product['title']}")

        # Test get by URL
        print("\n4. Testing get product by URL...")
        product = db.get_product_by_url(product_data["url"])
        assert product is not None, "Product not found by URL"
        print(f"   ✓ Retrieved by URL: {product['title']}")

        # Test update (upsert existing)
        print("\n5. Testing product update...")
        product_data["price"] = 1299.0  # Price changed
        updated_id = db.upsert_product(product_data)
        assert updated_id == product_id, "ID should remain same after update"
        updated_product = db.get_product_by_id(product_id)
        assert updated_product["price"] == 1299.0, "Price not updated"
        print(f"   ✓ Price updated to: ₹{updated_product['price']}")

        # Test price history
        print("\n6. Testing price history...")
        history = db.get_price_history(product_id)
        assert len(history) >= 2, "Should have at least 2 price records"
        print(f"   ✓ Price history records: {len(history)}")
        for record in history:
            print(f"      - ₹{record['price']} at {record['recorded_at']}")

        # Test insert another product
        print("\n7. Adding second product...")
        product2_data = {
            "url": "https://www.flipkart.com/test-product",
            "title": "Test Product - Flipkart Version",
            "canonical_title": "test product flipkart version",
            "source": "Flipkart",
            "price": 1399.0,
            "currency": "INR",
            "rating": 4.3,
        }
        product2_id = db.upsert_product(product2_data)
        print(f"   ✓ Second product inserted with ID: {product2_id}")

        # Test get multiple by IDs
        print("\n8. Testing get multiple products by IDs...")
        products = db.get_products_by_ids([product_id, product2_id])
        assert len(products) == 2, "Should return 2 products"
        print(f"   ✓ Retrieved {len(products)} products")

        # Test search
        print("\n9. Testing product search...")
        search_result = db.search_products("Test Product")
        assert (
            search_result["pagination"]["total"] >= 2
        ), "Should find at least 2 products"
        print(f"   ✓ Search found {search_result['pagination']['total']} products")

        # Test get all products
        print("\n10. Testing get all products...")
        all_result = db.get_all_products()
        assert all_result["pagination"]["total"] >= 2, "Should have at least 2 products"
        print(f"   ✓ Total products: {all_result['pagination']['total']}")

        # Test is_stale
        print("\n11. Testing staleness check...")
        is_stale = db.is_stale(product_id, ttl_seconds=300)
        print(f"   ✓ Product stale (TTL=300s): {is_stale}")
        is_stale_immediate = db.is_stale(product_id, ttl_seconds=0)
        print(f"   ✓ Product stale (TTL=0s): {is_stale_immediate}")

        # Test stats
        print("\n12. Testing database stats...")
        stats = db.get_stats()
        print(f"   ✓ Stats: {stats}")

        # Test delete
        print("\n13. Testing product delete...")
        deleted = db.delete_product(product2_id)
        assert deleted, "Delete should return True"
        deleted_product = db.get_product_by_id(product2_id)
        assert deleted_product is None, "Product should be deleted"
        print(f"   ✓ Product {product2_id} deleted")

        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)

    except AssertionError as e:
        print(f"\n   ✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n   ✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Close database connection before cleanup
        try:
            db._get_connection().close()
        except:
            pass

        # Clean up test database
        import time

        time.sleep(0.1)  # Brief pause for Windows file release
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
                print(f"\nCleaned up test database: {test_db_path}")
            except PermissionError:
                print(
                    f"\nNote: Could not remove test database (file in use): {test_db_path}"
                )

    return True


if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
