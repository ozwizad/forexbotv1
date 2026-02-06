import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DataLoader:
    """
    Handles data retrieval from MT5.
    """
    def __init__(self):
        self.connected = False

    def connect(self) -> bool:
        """
        Ensures connection to MT5 terminal.
        """
        if not mt5.initialize():
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        self.connected = True
        return True

    def get_historical_data(self, symbol: str, timeframe: int, num_candles: int = 1000) -> Optional[pd.DataFrame]:
        """
        Fetches 'num_candles' of historical data for technical analysis warming.
        """
        if not self.connected:
            if not self.connect():
                return None

        # Copy rates
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
        
        if rates is None or len(rates) == 0:
            logger.error(f"Failed to get rates for {symbol}")
            return None

        # Convert to Pandas DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Rename columns to standard lowercase
        df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'tick_volume': 'volume',
            'spread': 'spread',
            'real_volume': 'real_volume'
        }, inplace=True)
        
        return df[['time', 'open', 'high', 'low', 'close', 'volume', 'spread']]

    def get_latest_candle(self, symbol: str, timeframe: int) -> Optional[dict]:
        """
        Gets the single most recent candle (for live monitoring).
        """
        df = self.get_historical_data(symbol, timeframe, num_candles=1)
        if df is not None and not df.empty:
            return df.iloc[-1].to_dict()
        return None
