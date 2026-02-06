"""
Trading Cost Model
Applies realistic spreads, slippage, and commissions to backtest simulations.
Essential for accurate performance estimation.
"""

# XAUUSD (Gold) trading costs
SPREAD_XAU = 0.30       # $0.30/oz typical spread
SLIPPAGE_XAU = 0.10     # $0.10/oz average slippage
COMMISSION_PER_LOT = 7.0  # $7 round-trip commission per standard lot


def apply_entry_cost(entry_price, direction):
    """
    Apply spread and slippage costs to entry price.
    
    For BUY orders: price is increased (you pay the ask)
    For SELL orders: price is decreased (you receive the bid)
    
    Args:
        entry_price: Raw entry price from candle
        direction: 'BUY' or 'SELL'
        
    Returns:
        Adjusted entry price after costs
    """
    half_cost = (SPREAD_XAU + SLIPPAGE_XAU) / 2
    
    if direction == 'BUY':
        return entry_price + half_cost
    else:
        return entry_price - half_cost


def apply_exit_cost(exit_price, direction):
    """
    Apply spread and slippage costs to exit price.
    
    For BUY positions (closing with SELL): price is decreased
    For SELL positions (closing with BUY): price is increased
    
    Args:
        exit_price: Raw exit price from candle
        direction: Original position direction ('BUY' or 'SELL')
        
    Returns:
        Adjusted exit price after costs
    """
    half_cost = (SPREAD_XAU + SLIPPAGE_XAU) / 2
    
    if direction == 'BUY':
        return exit_price - half_cost
    else:
        return exit_price + half_cost


def calculate_commission(size):
    """
    Calculate commission based on position size.
    
    Args:
        size: Position size
        
    Returns:
        Commission cost in dollars
    """
    # Simple lot-based commission
    # Assuming size represents units, adjust based on lot calculation
    # For XAUUSD, typically 100 oz = 1 lot
    lots = max(size / 100, 0.01)
    return COMMISSION_PER_LOT * lots
