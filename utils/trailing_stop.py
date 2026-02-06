"""
Trailing Stop Management
Implements breakeven and trailing stop mechanisms to protect profits.
"""

# Trailing stop configuration
BREAKEVEN_ATR_MULT = 1.0   # Move to breakeven when profit >= 1×ATR
TRAILING_ATR_MULT = 1.5    # Start trailing when profit >= 1.5×ATR
TRAILING_DISTANCE_ATR = 1.0  # Trail stop at 1×ATR behind price


def manage_trailing_stop(position, current_high, current_low, current_atr):
    """
    Manage trailing stop for an open position.
    
    Logic:
    - Breakeven: When profit >= 1×ATR, move SL to entry (protect capital)
    - Trailing: When profit >= 1.5×ATR, trail SL at 1×ATR behind price
    
    Args:
        position: Dictionary with position details
                  {type, entry_price, sl, tp, size, entry_time}
        current_high: Current candle high
        current_low: Current candle low
        current_atr: Current ATR value
        
    Returns:
        Updated position dictionary with adjusted SL
    """
    if position['type'] == 'BUY':
        # For long positions, unrealized profit based on high
        unrealized = current_high - position['entry_price']
        
        # Breakeven: Move SL to entry when 1×ATR in profit
        if unrealized >= current_atr * BREAKEVEN_ATR_MULT:
            new_sl = max(position['sl'], position['entry_price'])
            position['sl'] = new_sl
        
        # Trailing: When 1.5×ATR in profit, trail at 1×ATR behind
        if unrealized >= current_atr * TRAILING_ATR_MULT:
            trail_sl = current_high - (current_atr * TRAILING_DISTANCE_ATR)
            position['sl'] = max(position['sl'], trail_sl)
    
    elif position['type'] == 'SELL':
        # For short positions, unrealized profit based on low
        unrealized = position['entry_price'] - current_low
        
        # Breakeven: Move SL to entry when 1×ATR in profit
        if unrealized >= current_atr * BREAKEVEN_ATR_MULT:
            new_sl = min(position['sl'], position['entry_price'])
            position['sl'] = new_sl
        
        # Trailing: When 1.5×ATR in profit, trail at 1×ATR behind
        if unrealized >= current_atr * TRAILING_ATR_MULT:
            trail_sl = current_low + (current_atr * TRAILING_DISTANCE_ATR)
            position['sl'] = min(position['sl'], trail_sl)
    
    return position
