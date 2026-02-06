"""
Confluence Filter
Multi-factor signal confirmation to reduce false entries.
Requires at least 2 out of 3 confirmations for trade entry.
"""

import numpy as np


def ema(data, period):
    """
    Calculate Exponential Moving Average.
    
    Args:
        data: Array or series of price data
        period: EMA period
        
    Returns:
        Array of EMA values
    """
    multiplier = 2 / (period + 1)
    result = np.zeros(len(data))
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
    return result


def rsi(data, period=14):
    """
    Calculate Relative Strength Index for the most recent value.
    
    Args:
        data: Array or series of price data
        period: RSI period (default 14)
        
    Returns:
        RSI value (0-100)
    """
    if len(data) < period + 1:
        return 50  # Neutral if insufficient data
    
    deltas = np.diff(data[-(period+1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def confluence_check(df, i, direction):
    """
    Multi-factor confluence filter.
    Requires at least 2 out of 3 confirmations.
    
    Checks:
    1. Trend Filter: EMA 50 vs EMA 200 alignment
    2. RSI Filter: Not in extreme overbought/oversold zones
    3. Volatility Regime: ATR in normal range (not extreme volatility)
    
    Args:
        df: DataFrame with price data and indicators
        i: Current index
        direction: 'BUY' or 'SELL'
        
    Returns:
        True if at least 2 out of 3 confirmations pass, False otherwise
    """
    row = df.iloc[i]
    score = 0
    
    # 1. Trend Filter: EMA 50 vs EMA 200
    if 'EMA_50' in df.columns and 'EMA_200' in df.columns:
        if direction == 'BUY' and row['EMA_50'] > row['EMA_200']:
            score += 1
        elif direction == 'SELL' and row['EMA_50'] < row['EMA_200']:
            score += 1
    
    # 2. RSI Filter: Not in extreme zones (avoid extremes)
    if 'RSI' in df.columns:
        if direction == 'BUY' and 30 < row['RSI'] < 70:
            score += 1
        elif direction == 'SELL' and 30 < row['RSI'] < 70:
            score += 1
    
    # 3. Volatility Regime: Normal range (0.5x to 1.5x average ATR)
    if 'ATR' in df.columns and i >= 50:
        current_atr = row['ATR']
        avg_atr = df['ATR'].iloc[i-50:i].mean()
        if avg_atr > 0:
            vol_ratio = current_atr / avg_atr
            if 0.5 < vol_ratio < 1.5:
                score += 1
    
    # Require at least 2 out of 3 confirmations
    return score >= 2
