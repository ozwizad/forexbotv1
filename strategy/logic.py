import pandas as pd
import logging
from strategy.interface import StrategyInterface, Signal
from config import settings

logger = logging.getLogger(__name__)

class EMATrendFollower(StrategyInterface):
    """
    Implementation of the EMA Trend Follower with Volatility Clamp strategy.
    
    Logic:
    1. Trend Filter: EMA50 > EMA200 (Buy) / EMA50 < EMA200 (Sell).
    2. Pullback: Price touched EMA50 within last 3 bars.
    3. Momentum: RSI rising/falling and within ranges.
    4. Trigger: Candle close vs Open and EMA50.
    """
    
    def __init__(self):
        # Parameters from settings
        self.ema_fast_period = settings.EMA_FAST
        self.ema_slow_period = settings.EMA_SLOW
        self.rsi_period = settings.RSI_PERIOD
        
    def categorize_signal(self, df: pd.DataFrame) -> Signal:
        """
        Evaluates the strategy rules on the provided DataFrame.
        Expected df columns: 'open', 'high', 'low', 'close', 'EMA_50', 'EMA_200', 'RSI'
        """
        # Minimum data requirement: Need at least 3 candles for logic (i, i-1, i-2)
        if len(df) < 3:
            logger.warning("Insufficient data for strategy analysis.")
            return Signal.HOLD

        # Indices (Pandas):
        # -1: Current candle (just closed) -> "i" in spec
        # -2: Previous candle -> "i+1" in spec
        # -3: Candle before previous -> "i+2" in spec
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # ----------------------------------------------------------------------
        # 1. REGIME FILTER
        # ----------------------------------------------------------------------
        ema_fast = curr[f'EMA_{self.ema_fast_period}']
        ema_slow = curr[f'EMA_{self.ema_slow_period}']
        
        if ema_fast > ema_slow:
            trend = "UP"
        elif ema_fast < ema_slow:
            trend = "DOWN"
        else:
            return Signal.HOLD # Sideways/Equality
            
        # Distance Check (0.1% rule from spec)
        # "If EMA50 == EMA200 or distance < 0.1% → NO TRADES"
        dist_pct = abs(ema_fast - ema_slow) / curr['close']
        if dist_pct < 0.001:
            return Signal.HOLD

        # ----------------------------------------------------------------------
        # 2. BUY SETUP Logic
        # ----------------------------------------------------------------------
        if trend == "UP":
            # Rule 1: Regime (Already checked)
            
            # Rule 2: Pullback (Touch or Cross EMA50 in last 3 candles)
            # Check lows of -1, -2, -3 against their respective EMA50s
            # Note: Using dynamic EMA values for past candles
            has_pullback = False
            for i in range(1, 4): # 1, 2, 3 (indices -1, -2, -3)
                row = df.iloc[-i]
                ema_val = row[f'EMA_{self.ema_fast_period}']
                if row['low'] <= ema_val:
                    has_pullback = True
                    break
            
            if not has_pullback:
                return Signal.HOLD

            # Rule 3: RSI Momentum
            # "RSI(14) was between 40 and 60" (Previous candle)
            # "Is now rising" (Current > Previous)
            rsi_prev = prev['RSI']
            rsi_curr = curr['RSI']
            
            if not (40 <= rsi_prev <= 60):
                return Signal.HOLD
            
            if not (rsi_curr > rsi_prev):
                return Signal.HOLD

            # Rule 4: Candle Shape (Bullish)
            if not (curr['close'] > curr['open']):
                return Signal.HOLD
                
            # Rule 5: Confirmation (Close > EMA50)
            if not (curr['close'] > ema_fast):
                return Signal.HOLD
                
            return Signal.BUY

        # ----------------------------------------------------------------------
        # 3. SELL SETUP Logic
        # ----------------------------------------------------------------------
        elif trend == "DOWN":
            # Rule 1: Regime (Already checked)
            
            # Rule 2: Pullback (Touch or Cross EMA50 in last 3 candles - HIGH >= EMA)
            has_pullback = False
            for i in range(1, 4):
                row = df.iloc[-i]
                ema_val = row[f'EMA_{self.ema_fast_period}']
                if row['high'] >= ema_val:
                    has_pullback = True
                    break
            
            if not has_pullback:
                return Signal.HOLD

            # Rule 3: RSI Momentum
            # "RSI(14) was between 60 and 40" (Previous candle - range order doesn't matter, just 40-60)
            # "Is now falling" (Current < Previous)
            rsi_prev = prev['RSI']
            rsi_curr = curr['RSI']

            if not (40 <= rsi_prev <= 60):
                return Signal.HOLD
                
            if not (rsi_curr < rsi_prev):
                return Signal.HOLD
                
            # Rule 4: Candle Shape (Bearish)
            if not (curr['close'] < curr['open']):
                return Signal.HOLD
                
            # Rule 5: Confirmation (Close < EMA50)
            if not (curr['close'] < ema_fast):
                return Signal.HOLD
                
            return Signal.SELL

        return Signal.HOLD
