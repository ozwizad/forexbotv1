from enum import Enum
import pandas as pd
from typing import Optional, Dict

class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class StrategyInterface:
    """
    Abstract base class for all strategies.
    Ensures consistent interface for the main event loop.
    """
    def categorize_signal(self, df: pd.DataFrame) -> Signal:
        """
        Analyzes the provided Dataframe (history + indicators) and returns a Signal.
        
        Args:
            df: Pandas DataFrame containing OHLCV and Indicator columns.
                Assumes the last row (iloc[-1]) is the 'Closed Candle' to analyze.
        
        Returns:
            Signal: BUY, SELL, or HOLD.
        """
        raise NotImplementedError
