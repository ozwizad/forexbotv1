"""
XAUUSD H1 Asian Range Breakout Strategy v2

Edge Thesis:
Gold consolidates during Asian session (00:00-08:00 UTC).
London open (08:00 UTC) brings institutional liquidity that breaks this range.
Trade the FIRST confirmed breakout only (One Bullet Rule).

v2 Changes:
- One Bullet Rule: Max 1 trade per day
- Range Filter: $5 < Range < $20 (50-200 pips XAUUSD)
- Accelerated Break-Even: At 0.8 * ATR profit, SL → Entry + Spread
- Time Exit Removed: Only TP or SL exits
"""

import pandas as pd
from strategy.interface import Signal


class AsianBreakoutStrategy:
    """
    Asian Range Breakout Strategy v2 for XAUUSD H1.
    
    Key Rules:
    - One Bullet Rule: Only 1 trade per day
    - Range Filter: 5 < Asian Range < 20 dollars
    - Accelerated Break-Even: 0.8 * Range triggers BE
    - No Time Exit: Only TP or SL
    """
    
    def __init__(self):
        # Session definitions (UTC hours)
        self.asian_start_hour = 0
        self.asian_end_hour = 8    # Extended to 08:00 for full range
        self.entry_window_start = 8   # London volatility window
        self.entry_window_end = 11    # 08:00-11:00 UTC only
        
        # ONE BULLET RULE: Max 1 trade per day
        self.daily_trade_limit = 1
        
        # Range Filters (XAUUSD dollars, not percentage)
        # $5 min prevents too-narrow ranges (violent breakouts)
        # $40 max prevents exhausted ranges (XAUUSD typically has larger ranges than Forex)
        self.min_range_dollars = 5.0
        self.max_range_dollars = 40.0
        
        # TP/SL Configuration
        self.tp_multiplier = 1.0   # TP = 1.0x Asian Range
        self.sl_at_range_boundary = True  # SL at opposite range boundary
        
        # Accelerated Break-Even
        # Move SL to Entry + Spread when profit reaches 0.8 * Range
        self.breakeven_trigger_multiplier = 0.8
        
        # Time Exit DISABLED (v2)
        self.time_exit_enabled = False
        # self.time_exit_hour = 20  # REMOVED

    def get_asian_range(self, df: pd.DataFrame, current_date) -> tuple:
        """
        Calculate the Asian session High and Low for the given date.
        Asian session: 00:00 - 08:00 UTC
        
        Returns:
            (asian_high, asian_low) or (None, None) if insufficient data
        """
        asian_candles = df[
            (df['time'].dt.date == current_date) &
            (df['time'].dt.hour >= self.asian_start_hour) &
            (df['time'].dt.hour < self.asian_end_hour)
        ]
        
        # Need at least 5 candles for a valid range (5 hours)
        if len(asian_candles) < 5:
            return None, None
        
        asian_high = asian_candles['high'].max()
        asian_low = asian_candles['low'].min()
        
        return asian_high, asian_low

    def check_range_filter(self, asian_high: float, asian_low: float) -> bool:
        """
        Check if the Asian range meets size requirements.
        
        Rules:
        - Range must be > $5 (prevents violent breakouts from narrow ranges)
        - Range must be < $20 (prevents trading exhausted ranges)
        
        Returns:
            True if range is valid for trading
        """
        if asian_high is None or asian_low is None:
            return False
        
        range_dollars = asian_high - asian_low
        
        # Range must be within acceptable bounds
        if range_dollars < self.min_range_dollars:
            return False  # Too narrow - breakout will be too violent
        
        if range_dollars > self.max_range_dollars:
            return False  # Too wide - energy already exhausted
        
        return True

    def calculate_breakeven_level(self, position: dict, current_price: float, 
                                   range_size: float, spread: float = 0.30) -> dict:
        """
        Accelerated Break-Even Check.
        
        When profit reaches 0.8 * Range, move SL to Entry + Spread.
        This protects gains earlier than standard 1.0 ATR breakeven.
        
        Args:
            position: Position dict with entry_price, type, sl
            current_price: Current market price
            range_size: Asian range size (used as ATR proxy)
            spread: Spread cost (default 0.30 for XAUUSD)
            
        Returns:
            Updated position dict
        """
        if position is None:
            return position
        
        # Already at breakeven?
        if position.get('breakeven_active', False):
            return position
        
        # Breakeven trigger = 0.8 * Range
        be_trigger = range_size * self.breakeven_trigger_multiplier
        
        if position['type'] == 'BUY':
            profit = current_price - position['entry_price']
            
            if profit >= be_trigger:
                # Move SL to Entry + Spread (cover the spread cost)
                new_sl = position['entry_price'] + spread
                if position['sl'] < new_sl:
                    position['sl'] = new_sl
                    position['breakeven_active'] = True
        
        elif position['type'] == 'SELL':
            profit = position['entry_price'] - current_price
            
            if profit >= be_trigger:
                # Move SL to Entry - Spread (no spread on sell, so just entry)
                new_sl = position['entry_price']
                if position['sl'] > new_sl:
                    position['sl'] = new_sl
                    position['breakeven_active'] = True
        
        return position
