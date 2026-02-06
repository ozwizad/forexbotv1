import pandas as pd
import logging
import numpy as np
from strategy.interface import StrategyInterface, Signal
from config import settings

logger = logging.getLogger(__name__)

class MeanReversionV1(StrategyInterface):
    """
    Mean Reversion Strategy V1 implementation.
    
    Rules:
    - Session: London (07-10) or NY (13-16).
    - Volatility: ATR(14) >= ATR(14).rolling(50).mean()
    - Buy: Close < EMA200, RSI <= 25, Dist >= 0.8*ATR, Bullish Candle, RSI Rising.
    - Sell: Close > EMA200, RSI >= 75, Dist >= 0.8*ATR, Bearish Candle, RSI Falling.
    """
    
    def __init__(self):
        # Parameters Fixed
        self.ema_period = 200
        self.rsi_period = 14
        self.atr_period = 14
        self.vol_ma_period = 50
        
    def categorize_signal(self, df: pd.DataFrame) -> Signal:
        """
        Evaluates the strategy rules on the provided DataFrame.
        """
        # Data requirements: Need at least 50 bars for ATR MA, plus previous bar analysis
        if len(df) < 51:
            return Signal.HOLD

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # ----------------------------------------------------------------------
        # 1. SESSION FILTER
        # ----------------------------------------------------------------------
        # Timestamps are in UTC (as per spec).
        # London: 07:00 <= hour < 10:00
        # New York: 13:00 <= hour < 16:00
        hour = curr['time'].hour
        is_london = 7 <= hour < 10
        is_ny = 13 <= hour < 16
        
        if not (is_london or is_ny):
            return Signal.HOLD
            
        # ----------------------------------------------------------------------
        # 2. VOLATILITY FILTER
        # ----------------------------------------------------------------------
        # Compute rolling mean of ATR(14) over last 50 bars
        # Note: We compute specific to this call to avoid recalc overhead or assume 'ATR' col exists
        # Spec says "Compute rolling mean of ATR(14) over last 50 bars"
        # We need to ensure ATR is present.
        
        # To avoid re-calculating rolling on just passed slice efficiently:
        # We assume the 'ATR' column is fully populated in the DF passed.
        # We extract the last 50 ATR values including current? 
        # "over last 50 bars". Usually means exclusive of current or inclusive?
        # Standard: rolling(50) at index i includes i.
        
        # Let's calculate the value dynamically if not present (unlikely with our engine)
        atr_series = df['ATR']
        if len(atr_series) < 50:
             return Signal.HOLD
             
        atr_50_mean = atr_series.rolling(window=50).mean().iloc[-1]
        atr_current = curr['ATR']
        
        if atr_current < atr_50_mean:
            return Signal.HOLD

        # ----------------------------------------------------------------------
        # 3. CORE LOGIC
        # ----------------------------------------------------------------------
        ema200 = curr[f'EMA_{self.ema_period}'] # Expecting EMA_200 column
        rsi_curr = curr['RSI']
        rsi_prev = prev['RSI']
        close = curr['close']
        open_ = curr['open']
        
        dist = abs(close - ema200)
        dist_threshold = atr_current * 0.8
        
        # BUY SETUP
        if close < ema200:
             # RSI Extreme
             if rsi_curr <= 25:
                 # Stretch
                 if dist >= dist_threshold:
                     # Trigger Candle
                     if close > open_: # Bullish
                         if rsi_curr > rsi_prev: # Rising
                             return Signal.BUY

        # SELL SETUP
        elif close > ema200:
            # RSI Extreme
            if rsi_curr >= 75:
                # Stretch
                if dist >= dist_threshold:
                    # Trigger Candle
                    if close < open_: # Bearish
                        if rsi_curr < rsi_prev: # Falling
                            return Signal.SELL
                            
        return Signal.HOLD
