
import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from data.csv_loader import CSVLoader
from strategy.xau_volsnap import XAUVolSnapStrategy
from strategy.interface import Signal
from risk.monitor import RiskMonitor
from risk.adaptive_risk import AdaptiveRiskManager
from utils.costs import apply_entry_cost, apply_exit_cost, calculate_commission
from utils.trailing_stop import manage_trailing_stop

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
    
    # Initialize adaptive risk manager
    risk_manager = AdaptiveRiskManager(base_risk=0.01)
    
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
            # Apply trailing stop management
            pos = manage_trailing_stop(pos, current_high, current_low, current_atr)
            
            pdl = 0
            closed = False
            reason = ""
            
            if pos['type'] == 'BUY':
                if current_low <= pos['sl']:
                    # SL Hit - apply exit costs
                    exit_price = apply_exit_cost(pos['sl'], 'BUY')
                    pdl = (exit_price - pos['entry_price']) * pos['size']
                    # Subtract commission
                    pdl -= calculate_commission(pos['size'])
                    closed = True
                    reason = "SL"
                elif current_high >= pos['tp']:
                    # TP Hit - apply exit costs
                    exit_price = apply_exit_cost(pos['tp'], 'BUY')
                    pdl = (exit_price - pos['entry_price']) * pos['size']
                    # Subtract commission
                    pdl -= calculate_commission(pos['size'])
                    closed = True
                    reason = "TP"
                    
            elif pos['type'] == 'SELL':
                if current_high >= pos['sl']:
                    # SL Hit - apply exit costs
                    exit_price = apply_exit_cost(pos['sl'], 'SELL')
                    pdl = (pos['entry_price'] - exit_price) * pos['size']
                    # Subtract commission
                    pdl -= calculate_commission(pos['size'])
                    closed = True
                    reason = "SL"
                elif current_low <= pos['tp']:
                    # TP Hit - apply exit costs
                    exit_price = apply_exit_cost(pos['tp'], 'SELL')
                    pdl = (pos['entry_price'] - exit_price) * pos['size']
                    # Subtract commission
                    pdl -= calculate_commission(pos['size'])
                    closed = True
                    reason = "TP"
            
            if closed:
                balance += pdl
                # Record result for adaptive risk manager
                risk_manager.record_result(pdl)
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
                # Get adaptive risk (may be 0 if drawdown too high)
                risk_per_trade = risk_manager.get_risk(balance)
                
                if risk_per_trade > 0:
                    # Calculate Size
                    risk_amt = balance * risk_per_trade
                    
                    # FIXED: Improved Risk/Reward Ratio
                    # SL Distance: 1.5 * ATR (was 1.2)
                    # TP Distance: 3.0 * ATR (was 1.0)
                    # This gives minimum 1:2 Risk/Reward ratio
                    sl_dist = current_atr * 1.5
                    
                    if sl_dist == 0:
                        continue
                        
                    # Size = Risk / Distance
                    size = risk_amt / sl_dist
                    
                    if signal == Signal.BUY:
                        # Apply entry costs (spread + slippage)
                        entry_price = apply_entry_cost(current_close, 'BUY')
                        sl = entry_price - (current_atr * 1.5)
                        tp = entry_price + (current_atr * 3.0)
                        
                        positions.append({
                            'type': 'BUY',
                            'entry_price': entry_price,
                            'sl': sl,
                            'tp': tp,
                            'size': size,
                            'entry_time': current_time
                        })
                        
                    elif signal == Signal.SELL:
                        # Apply entry costs (spread + slippage)
                        entry_price = apply_entry_cost(current_close, 'SELL')
                        sl = entry_price + (current_atr * 1.5)
                        tp = entry_price - (current_atr * 3.0)
                        
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
    
    # Enhanced Diagnostics
    # Sharpe Ratio (approximate using returns)
    returns = equity_series.pct_change().dropna()
    if len(returns) > 0 and returns.std() > 0:
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252 * 24)  # Annualized for hourly data
    else:
        sharpe_ratio = 0.0
    
    # Calmar Ratio (Return / Max Drawdown)
    total_return = (balance - 10000.0) / 10000.0 * 100
    if abs(max_drawdown) > 0:
        calmar_ratio = total_return / abs(max_drawdown)
    else:
        calmar_ratio = 0.0
    
    # Average Win/Loss
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
    
    print("-" * 50)
    print("BACKTEST RESULTS: XAUUSD Volatility Snap v2")
    print("(With Adaptive Risk, Costs, Trailing Stops)")
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

if __name__ == "__main__":
    run_backtest()
