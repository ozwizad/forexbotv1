import sys
from pathlib import Path
import logging
import pandas as pd

# Add Project Root to Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config import settings
from utils.logging import setup_logging
from data.csv_loader import CSVLoader
from data.indicators import add_indicators
from strategy.logic import EMATrendFollower, Signal

def run_signal_check():
    setup_logging(project_root / "logs", "INFO")
    logger = logging.getLogger("BacktestStep1")
    
    csv_path = project_root / "data/historical/EURUSD_H1.csv"
    
    # 1. Load Data
    df = CSVLoader.load_data(str(csv_path))
    
    # 2. Add Indicators
    logger.info("Computing indicators...")
    df = add_indicators(
        df, 
        settings.EMA_FAST, 
        settings.EMA_SLOW, 
        settings.RSI_PERIOD, 
        settings.ATR_PERIOD
    )
    
    # 3. Iterate and Check Signals
    logger.info("Running Strategy Simulation (Signal Check)...")
    strategy = EMATrendFollower()
    
    signals_detected = 0
    max_signals_to_log = 10
    
    # Strategy needs at least 200 bars for EMA200
    start_index = 200
    
    for i in range(start_index, len(df)):
        # Determine slice for the strategy
        # We need historical context. Strategy logic typically looks at df.iloc[-1] as current.
        # But for backtest speed, passing the whole DF and an index is faster, 
        # OR slicing.
        # The logic.py 'categorize_signal' takes a DataFrame and uses iloc[-1], -2, -3.
        # So we pass a slice ending at 'i'.
        
        # Optimization: Passing a small rolling window frame is inefficient in Python loop but simplest for reusing logic.
        # We pass df.iloc[i-500:i+1] to ensure enough data for lookbacks if logic changes, 
        # but logic currently only looks back 3 candles + indicators (which are pre-calculated).
        # Actually logic needs row i, i-1, i-2 checking indicator columns. 
        # Since indicators are pre-calculated in Step 2, we just need to pass the slice so iloc[-1] is row i.
        
        window = df.iloc[i-20:i+1] # Small window is enough since indicators are already there
        
        sig = strategy.categorize_signal(window)
        
        if sig != Signal.HOLD:
            signals_detected += 1
            current_bar = df.iloc[i]
            
            if signals_detected <= max_signals_to_log:
                logger.info(f"SIGNAL DETECTED [{signals_detected}]: {current_bar['time']} | {sig.value} | Price {current_bar['close']:.5f} | EMA50 {current_bar['EMA_50']:.5f} | EMA200 {current_bar['EMA_200']:.5f} | RSI {current_bar['RSI']:.2f}")

    logger.info("="*40)
    logger.info(f"Total Signals Detected: {signals_detected}")
    logger.info(f"Total Bars Processed: {len(df) - start_index}")
    logger.info("="*40)

if __name__ == "__main__":
    run_signal_check()
