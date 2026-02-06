"""
Backtest Runner for XAUUSD H1 Asian Range Breakout Strategy
"""

import sys
import os
import pandas as pd
import logging
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from data.csv_loader import CSVLoader
from strategy.asian_breakout import AsianBreakoutStrategy

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AsianBreakout_Backtest")


def run_backtest():
    # 1. Load Data
    data_file = r"c:\Users\Ozai\Desktop\Klasörler\Protop\XAUUSD_H1.xlsx"
    if not os.path.exists(data_file):
        logger.error(f"File not found: {data_file}")
        return

    logger.info("Loading Data...")
    df = CSVLoader.load_data(data_file)
    
    # 2. Init Strategy
    strategy = AsianBreakoutStrategy()
    
    # 3. Simulation State
    balance = 10000.0
    risk_per_trade = 0.01  # 1%
    
    trade_history = []
    equity_curve = [balance]
    
    # Track open position
    position = None  # {type, entry_price, sl, tp, size, entry_time, time_exit_hour}
    
    # Track whether we've traded today
    last_trade_date = None
    
    # Cache Asian range per day
    asian_range_cache = {}
    
    logger.info("Starting Simulation...")
    
    for i in range(len(df)):
        row = df.iloc[i]
        current_time = row['time']
        current_date = current_time.date()
        current_hour = current_time.hour
        current_close = row['close']
        current_high = row['high']
        current_low = row['low']
        
        # --- Manage Open Position ---
        if position is not None:
            closed = False
            exit_price = None
            reason = ""
            pnl = 0
            
            # Check Time Exit (20:00 UTC)
            if current_hour >= strategy.time_exit_hour:
                exit_price = current_close
                reason = "TIME"
                closed = True
            
            # Check SL/TP
            if not closed:
                if position['type'] == 'BUY':
                    if current_low <= position['sl']:
                        exit_price = position['sl']
                        reason = "SL"
                        closed = True
                    elif current_high >= position['tp']:
                        exit_price = position['tp']
                        reason = "TP"
                        closed = True
                elif position['type'] == 'SELL':
                    if current_high >= position['sl']:
                        exit_price = position['sl']
                        reason = "SL"
                        closed = True
                    elif current_low <= position['tp']:
                        exit_price = position['tp']
                        reason = "TP"
                        closed = True
            
            if closed:
                if position['type'] == 'BUY':
                    pnl = (exit_price - position['entry_price']) * position['size']
                else:
                    pnl = (position['entry_price'] - exit_price) * position['size']
                
                balance += pnl
                trade_history.append({
                    'entry_time': position['entry_time'],
                    'exit_time': current_time,
                    'type': position['type'],
                    'result': reason,
                    'pnl': pnl,
                    'entry': position['entry_price'],
                    'exit': exit_price
                })
                position = None
        
        equity_curve.append(balance)
        
        # --- Check for New Entry ---
        # Only during entry window (07:00 - 14:00 UTC)
        if position is None and strategy.entry_window_start <= current_hour < strategy.entry_window_end:
            # Only one trade per day
            if last_trade_date == current_date:
                continue
            
            # Get Asian range for today (cached)
            if current_date not in asian_range_cache:
                asian_high, asian_low = strategy.get_asian_range(df, current_date)
                asian_range_cache[current_date] = (asian_high, asian_low)
            else:
                asian_high, asian_low = asian_range_cache[current_date]
            
            # Skip if no valid range
            if asian_high is None or asian_low is None:
                continue
            
            # Check range filter
            if not strategy.check_range_filter(asian_high, asian_low):
                continue
            
            range_size = asian_high - asian_low
            
            # BUY: Close above Asian High
            if current_close > asian_high:
                entry_price = current_close
                sl = asian_low
                tp = entry_price + (range_size * strategy.tp_multiplier)
                
                sl_dist = entry_price - sl
                if sl_dist <= 0:
                    continue
                
                risk_amt = balance * risk_per_trade
                size = risk_amt / sl_dist
                
                position = {
                    'type': 'BUY',
                    'entry_price': entry_price,
                    'sl': sl,
                    'tp': tp,
                    'size': size,
                    'entry_time': current_time
                }
                last_trade_date = current_date
            
            # SELL: Close below Asian Low
            elif current_close < asian_low:
                entry_price = current_close
                sl = asian_high
                tp = entry_price - (range_size * strategy.tp_multiplier)
                
                sl_dist = sl - entry_price
                if sl_dist <= 0:
                    continue
                
                risk_amt = balance * risk_per_trade
                size = risk_amt / sl_dist
                
                position = {
                    'type': 'SELL',
                    'entry_price': entry_price,
                    'sl': sl,
                    'tp': tp,
                    'size': size,
                    'entry_time': current_time
                }
                last_trade_date = current_date
    
    # End of Loop - Close any remaining position
    if position is not None:
        exit_price = df.iloc[-1]['close']
        if position['type'] == 'BUY':
            pnl = (exit_price - position['entry_price']) * position['size']
        else:
            pnl = (position['entry_price'] - exit_price) * position['size']
        balance += pnl
        trade_history.append({
            'entry_time': position['entry_time'],
            'exit_time': df.iloc[-1]['time'],
            'type': position['type'],
            'result': 'EOD',
            'pnl': pnl,
            'entry': position['entry_price'],
            'exit': exit_price
        })
    
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
    max_drawdown = drawdown.min()
    
    print("-" * 50)
    print("BACKTEST RESULTS: XAUUSD Asian Range Breakout")
    print("-" * 50)
    print(f"Data Range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {win_rate:.2f}%")
    print(f"Profit Factor:{profit_factor:.2f}")
    print(f"Net PnL:      ${net_pnl:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Final Balance:${balance:.2f}")
    print("-" * 50)
    
    # Trade breakdown
    tp_trades = len(df_trades[df_trades['result'] == 'TP'])
    sl_trades = len(df_trades[df_trades['result'] == 'SL'])
    time_trades = len(df_trades[df_trades['result'] == 'TIME'])
    print(f"TP Exits: {tp_trades} | SL Exits: {sl_trades} | Time Exits: {time_trades}")
    print("-" * 50)


if __name__ == "__main__":
    run_backtest()
