import pandas as pd
import numpy as np

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """
    Calculates Exponential Moving Average.
    """
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates Relative Strength Index.
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    # Smoothed version (Wilder's Smoothing) - Standard for Trading
    # RSI typically uses Wilder smoothing, which is approximately alpha = 1/period
    # But for simplicity and common pandas usage, we can stick to standard EWMA or simple Rolling
    # To match standard MT5 RSI more closely, we often use Wilder's.
    # Let's use the standard Wilder's smoothing logic:
    # avg_u[i] = (avg_u[i-1]*(n-1) + u[i]) / n
    
    # Re-implmenting for Wilder's (more accurate for trading):
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculates Average True Range.
    Requires DataFrame with 'high', 'low', 'close' columns.
    """
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    # ATR is usually an RMA (Rolling Moving Average) or Wilder's Smoothing
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def add_indicators(df: pd.DataFrame, ema_fast: int, ema_slow: int, rsi_period: int, atr_period: int) -> pd.DataFrame:
    """
    Enriches the dataframe with technical indicators.
    """
    df = df.copy()
    
    # Ensure columns exist
    required_cols = {'close', 'high', 'low'}
    if not required_cols.issubset(df.columns):
         # Try case insensitive mapping if needed, but assuming lowercase for internal use
         pass

    df[f'EMA_{ema_fast}'] = calculate_ema(df['close'], ema_fast)
    df[f'EMA_{ema_slow}'] = calculate_ema(df['close'], ema_slow)
    df['RSI'] = calculate_rsi(df['close'], rsi_period)
    df['ATR'] = calculate_atr(df, atr_period)
    
    return df
