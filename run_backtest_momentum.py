"""
Backtest Runner for XAUUSD H1 Momentum Continuation Strategy
"""

import sys
import os
import pandas as pd
import numpy as np
import logging

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from data.csv_loader import CSVLoader
from strategy.momentum_continuation import MomentumContinuationStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MomentumContinuation_Backtest")


def run_backtest():
    # 1. Load Data
    data_file = r"c:\Users\Ozai\Desktop\Klasörler\Protop\XAUUSD_H1.xlsx"
    if not os.path.exists(data_file):
        logger.error(f"File not found: {data_file}")
        return

    logger.info("Loading Data...")
    df = CSVLoader.load_data(data_file)
    
    # 2. Init Strategy
    strategy = MomentumContinuationStrategy()
    logger.info("Calculating Indicators...")
    df = strategy.prepare_data(df)
    
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    # 3. Simulation State
    balance = 10000.0
    risk_per_trade = 0.01
    
    trade_history = []
    equity_curve = [balance]
    
    position = None
    session_opens = {}
    last_trade_session = None
    
    logger.info("Starting Simulation...")
    
    for i in range(len(df)):
        row = df.iloc[i]
        current_time = row['time']
        current_date = row['date']
        current_hour = row['hour']
        current_close = row['close']
        current_high = row['high']
        current_low = row['low']
        current_atr = row['ATR']
        current_body = row['candle_body']
        
        # Determine Session Opens
        london_key = (current_date, 'london')
        if london_key not in session_opens and current_hour >= strategy.london_open_hour:
            session_opens[london_key] = current_close
        
        ny_key = (current_date, 'ny')
        if ny_key not in session_opens and current_hour >= strategy.ny_open_hour:
            session_opens[ny_key] = current_close
        
        # Manage Open Position
        if position is not None:
            closed = False
            exit_price = None
            reason = ""
            pnl = 0
            
            bars_held = i - position['entry_bar_idx']
            if bars_held >= strategy.time_exit_bars:
                exit_price = current_close
                reason = "TIME"
                closed = True
            
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
                    'exit': exit_price,
                    'duration_bars': bars_held
                })
                position = None
        
        equity_curve.append(balance)
        
        # Check for New Entry
        if position is not None:
            continue
        if current_hour < strategy.london_open_hour or current_hour >= strategy.session_end_hour:
            continue
        
        # Determine session
        if current_hour >= strategy.ny_open_hour:
            session_key = (current_date, 'ny')
        else:
            session_key = (current_date, 'london')
        
        if last_trade_session == session_key:
            continue
        
        session_open = session_opens.get(session_key)
        if session_open is None:
            continue
        
        displacement = current_close - session_open
        displacement_abs = abs(displacement)
        
        # Check displacement >= 2x ATR
        if displacement_abs < strategy.displacement_atr_mult * current_atr:
            continue
        
        # Check strong candle: body >= 0.6x ATR
        if current_body < strategy.strong_candle_mult * current_atr:
            continue
        
        # Trade in direction of momentum
        if displacement > 0:
            # Price moved UP → BUY (follow momentum)
            entry_price = current_close
            sl = entry_price - (strategy.sl_atr_mult * current_atr)
            tp = entry_price + (strategy.tp_atr_mult * current_atr)
            
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
                'entry_time': current_time,
                'entry_bar_idx': i
            }
            last_trade_session = session_key
            
        else:
            # Price moved DOWN → SELL (follow momentum)
            entry_price = current_close
            sl = entry_price + (strategy.sl_atr_mult * current_atr)
            tp = entry_price - (strategy.tp_atr_mult * current_atr)
            
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
                'entry_time': current_time,
                'entry_bar_idx': i
            }
            last_trade_session = session_key
    
    # Close remaining position
    if position is not None:
        exit_price = df.iloc[-1]['close']
        bars_held = len(df) - 1 - position['entry_bar_idx']
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
            'exit': exit_price,
            'duration_bars': bars_held
        })
    
    # DIAGNOSTICS
    df_trades = pd.DataFrame(trade_history)
    
    if len(df_trades) == 0:
        print("No trades generated.")
        return
    
    total_trades = len(df_trades)
    wins = df_trades[df_trades['pnl'] > 0]
    losses = df_trades[df_trades['pnl'] <= 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / total_trades * 100
    
    gross_profit = wins['pnl'].sum()
    gross_loss = abs(losses['pnl'].sum())
    
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else 999.0
    net_pnl = df_trades['pnl'].sum()
    
    equity_series = pd.Series(equity_curve)
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    first_date = df['time'].iloc[0]
    last_date = df['time'].iloc[-1]
    years = (last_date - first_date).days / 365.25
    
    trades_per_year = total_trades / years if years > 0 else 0
    avg_duration = df_trades['duration_bars'].mean()
    expectancy = net_pnl / total_trades if total_trades > 0 else 0
    
    tp_trades = len(df_trades[df_trades['result'] == 'TP'])
    sl_trades = len(df_trades[df_trades['result'] == 'SL'])
    time_trades = len(df_trades[df_trades['result'] == 'TIME'])
    
    under_sampled = total_trades < 200
    
    print("=" * 60)
    print("BACKTEST RESULTS: XAUUSD Momentum Continuation")
    print("=" * 60)
    print(f"Data Range:       {first_date.date()} to {last_date.date()} ({years:.1f} years)")
    print("-" * 60)
    print(f"Total Trades:     {total_trades}")
    print(f"Trades/Year:      {trades_per_year:.1f}")
    print(f"Win Rate:         {win_rate:.2f}% ({win_count}W / {loss_count}L)")
    print(f"Profit Factor:    {profit_factor:.2f}")
    print(f"Net PnL:          ${net_pnl:.2f}")
    print(f"Expectancy/Trade: ${expectancy:.2f}")
    print(f"Max Drawdown:     {max_drawdown:.2f}%")
    print(f"Final Balance:    ${balance:.2f}")
    print("-" * 60)
    print(f"Avg Duration:     {avg_duration:.1f} bars (hours)")
    print(f"Exit Breakdown:   TP: {tp_trades} | SL: {sl_trades} | Time: {time_trades}")
    print("=" * 60)
    
    if under_sampled:
        print("⚠️  WARNING: Total trades < 200. STATISTICALLY UNDER-SAMPLED.")
    else:
        print("✓  Sample size adequate (>= 200 trades).")
    
    # Target checks
    print("-" * 60)
    if profit_factor >= 1.2:
        print(f"✓  Profit Factor {profit_factor:.2f} >= 1.2 TARGET MET")
    else:
        print(f"✗  Profit Factor {profit_factor:.2f} < 1.2 TARGET NOT MET")
    
    if max_drawdown > -25:
        print(f"✓  Max Drawdown {max_drawdown:.2f}% > -25% TARGET MET")
    else:
        print(f"✗  Max Drawdown {max_drawdown:.2f}% <= -25% TARGET NOT MET")
    
    print("=" * 60)


if __name__ == "__main__":
    run_backtest()
