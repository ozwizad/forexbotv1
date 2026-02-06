"""
Backtest Runner for XAUUSD H1 Exhaustion Fade Strategy
With enhanced diagnostics as requested.
"""

import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from data.csv_loader import CSVLoader
from strategy.exhaustion_fade import ExhaustionFadeStrategy
from strategy.confluence import ema, rsi, confluence_check
from risk.adaptive_risk import AdaptiveRiskManager
from utils.costs import apply_entry_cost, apply_exit_cost, calculate_commission
from utils.trailing_stop import manage_trailing_stop

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ExhaustionFade_Backtest")

# Constants for metrics and filters
TRADING_DAYS_PER_YEAR = 252
HOURS_PER_DAY = 24
NEWS_BLACKOUT_START = 12  # US data release hours start (UTC)
NEWS_BLACKOUT_END = 15    # US data release hours end (UTC)


def run_backtest():
    # 1. Load Data
    data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "XAUUSD_H1.xlsx")
    if not os.path.exists(data_file):
        logger.error(f"File not found: {data_file}")
        return

    logger.info("Loading Data...")
    df = CSVLoader.load_data(data_file)
    
    # 2. Init Strategy
    strategy = ExhaustionFadeStrategy()
    logger.info("Calculating Indicators...")
    df = strategy.prepare_data(df)
    
    # Add confluence indicators
    df['EMA_50'] = ema(df['close'].values, 50)
    df['EMA_200'] = ema(df['close'].values, 200)
    df['RSI'] = df['close'].rolling(15).apply(lambda x: rsi(x.values, 14), raw=False)
    
    # Drop NaN rows from ATR calculation
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    # 3. Simulation State
    balance = 10000.0
    
    # Initialize adaptive risk manager
    risk_manager = AdaptiveRiskManager(base_risk=0.01)
    
    trade_history = []
    equity_curve = [balance]
    
    # Track open position
    position = None  # {type, entry_price, sl, tp, size, entry_time, entry_bar_idx}
    
    # Track session opens deterministically
    # London open = first candle closing at or after 07:00 UTC on each day
    # NY open = first candle closing at or after 13:00 UTC on each day
    session_opens = {}  # {(date, 'london'): open_price, (date, 'ny'): open_price}
    
    # Track last traded session to ensure one trade per session
    last_trade_session = None  # (date, 'london' or 'ny')
    
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
        
        # --- Determine Session Open Prices (Deterministic, No Lookahead) ---
        # London session open: first candle closing at or after 07:00
        london_key = (current_date, 'london')
        if london_key not in session_opens and current_hour >= strategy.london_open_hour:
            session_opens[london_key] = current_close
        
        # NY session open: first candle closing at or after 13:00
        ny_key = (current_date, 'ny')
        if ny_key not in session_opens and current_hour >= strategy.ny_open_hour:
            session_opens[ny_key] = current_close
        
        # --- Manage Open Position ---
        if position is not None:
            # Apply trailing stop management
            position = manage_trailing_stop(position, current_high, current_low, current_atr)
            
            closed = False
            exit_price = None
            reason = ""
            pnl = 0
            
            # Time exit (4 bars = 4 hours)
            bars_held = i - position['entry_bar_idx']
            if bars_held >= strategy.time_exit_bars:
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
                    'exit': exit_price,
                    'duration_bars': bars_held
                })
                position = None
        
        equity_curve.append(balance)
        
        # --- Check for New Entry ---
        # Only during session hours (07:00 - 20:00 UTC)
        if position is not None:
            continue
        if current_hour < strategy.london_open_hour or current_hour >= strategy.session_end_hour:
            continue
        
        # Determine which session we're in and get its open
        if current_hour >= strategy.ny_open_hour:
            session_key = (current_date, 'ny')
        else:
            session_key = (current_date, 'london')
        
        # Skip if we already traded this session
        if last_trade_session == session_key:
            continue
        
        # Get session open price
        session_open = session_opens.get(session_key)
        if session_open is None:
            continue
        
        # Calculate displacement from session open
        displacement = current_close - session_open
        displacement_abs = abs(displacement)
        
        # Check if displacement > 3x ATR
        if displacement_abs < strategy.displacement_atr_mult * current_atr:
            continue
        
        # Check exhaustion candle filter: body < 0.5x ATR
        if current_body >= strategy.exhaustion_candle_mult * current_atr:
            continue
        
        # Filter out US data release hours (12:00-15:00 UTC)
        if NEWS_BLACKOUT_START <= current_hour < NEWS_BLACKOUT_END:
            continue
        
        # Signal detected - fade the move
        if displacement > 0:
            # Price moved UP → SELL
            # Check confluence filter
            if not confluence_check(df, i, 'SELL'):
                continue
            
            # Get adaptive risk
            risk_per_trade = risk_manager.get_risk(balance)
            if risk_per_trade == 0:
                continue
            
            entry_price = apply_entry_cost(current_close, 'SELL')
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
            
        else:
            # Price moved DOWN → BUY
            # Check confluence filter
            if not confluence_check(df, i, 'BUY'):
                continue
            
            # Get adaptive risk
            risk_per_trade = risk_manager.get_risk(balance)
            if risk_per_trade == 0:
                continue
            
            entry_price = apply_entry_cost(current_close, 'BUY')
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
    
    # End of Loop - Close any remaining position
    if position is not None:
        exit_price = apply_exit_cost(df.iloc[-1]['close'], position['type'])
        bars_held = len(df) - 1 - position['entry_bar_idx']
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
            'exit': exit_price,
            'duration_bars': bars_held
        })
    
    # ======= ENHANCED DIAGNOSTICS =======
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
    
    # Drawdown
    equity_series = pd.Series(equity_curve)
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    
    # --- Additional Diagnostics ---
    # Data range
    first_date = df['time'].iloc[0]
    last_date = df['time'].iloc[-1]
    years = (last_date - first_date).days / 365.25
    
    # Trades per year
    trades_per_year = total_trades / years if years > 0 else 0
    
    # Average trade duration (in bars/hours)
    avg_duration = df_trades['duration_bars'].mean()
    
    # Expectancy per trade
    expectancy = net_pnl / total_trades if total_trades > 0 else 0
    
    # Win/Loss distribution
    tp_trades = len(df_trades[df_trades['result'] == 'TP'])
    sl_trades = len(df_trades[df_trades['result'] == 'SL'])
    time_trades = len(df_trades[df_trades['result'] == 'TIME'])
    
    # Statistical significance check
    under_sampled = total_trades < 200
    
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
    
    print("=" * 60)
    print("BACKTEST RESULTS: XAUUSD Exhaustion Fade Strategy v2")
    print("(With Adaptive Risk, Costs, Trailing Stops, Confluence)")
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
    print(f"Total Return:     {total_return:.2f}%")
    print("-" * 60)
    print("Enhanced Metrics:")
    print(f"Sharpe Ratio:     {sharpe_ratio:.2f}")
    print(f"Calmar Ratio:     {calmar_ratio:.2f}")
    print(f"Avg Win:          ${avg_win:.2f}")
    print(f"Avg Loss:         ${avg_loss:.2f}")
    print(f"Risk/Reward:      1:{(avg_win/abs(avg_loss)):.2f}" if avg_loss != 0 else "Risk/Reward:  N/A")
    print("-" * 60)
    print(f"Avg Duration:     {avg_duration:.1f} bars (hours)")
    print(f"Exit Breakdown:   TP: {tp_trades} | SL: {sl_trades} | Time: {time_trades}")
    print("=" * 60)
    
    if under_sampled:
        print("⚠️  WARNING: Total trades < 200. Strategy is STATISTICALLY UNDER-SAMPLED.")
    else:
        print("✓  Sample size adequate (>= 200 trades).")
    
    print("=" * 60)


if __name__ == "__main__":
    run_backtest()
