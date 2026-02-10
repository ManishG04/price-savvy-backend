"""
Database module for Price Savvy Backend
As per PRD: SQLite (via SQLAlchemy or built-in sqlite3) for storage
"""
import sqlite3
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


class Database:
    """SQLite database handler for product storage."""
    
    _local = threading.local()
    
    def __init__(self, db_path: str = 'price_savvy.db'):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    
    def _ensure_tables(self) -> None:
        """Create database tables if they don't exist."""
        with self.get_cursor() as cursor:
            # Products table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    canonical_title TEXT,
                    source TEXT NOT NULL,
                    price REAL NOT NULL,
                    original_price REAL,
                    currency TEXT DEFAULT 'INR',
                    rating REAL,
                    rating_count INTEGER,
                    image_url TEXT,
                    availability TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for efficient lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_products_url 
                ON products(url)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_products_source 
                ON products(source)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_products_canonical_title 
                ON products(canonical_title)
            ''')
            
            # Price history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_price_history_product 
                ON price_history(product_id)
            ''')
    
    def upsert_product(self, product_data: Dict[str, Any]) -> int:
        """
        Insert or update a product.
        
        Args:
            product_data: Dictionary containing product fields
            
        Returns:
            The product ID
        """
        with self.get_cursor() as cursor:
            # Check if product exists
            cursor.execute(
                'SELECT id, price FROM products WHERE url = ?',
                (product_data['url'],)
            )
            existing = cursor.fetchone()
            
            if existing:
                product_id = existing['id']
                old_price = existing['price']
                
                # Update existing product
                cursor.execute('''
                    UPDATE products SET
                        title = ?,
                        canonical_title = ?,
                        source = ?,
                        price = ?,
                        original_price = ?,
                        currency = ?,
                        rating = ?,
                        rating_count = ?,
                        image_url = ?,
                        availability = ?,
                        description = ?,
                        updated_at = ?
                    WHERE id = ?
                ''', (
                    product_data.get('title', ''),
                    product_data.get('canonical_title', ''),
                    product_data.get('source', ''),
                    product_data.get('price', 0.0),
                    product_data.get('original_price'),
                    product_data.get('currency', 'INR'),
                    product_data.get('rating'),
                    product_data.get('rating_count'),
                    product_data.get('image_url'),
                    product_data.get('availability'),
                    product_data.get('description'),
                    datetime.utcnow(),
                    product_id
                ))
                
                # Record price history if price changed
                new_price = product_data.get('price', 0.0)
                if old_price != new_price:
                    cursor.execute(
                        'INSERT INTO price_history (product_id, price) VALUES (?, ?)',
                        (product_id, new_price)
                    )
            else:
                # Insert new product
                cursor.execute('''
                    INSERT INTO products (
                        url, title, canonical_title, source, price,
                        original_price, currency, rating, rating_count,
                        image_url, availability, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product_data['url'],
                    product_data.get('title', ''),
                    product_data.get('canonical_title', ''),
                    product_data.get('source', ''),
                    product_data.get('price', 0.0),
                    product_data.get('original_price'),
                    product_data.get('currency', 'INR'),
                    product_data.get('rating'),
                    product_data.get('rating_count'),
                    product_data.get('image_url'),
                    product_data.get('availability'),
                    product_data.get('description')
                ))
                product_id = cursor.lastrowid
                
                # Record initial price
                cursor.execute(
                    'INSERT INTO price_history (product_id, price) VALUES (?, ?)',
                    (product_id, product_data.get('price', 0.0))
                )
            
            return product_id
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get a product by its ID."""
        with self.get_cursor() as cursor:
            cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_product_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a product by its URL."""
        with self.get_cursor() as cursor:
            cursor.execute('SELECT * FROM products WHERE url = ?', (url,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_products_by_ids(self, product_ids: List[int]) -> List[Dict[str, Any]]:
        """Get multiple products by their IDs."""
        if not product_ids:
            return []
        
        placeholders = ','.join('?' * len(product_ids))
        with self.get_cursor() as cursor:
            cursor.execute(
                f'SELECT * FROM products WHERE id IN ({placeholders})',
                product_ids
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def search_products(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = 'price',
        sort_order: str = 'asc'
    ) -> Dict[str, Any]:
        """
        Search products by title.
        
        Args:
            query: Search query
            page: Page number (1-indexed)
            per_page: Results per page
            sort_by: Field to sort by (price, rating)
            sort_order: Sort order (asc, desc)
            
        Returns:
            Dictionary with products and pagination metadata
        """
        offset = (page - 1) * per_page
        
        # Validate sort parameters
        valid_sort_fields = {'price', 'rating', 'updated_at'}
        sort_by = sort_by if sort_by in valid_sort_fields else 'price'
        sort_order = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
        
        with self.get_cursor() as cursor:
            # Get total count
            cursor.execute(
                'SELECT COUNT(*) as count FROM products WHERE title LIKE ?',
                (f'%{query}%',)
            )
            total = cursor.fetchone()['count']
            
            # Get paginated results
            cursor.execute(
                f'''
                SELECT * FROM products 
                WHERE title LIKE ? 
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
                ''',
                (f'%{query}%', per_page, offset)
            )
            products = [dict(row) for row in cursor.fetchall()]
        
        return {
            'products': products,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
                'has_next': page * per_page < total,
                'has_prev': page > 1
            }
        }
    
    def get_price_history(self, product_id: int) -> List[Dict[str, Any]]:
        """Get price history for a product."""
        with self.get_cursor() as cursor:
            cursor.execute(
                '''
                SELECT price, recorded_at 
                FROM price_history 
                WHERE product_id = ? 
                ORDER BY recorded_at DESC
                ''',
                (product_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def is_stale(self, product_id: int, ttl_seconds: int = 300) -> bool:
        """Check if a product's data is stale (beyond TTL)."""
        with self.get_cursor() as cursor:
            cursor.execute(
                'SELECT updated_at FROM products WHERE id = ?',
                (product_id,)
            )
            row = cursor.fetchone()
            if not row:
                return True
            
            updated_at = datetime.fromisoformat(row['updated_at'])
            age = (datetime.utcnow() - updated_at).total_seconds()
            return age > ttl_seconds


# Global database instance
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """Get or create the global database instance."""
    global _db_instance
    if _db_instance is None:
        from flask import current_app
        try:
            db_url = current_app.config.get('DATABASE_URL', 'sqlite:///price_savvy.db')
            # Extract path from sqlite:/// URL
            if db_url.startswith('sqlite:///'):
                db_path = db_url[10:]
            else:
                db_path = 'price_savvy.db'
        except RuntimeError:
            db_path = 'price_savvy.db'
        _db_instance = Database(db_path)
    return _db_instance
