"""
XAUUSD H1 Momentum Continuation Strategy

Edge Thesis:
Gold trends strongly. When price displaces >2x ATR from session open
with a strong candle (body >= 0.6x ATR), follow the momentum.
"""

import pandas as pd
from data.indicators import calculate_atr


class MomentumContinuationStrategy:
    """
    Momentum Continuation Strategy for XAUUSD H1.
    """
    
    def __init__(self):
        # Session definitions (UTC hours)
        self.london_open_hour = 7
        self.ny_open_hour = 13
        self.session_end_hour = 18  # End earlier to avoid late-session chop
        
        # Thresholds
        self.displacement_atr_mult = 2.0
        self.strong_candle_mult = 0.6
        
        # Exit parameters
        self.tp_atr_mult = 2.0
        self.sl_atr_mult = 1.5
        self.time_exit_bars = 6  # 6 hours
        
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
