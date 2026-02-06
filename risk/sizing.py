import math
from typing import Tuple

def calculate_position_size(
    account_balance: float,
    risk_pct: float,
    sl_distance_points: float,
    tick_value: float,
    point_value: float,
    lot_step: float = 0.01,
    min_lot: float = 0.01,
    max_lot: float = 100.0
) -> float:
    """
    Calculates the detailed position size based on fixed fractional risk.
    
    Args:
        account_balance: Current account balance (or equity).
        risk_pct: Risk percentage (e.g., 0.01 for 1%).
        sl_distance_points: Distance to Stop Loss in POINTS.
        tick_value: Value of one tick for 1.0 lot (in account currency).
        point_value: Size of one point (e.g. 0.00001 for 5-digit broker). 
                     Note: tick_value usually corresponds to tick_size (points).
                     Formula: Risk_Amount = Volume * SL_Points * Tick_Value_Per_Point
    
    Returns:
        float: Calculated lot size valid for the broker.
    """
    if sl_distance_points <= 0:
        return 0.0

    risk_amount = account_balance * risk_pct
    
    # Calculate Raw Lot Size
    # Formula derived: Risk = Lots * SL_Points * Profit_Per_Point_Per_1Lot
    # Note on MT5: tick_value is usually for 1 lot movement of 1 tick.
    # We assume 'tick_value' provided here is "Profit for 1 lot for 1 point movement".
    # If tick_value is per minimum tick (e.g. 0.1 points), adjustment is needed.
    # Standard robust formula assuming tick_value is correctly normalized to Points:
    if tick_value <= 0:
        return 0.0
        
    raw_lots = risk_amount / (sl_distance_points * tick_value)
    
    # Normalize to step
    lots = math.floor(raw_lots / lot_step) * lot_step
    
    # Clamp
    lots = max(min_lot, min(lots, max_lot))
    
    # Final safety check: round to avoid float precision issues (e.g. 0.120000001)
    lots = round(lots, 2) 
    
    return lots
