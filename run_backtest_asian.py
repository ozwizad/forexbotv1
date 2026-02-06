"""
Backtest Runner for XAUUSD H1 Asian Range Breakout Strategy
"""

import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from data.csv_loader import CSVLoader
from strategy.asian_breakout import AsianBreakoutStrategy
from strategy.confluence import ema, rsi, confluence_check
from risk.adaptive_risk import AdaptiveRiskManager
from utils.costs import apply_entry_cost, apply_exit_cost, calculate_commission
from utils.trailing_stop import manage_trailing_stop

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AsianBreakout_Backtest")

# Constants for metrics calculation
TRADING_DAYS_PER_YEAR = 252
HOURS_PER_DAY = 24


def run_backtest():
    # 1. Load Data
    data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "XAUUSD_H1.xlsx")
    if not os.path.exists(data_file):
        logger.error(f"File not found: {data_file}")
        return

    logger.info("Loading Data...")
    df = CSVLoader.load_data(data_file)
    
    # 2. Init Strategy
    strategy = AsianBreakoutStrategy()
    
    # Add confluence indicators (EMA, RSI, ATR)
    logger.info("Calculating Indicators...")
    # Calculate EMA 50 and 200
    df['EMA_50'] = ema(df['close'].values, 50)
    df['EMA_200'] = ema(df['close'].values, 200)
    
    # Calculate RSI
    df['RSI'] = df['close'].rolling(15).apply(lambda x: rsi(x.values, 14), raw=False)
    
    # Calculate ATR if not already present (needed for trailing stops)
    if 'ATR' not in df.columns:
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift())
        df['low_close'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['ATR'] = df['tr'].rolling(14).mean()
        df.drop(['high_low', 'high_close', 'low_close', 'tr'], axis=1, inplace=True)
    
    # Drop NaN rows from indicator calculations
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    # 3. Simulation State
    balance = 10000.0
    
    # Initialize adaptive risk manager
    risk_manager = AdaptiveRiskManager(base_risk=0.01)
    
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
        current_atr = row['ATR']
        
        # --- Manage Open Position ---
        if position is not None:
            # Apply trailing stop management
            position = manage_trailing_stop(position, current_high, current_low, current_atr)
            
            closed = False
            exit_price = None
            reason = ""
            pnl = 0
            
            # Check Time Exit (20:00 UTC)
            if current_hour >= strategy.time_exit_hour:
                exit_price = apply_exit_cost(current_close, position['type'])
                reason = "TIME"
                closed = True
            
            # Check SL/TP
            if not closed:
                if position['type'] == 'BUY':
                    if current_low <= position['sl']:
                        exit_price = apply_exit_cost(position['sl'], 'BUY')
                        reason = "SL"
                        closed = True
                    elif current_high >= position['tp']:
                        exit_price = apply_exit_cost(position['tp'], 'BUY')
                        reason = "TP"
                        closed = True
                elif position['type'] == 'SELL':
                    if current_high >= position['sl']:
                        exit_price = apply_exit_cost(position['sl'], 'SELL')
                        reason = "SL"
                        closed = True
                    elif current_low <= position['tp']:
                        exit_price = apply_exit_cost(position['tp'], 'SELL')
                        reason = "TP"
                        closed = True
            
            if closed:
                if position['type'] == 'BUY':
                    pnl = (exit_price - position['entry_price']) * position['size']
                else:
                    pnl = (position['entry_price'] - exit_price) * position['size']
                
                # Subtract commission
                pnl -= calculate_commission(position['size'])
                
                balance += pnl
                # Record result for adaptive risk manager
                risk_manager.record_result(pnl)
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
                # Check confluence filter
                if not confluence_check(df, i, 'BUY'):
                    continue
                
                # Get adaptive risk
                risk_per_trade = risk_manager.get_risk(balance)
                if risk_per_trade == 0:
                    continue
                
                entry_price = apply_entry_cost(current_close, 'BUY')
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
                # Check confluence filter
                if not confluence_check(df, i, 'SELL'):
                    continue
                
                # Get adaptive risk
                risk_per_trade = risk_manager.get_risk(balance)
                if risk_per_trade == 0:
                    continue
                
                entry_price = apply_entry_cost(current_close, 'SELL')
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
        exit_price = apply_exit_cost(df.iloc[-1]['close'], position['type'])
        if position['type'] == 'BUY':
            pnl = (exit_price - position['entry_price']) * position['size']
        else:
            pnl = (position['entry_price'] - exit_price) * position['size']
        pnl -= calculate_commission(position['size'])
        balance += pnl
        risk_manager.record_result(pnl)
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
    
    # Enhanced Diagnostics
    returns = equity_series.pct_change().dropna()
    if len(returns) > 0 and returns.std() > 0:
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(TRADING_DAYS_PER_YEAR * HOURS_PER_DAY)
    else:
        sharpe_ratio = 0.0
    
    total_return = (balance - 10000.0) / 10000.0 * 100
    if abs(max_drawdown) > 0:
        calmar_ratio = total_return / abs(max_drawdown)
    else:
        calmar_ratio = 0.0
    
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
    
    print("-" * 50)
    print("BACKTEST RESULTS: XAUUSD Asian Range Breakout v2")
    print("(With Adaptive Risk, Costs, Trailing Stops, Confluence)")
    print("-" * 50)
    print(f"Data Range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {win_rate:.2f}%")
    print(f"Profit Factor:{profit_factor:.2f}")
    print(f"Net PnL:      ${net_pnl:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Final Balance:${balance:.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print("-" * 50)
    print("Enhanced Metrics:")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Calmar Ratio: {calmar_ratio:.2f}")
    print(f"Avg Win:      ${avg_win:.2f}")
    print(f"Avg Loss:     ${avg_loss:.2f}")
    print(f"Risk/Reward:  1:{(avg_win/abs(avg_loss)):.2f}" if avg_loss != 0 else "Risk/Reward:  N/A")
    print("-" * 50)
    
    # Trade breakdown
    tp_trades = len(df_trades[df_trades['result'] == 'TP'])
    sl_trades = len(df_trades[df_trades['result'] == 'SL'])
    time_trades = len(df_trades[df_trades['result'] == 'TIME'])
    print(f"TP Exits: {tp_trades} | SL Exits: {sl_trades} | Time Exits: {time_trades}")
    print("-" * 50)


if __name__ == "__main__":
    run_backtest()
