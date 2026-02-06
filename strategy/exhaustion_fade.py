"""
XAUUSD H1 Exhaustion Fade Strategy

Edge Thesis:
When XAUUSD moves >3x ATR(14) from session open in a single session,
it signals short-term exhaustion. Fade the move with mean-reversion logic.
"""

import pandas as pd
from data.indicators import calculate_atr


class ExhaustionFadeStrategy:
    """
    Exhaustion Fade Strategy for XAUUSD H1.
    """
    
    def __init__(self):
        # Session definitions (UTC hours)
        self.london_open_hour = 7
        self.ny_open_hour = 13
        self.session_end_hour = 20
        
        # Thresholds
        self.displacement_atr_mult = 3.0
        self.exhaustion_candle_mult = 0.5
        
        # Exit parameters
        self.tp_atr_mult = 1.0
        self.sl_atr_mult = 1.0
        self.time_exit_bars = 4  # 4 hours
        
        # ATR period
        self.atr_period = 14

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculate ATR for the entire dataset.
        """
        df = df.copy()
        df['ATR'] = calculate_atr(df, self.atr_period)
        df['hour'] = df['time'].dt.hour
        df['date'] = df['time'].dt.date
        df['candle_body'] = abs(df['close'] - df['open'])
        return df
