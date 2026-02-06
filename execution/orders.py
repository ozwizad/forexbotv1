from dataclasses import dataclass
from typing import Literal
from datetime import datetime

@dataclass
class OrderRequest:
    symbol: str
    order_type: Literal["BUY", "SELL"]
    volume: float
    price: float  # Estimated entry price
    sl: float
    tp: float
    magic: int
    comment: str
    timestamp: datetime
