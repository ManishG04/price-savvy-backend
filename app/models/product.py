"""
Product Model
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Product:
    """Product model representing a scraped product."""
    
    id: Optional[int] = None
    url: str = ""
    title: str = ""
    source: str = ""
    current_price: float = 0.0
    original_price: Optional[float] = None
    currency: str = "INR"
    rating: Optional[str] = None
    reviews: Optional[str] = None
    image_url: Optional[str] = None
    availability: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert product to dictionary."""
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'source': self.source,
            'current_price': self.current_price,
            'original_price': self.original_price,
            'currency': self.currency,
            'rating': self.rating,
            'reviews': self.reviews,
            'image_url': self.image_url,
            'availability': self.availability,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Product':
        """Create a Product instance from a dictionary."""
        return cls(
            id=data.get('id'),
            url=data.get('url', ''),
            title=data.get('title', ''),
            source=data.get('source', ''),
            current_price=data.get('current_price', 0.0),
            original_price=data.get('original_price'),
            currency=data.get('currency', 'INR'),
            rating=data.get('rating'),
            reviews=data.get('reviews'),
            image_url=data.get('image_url'),
            availability=data.get('availability'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
        )
