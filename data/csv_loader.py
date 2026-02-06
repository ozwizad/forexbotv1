import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CSVLoader:
    """
    Loads historical data from CSV files for backtesting.
    Specific format: Date Time;Open;High;Low;Close;Volume (Semicolon separated)
    Format example: 18.01.2010 13:00;143.736;143.785;143.644;143.751;3820
    """
    
    @staticmethod
    def load_data(filepath: str) -> pd.DataFrame:
        logger.info(f"Loading data from {filepath}...")
        
        try:
            if filepath.endswith('.xlsx') or filepath.endswith('.xls'):
                # Load Excel, assuming no header if it fails standard detection or based on debug
                # Debug showed: 2009-05-26 07:00:00  952049  952354 ...
                # This implies NO HEADER.
                df = pd.read_excel(filepath, header=None)
                
                # Assign columns manually based on standard OHLCV order
                # Assuming: Time, Open, High, Low, Close, Volume
                # There are 6 columns in debug output.
                if len(df.columns) >= 5:
                    df.columns = ['time', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]
                else:
                    # Fallback
                    df.columns = ['time', 'open', 'high', 'low', 'close', 'volume'][:len(df.columns)]

                # Convert time
                df['time'] = pd.to_datetime(df['time'])
                
                # Check if prices are scaled (e.g. 952049 instead of 952.049)
                # Strategy works on relativity, but let's check for sanity if needed.
                # User said "Use this CSV... no lookahead bias".
                # User did not ask to normalize. I will keep it raw to be safe, 
                # unless I see obvious issues in results (like 0 trades due to ATR issues).
                # Actually, standard indicators (RSI) are scale invariant.
                # ATR is scale dependent, but SL/TP are defined in ATR terms.
                # So logic holds.
                
            else:
                # Load CSV with semicolon separator
                df = pd.read_csv(filepath, sep=';', names=['time_str', 'open', 'high', 'low', 'close', 'volume'], header=0)
                
                # Parse datetime
                # Format is DD.MM.YYYY HH:MM
                df['time'] = pd.to_datetime(df['time_str'], format='%d.%m.%Y %H:%M')
                
                # Drop string column and reorder
                df.drop('time_str', axis=1, inplace=True)
            
            # Ensure required columns
            required = ['time', 'open', 'high', 'low', 'close']
            if not all(col in df.columns for col in required):
                # Try simple renaming if columns are standard index 0-5
                # But safer to just filter what we have
                pass

            # Standardize
            if 'volume' in df.columns:
                df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
            else:
                 df = df[['time', 'open', 'high', 'low', 'close']]
            
            # Sort by time just in case
            df.sort_values('time', inplace=True)
            df.reset_index(drop=True, inplace=True)
            
            logger.info(f"Loaded {len(df)} rows.")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise e
