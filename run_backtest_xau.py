
import sys
import os
import pandas as pd
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from data.csv_loader import CSVLoader
from strategy.xau_volsnap import XAUVolSnapStrategy
from strategy.interface import Signal
from risk.monitor import RiskMonitor

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("XAU_Backtest")

def run_backtest():
    # 1. Load Data
    data_file = r"c:\Users\Ozai\Desktop\Klasörler\Protop\XAUUSD_H1.xlsx"
    if not os.path.exists(data_file):
        logger.error(f"File not found: {data_file}")
        return

    logger.info("Loading Data...")
    df = CSVLoader.load_data(data_file)
    
    # 2. Init Strategy
    strategy = XAUVolSnapStrategy()
    logger.info("Calculating Indicators...")
    df = strategy.prepare_data(df)
    
    # Drops NaNs from indicators
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    # 3. Simulation Loop
    logger.info("Starting Simulation...")
    
    balance = 10000.0
    equity = 10000.0
    positions = [] # List of dicts: {type, entry_price, sl, tp, size, entry_time}
    trade_history = []
    
    risk_per_trade = 0.01 # 1%
    
    # For reporting
    equity_curve = [10000.0]
    
    # Iterate
    # We need prev_row for setup, row for confirmation/entry
    # So we iterate from index 1
    
    for i in range(1, len(df)):
        prev_row = df.iloc[i-1]
        row = df.iloc[i]
        
        current_time = row['time']
        current_close = row['close']
        current_low = row['low']
        current_high = row['high']
        current_atr = row['ATR']
        
        # --- Manage Open Positions (Check SL/TP) ---
        active_positions = []
        for pos in positions:
            pdl = 0
            closed = False
            reason = ""
            
            if pos['type'] == 'BUY':
                if current_low <= pos['sl']:
                    # SL Hit
                    exit_price = pos['sl'] # Assuming no slippage as per req
                    pdl = (exit_price - pos['entry_price']) * pos['size']
                    closed = True
                    reason = "SL"
                elif current_high >= pos['tp']:
                    # TP Hit
                    exit_price = pos['tp']
                    pdl = (exit_price - pos['entry_price']) * pos['size']
                    closed = True
                    reason = "TP"
                    
            elif pos['type'] == 'SELL':
                if current_high >= pos['sl']:
                    # SL Hit
                    exit_price = pos['sl']
                    pdl = (pos['entry_price'] - exit_price) * pos['size']
                    closed = True
                    reason = "SL"
                elif current_low <= pos['tp']:
                    # TP Hit
                    exit_price = pos['tp']
                    pdl = (pos['entry_price'] - exit_price) * pos['size']
                    closed = True
                    reason = "TP"
            
            if closed:
                balance += pdl
                trade_history.append({
                    'entry_time': pos['entry_time'],
                    'exit_time': current_time,
                    'type': pos['type'],
                    'result': reason,
                    'pnl': pdl,
                    'entry': pos['entry_price'],
                    'exit': exit_price
                })
            else:
                active_positions.append(pos)
        
        positions = active_positions
        
        # Update Equity (approximate with close)
        # Note: req says "No slippage, Market execution at candle close"
        # We process exits on the candle itself (High/Low)
        # We process Entries at CLOSE of confirmation
        
        current_equity = balance
        # Add unrealized PnL ?? For speed, simple equity curve usually on closed balance
        # or simplified. Let's stick to Balance for the curve steps or calculate floating.
        # User asked for "Equity curve summary"
        equity_curve.append(balance)
        
        # --- Check for New Signals ---
        # "Max 1 open position"
        if len(positions) == 0:
            signal = strategy.categorize_signal(row, prev_row)
            
            if signal != Signal.HOLD:
                # Calculate Size
                # Risk 1% of Balance
                risk_amt = balance * risk_per_trade
                
                # SL Distance
                # Buy: Entry - SL
                # Sell: SL - Entry
                # Strategy defines SL as Entry +/- 1.2 * ATR
                sl_dist = current_atr * 1.2
                
                if sl_dist == 0:
                    continue
                    
                # Size = Risk / Distance
                # NOTE: XAUUSD contract size usually 100 or 1 etc.
                # Assuming standard lot = 100 oz? or just raw price diff logic?
                # User says "1% risk per trade".
                # PnL = (Exit - Entry) * Size
                # Risk = (Entry - SL) * Size = sl_dist * Size
                # Size = Risk / sl_dist
                size = risk_amt / sl_dist
                
                if signal == Signal.BUY:
                    entry_price = current_close
                    sl = entry_price - (current_atr * 1.2)
                    tp = entry_price + (current_atr * 1.0)
                    
                    positions.append({
                        'type': 'BUY',
                        'entry_price': entry_price,
                        'sl': sl,
                        'tp': tp,
                        'size': size,
                        'entry_time': current_time
                    })
                    
                elif signal == Signal.SELL:
                    entry_price = current_close
                    sl = entry_price + (current_atr * 1.2)
                    tp = entry_price - (current_atr * 1.0)
                    
                    positions.append({
                        'type': 'SELL',
                        'entry_price': entry_price,
                        'sl': sl,
                        'tp': tp,
                        'size': size,
                        'entry_time': current_time
                    })

    # End of Loop
    
    # Stats
    df_trades = pd.DataFrame(trade_history)
    
    if len(df_trades) == 0:
        print("No trades generated.")
        return

    total_trades = len(df_trades)
    wins = df_trades[df_trades['pnl'] > 0]
    losses = df_trades[df_trades['pnl'] <= 0]
    
    win_rate = len(wins) / total_trades * 100
    gross_profit = wins['pnl'].sum()
    gross_loss = abs(losses['pnl'].sum())
    
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else 999.0
    net_pnl = df_trades['pnl'].sum()
    
    # Drawdown
    equity_series = pd.Series(equity_curve)
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min() # Negative value
    
    print("-" * 40)
    print("BACKTEST RESULTS: XAUUSD Volatility Snap v1")
    print("-" * 40)
    print(f"Data Range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {win_rate:.2f}%")
    print(f"Profit Factor:{profit_factor:.2f}")
    print(f"Net PnL:      ${net_pnl:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Final Balance:${balance:.2f}")
    print("-" * 40)

if __name__ == "__main__":
    run_backtest()
