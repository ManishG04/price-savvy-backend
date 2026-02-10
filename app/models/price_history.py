"""
Price History Model
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PriceHistory:
    """Price history model for tracking price changes."""
    
    id: Optional[int] = None
    product_id: int = 0
    price: float = 0.0
    currency: str = "INR"
    recorded_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert price history to dictionary."""
        return {
            'id': self.id,
            'product_id': self.product_id,
            'price': self.price,
            'currency': self.currency,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PriceHistory':
        """Create a PriceHistory instance from a dictionary."""
        return cls(
            id=data.get('id'),
            product_id=data.get('product_id', 0),
            price=data.get('price', 0.0),
            currency=data.get('currency', 'INR'),
            recorded_at=data.get('recorded_at'),
        )
