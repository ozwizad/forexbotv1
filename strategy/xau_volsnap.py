import pandas as pd
import numpy as np
import logging
from strategy.interface import StrategyInterface, Signal
from data.indicators import calculate_ema, calculate_atr, calculate_rsi

logger = logging.getLogger(__name__)

class XAUVolSnapStrategy(StrategyInterface):
    """
    XAUUSD H1 Volatility Snap v1 Strategy
    
    Market: XAUUSD H1
    Indicators: EMA(100), ATR(14), RSI(14)
    Sessions: London (07-10 UTC), NY (13-16 UTC)
    """
    
    def __init__(self):
        self.ema_period = 100
        self.atr_period = 14
        self.rsi_period = 14
        self.sl_atr_mult = 1.2
        self.tp_atr_mult = 1.0
        self.max_dist_ema_mult = 2.0
    
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-calculates indicators for the entire dataset to speed up backtesting.
        """
        df = df.copy()
        df['EMA100'] = calculate_ema(df['close'], self.ema_period)
        df['ATR'] = calculate_atr(df, self.atr_period)
        df['RSI'] = calculate_rsi(df['close'], self.rsi_period)
        
        # Pre-calculate hour for session filter (assuming timestamp is in UTC or aligned)
        df['hour'] = df['time'].dt.hour
        return df

    def categorize_signal(self, row: pd.Series, prev_row: pd.Series) -> Signal:
        """
        Refined analyze method that looks at the current confirmed candle (row)
        and potentially the setup candle (prev_row).
        
        In the requirements:
        "Confirmation candle (next bar): bullish/bearish"
        This implies we are continuously looking for a setup.
        
        Let's interpret the user's logic step-by-step for a LIVE decision or backtest iteration.
        
        The 'Entry' happens at the close of the confirmation candle.
        So we analyze the 'Confirmation Candle' (Just Closed).
        
        Setup conditions must be met on the bar BEFORE the confirmation candle (Setup Candle).
        """
        
        # 0. Session Filter
        # "Only evaluate trades when candle close time is within..."
        # If we are analyzing 'row' (the just-closed candle), uses its time.
        current_hour = row['hour']
        is_london = 7 <= current_hour < 10
        is_ny = 13 <= current_hour < 16
        
        if not (is_london or is_ny):
            return Signal.HOLD

        # Setup candle is the previous one
        setup_close = prev_row['close']
        setup_open = prev_row['open']
        setup_atr = prev_row['ATR']
        setup_rsi = prev_row['RSI']
        setup_ema = prev_row['EMA100']
        
        # Current (Confirmation) candle
        conf_close = row['close']
        conf_open = row['open']
        
        # Constants
        atr_12 = setup_atr * 1.2
        atr_max_dev = setup_atr * self.max_dist_ema_mult

        # --- BUY SETUP ---
        # 1. Large bearish expansion candle (Setup)
        # (close - open) < -ATR(14) * 1.2
        is_bearish_expansion = (setup_close - setup_open) < -atr_12
        
        # 2. RSI oversold (Setup)
        # RSI(14) < 30
        is_oversold = setup_rsi < 30
        
        # 3. Price not excessively far from EMA100 (Setup)
        # abs(close - EMA100) < ATR(14) * 2
        dist_ema = abs(setup_close - setup_ema)
        is_near_ema = dist_ema < atr_max_dev
        
        # 4. Confirmation candle (next bar) -> The current 'row'
        # bullish candle (close > open)
        is_confirmation_bullish = conf_close > conf_open
        
        if is_bearish_expansion and is_oversold and is_near_ema and is_confirmation_bullish:
            return Signal.BUY

        # --- SELL SETUP ---
        # 1. Large bullish expansion candle (Setup)
        # (close - open) > ATR(14) * 1.2
        is_bullish_expansion = (setup_close - setup_open) > atr_12
        
        # 2. RSI overbought (Setup)
        # RSI(14) > 70
        is_overbought = setup_rsi > 70
        
        # 3. Price not excessively far from EMA100 (Setup)
        # abs(close - EMA100) < ATR(14) * 2
        # (using calculated dist_ema from above, same logic)
        
        # 4. Confirmation candle (next bar) -> The current 'row'
        # bearish candle (close < open)
        is_confirmation_bearish = conf_close < conf_open
        
        if is_bullish_expansion and is_overbought and is_near_ema and is_confirmation_bearish:
            return Signal.SELL

        return Signal.HOLD
