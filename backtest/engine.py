import sys
import logging
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import pandas as pd
import numpy as np

# Add Project Root to Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config import settings
from utils.logging import setup_logging
from data.csv_loader import CSVLoader
from data.indicators import add_indicators
from strategy.logic import EMATrendFollower, Signal
from risk.monitor import RiskMonitor # We might mock this or use it carefully

logger = logging.getLogger("BacktestEngine")

@dataclass
class Trade:
    symbol: str
    direction: str # BUY / SELL
    entry_time: datetime
    entry_price: float
    volume: float
    sl: float
    tp: float
    exit_time: Optional[datetime] = None
    exit_price: float = 0.0
    pnl: float = 0.0
    exit_reason: str = "" # TP, SL, FORCE

class BacktestEngine:
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity_curve = []
        self.trades: List[Trade] = []
        self.active_trade: Optional[Trade] = None
        
        # Backtest Params
        self.fixed_spread_pips = 1.5 
        self.pip_size = 0.0001
        self.point_size = 0.00001 # 5-digit broker assumption
        self.spread_points = self.fixed_spread_pips * 10
        self.commission_per_lot = 7.0 # Round turn USD
        
        # Modules
        from strategy.mean_reversion import MeanReversionV1
        self.strategy = MeanReversionV1()
        # We need a custom/stripped-down monitor for backtesting loop
        # because the real RiskMonitor tracks "Daily" time in real-time.
        # We will implement logic manually here or subclass.
        # For simplicity, we implement the sizing logic directly using the module function.
        self.daily_losses = {} # Date -> float
        
    def run(self, csv_path: str):
        setup_logging(project_root / "logs", "INFO")
        logger.info(f"Starting Backtest (Mean Reversion V1) on {csv_path}")
        logger.info(f"Initial Balance: {self.balance}")
        
        # 1. Load Data
        df = CSVLoader.load_data(csv_path)
        
        # 2. Indicators
        df = add_indicators(df, settings.EMA_FAST, settings.EMA_SLOW, settings.RSI_PERIOD, settings.ATR_PERIOD)
        
        # 3. Main Loop
        start_index = 200 # Need 200 for EMA and 50 for ATR Mean
        
        for i in range(start_index, len(df) - 1):
            current_bar = df.iloc[i]
            next_bar = df.iloc[i+1] # We execute on Open/High/Low of next bar
            
            # Update Equity Curve (Approximation at Close of i)
            self.equity_curve.append({
                'time': current_bar['time'],
                'equity': self.balance + self._get_unrealized_pnl(current_bar['close'])
            })
            
            # --- EXECUTION LOGIC (Checking Active Trade) ---
            if self.active_trade:
                self._process_active_trade(self.active_trade, next_bar)
                # If closed, active_trade becomes None
                
            # --- SIGNAL LOGIC (If no trade) ---
            if not self.active_trade:
                # Check Daily Loss Limit
                current_date = current_bar['time'].date()
                daily_loss = self.daily_losses.get(current_date, 0.0)
                if daily_loss <= -(self.initial_balance * 0.03):
                    continue # Skip day
                    
                # Get Signal
                # Pass slice ending at i. Need reasonable window for rolling(50)
                window = df.iloc[i-60:i+1] # 60 is safe for 50 rolling
                sig = self.strategy.categorize_signal(window)
                
                if sig != Signal.HOLD:
                    self._execute_entry(sig, current_bar, next_bar)

        self._generate_report()

    def _get_unrealized_pnl(self, current_price: float) -> float:
        if not self.active_trade:
            return 0.0
        
        diff = 0.0
        if self.active_trade.direction == "BUY":
            diff = current_price - self.active_trade.entry_price
        else:
            diff = self.active_trade.entry_price - current_price
            
        # Value = Volume * Diff(Points) * TickValue
        # Diff is price diff. 
        # Standard: 1.0 Lot * 0.0001 (1 pip) = 10 USD.
        # So Value = (Diff / 0.0001) * 10 * Volume
        # Or simply: Diff / 0.00001 (Points) * 1.0 (TickVal) * Volume
        
        points = diff / self.point_size
        return points * 1.0 * self.active_trade.volume

    def _process_active_trade(self, trade: Trade, bar: pd.Series):
        # Check SL / TP on 'bar' (Next Bar)
        # Conservative Assumption: Check Low first for Buy, High first for Sell (Pessimistic)
        
        # Data
        open_ = bar['open']
        high = bar['high']
        low = bar['low']
        
        closed = False
        close_price = 0.0
        reason = ""
        
        # Note: In real life, spread widens SL execution. We simulate by adding spread to SL check.
        # BUY: SL is hit if Bid <= SL. (Low is usually Bid). 
        # SELL: SL is hit if Ask >= SL. (High is Bid, so Ask = High + Spread).
        
        if trade.direction == "BUY":
            # Check SL
            if low <= trade.sl:
                closed = True
                close_price = trade.sl # Assume slippage? For now clean.
                reason = "SL"
            # Check TP
            elif high >= trade.tp:
                closed = True
                close_price = trade.tp
                reason = "TP"
                
        elif trade.direction == "SELL":
            # Check SL (High + Spread >= SL)
            # We use High directly to simulate Bid chart, add spread
            if (high + (self.spread_points * self.point_size)) >= trade.sl:
                closed = True
                close_price = trade.sl
                reason = "SL"
            # Check TP (Low + Spread <= TP)
            elif (low + (self.spread_points * self.point_size)) <= trade.tp:
                closed = True
                close_price = trade.tp
                reason = "TP"
        
        if closed:
            self._close_trade(trade, close_price, bar['time'], reason)

    def _close_trade(self, trade: Trade, price: float, time: datetime, reason: str):
        trade.exit_price = price
        trade.exit_time = time
        trade.exit_reason = reason
        
        # Calculate PnL
        pnl_gross = 0.0
        if trade.direction == "BUY":
            pnl_gross = (price - trade.entry_price) / self.point_size * trade.volume
        else:
            pnl_gross = (trade.entry_price - price) / self.point_size * trade.volume
            
        commission = trade.volume * self.commission_per_lot
        trade.pnl = pnl_gross - commission
        
        self.balance += trade.pnl
        self.trades.append(trade)
        self.active_trade = None
        
        # Update Daily Loss
        d = time.date()
        self.daily_losses[d] = self.daily_losses.get(d, 0.0) + trade.pnl
        
        logger.info(f"TRADE CLOSED: {trade.direction} | PnL: {trade.pnl:.2f} | Reason: {reason}")

    def _execute_entry(self, signal: Signal, curr_bar: pd.Series, next_bar: pd.Series):
        # Calculate Logic Mean Reversion V1
        
        atr = curr_bar['ATR']
        if pd.isna(atr) or atr == 0:
            return
            
        ema200 = curr_bar['EMA_200']
        
        direction = "BUY" if signal == Signal.BUY else "SELL"
        entry_price = next_bar['open'] # Assume next open
        # NOTE: Spec says "Entry Price: Close of trigger candle".
        # But real execution is usually next open. 
        # "Entry Price: Close of the trigger candle" -> This implies immediate execution or simulation assumption.
        # However, to be realistic, we trade on Next Open.
        # But if rule strictly says "Close", we use current_bar['close'].
        # Let's stick to "Next Bar Open" as standard backtest practice unless explicitly told "Same Bar Close Execution" (unrealistic).
        # Actually spec says: "Market orders at candle close + spread". 
        # This implies we execute AT the close price effectively (or Open of next which is ideally same).
        # We will use next_bar['open'] as the trade price to avoid lookahead bias of filling at a price (Close) that technically existed before we could process.
        
        # Spread cost on Entry
        if direction == "BUY":
            entry_price += (self.spread_points * self.point_size)
        
        # SL Calc (Rule 7)
        # SL_dist = min(ATR*1.2, abs(entry - EMA200))
        # Note: entry here is the executed price.
        
        dist_ema = abs(entry_price - ema200)
        dist_atr = atr * 1.2
        sl_dist = min(dist_atr, dist_ema)
        
        sl_points = sl_dist / self.point_size
        
        # Sizing (Rule 10 - Fixed 1%)
        from risk.sizing import calculate_position_size
        volume = calculate_position_size(
            account_balance=self.balance,
            risk_pct=0.01,
            sl_distance_points=sl_points,
            tick_value=1.0,
            point_value=self.point_size
        )
        
        if volume == 0.0:
            return
            
        # SL / TP Prices
        sl = 0.0
        tp = 0.0
        tp_dist = sl_dist * 1.5
        
        if direction == "BUY":
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
        else:
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist
            
        # Commit Trade
        self.active_trade = Trade(
            symbol="EURUSD",
            direction=direction,
            entry_time=next_bar['time'],
            entry_price=entry_price,
            volume=volume,
            sl=sl,
            tp=tp
        )
        logger.info(f"TRADE OPEN: {direction} @ {entry_price} | Vol: {volume} | SL: {sl} | TP: {tp}")

    def _generate_report(self):
        total_trades = len(self.trades)
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
        total_profit = sum(t.pnl for t in wins)
        total_loss = sum(t.pnl for t in losses)
        net_profit = total_profit + total_loss
        profit_factor = (total_profit / abs(total_loss)) if total_loss != 0 else 0
        
        max_dd = 0.0
        peak = self.initial_balance
        # Reconstruct detailed equity for DD
        # ... (Simplified max DD on closed trades for now)
        current_bal = self.initial_balance
        for t in self.trades:
            current_bal += t.pnl
            if current_bal > peak:
                peak = current_bal
            dd = (peak - current_bal) / peak * 100
            if dd > max_dd:
                max_dd = dd
                
        report = f"""
==================================================
BACKTEST REPORT: EURUSD H1
Strategy: Mean Reversion V1
Range: All Data       
==================================================
Initial Balance: ${self.initial_balance}
Final Balance:   ${self.balance:.2f}
Net Profit:      ${net_profit:.2f} ({(self.balance/self.initial_balance - 1)*100:.2f}%)

Total Trades:    {total_trades}
Win Rate:        {win_rate:.2f}%
Profit Factor:   {profit_factor:.2f}
Max Drawdown:    {max_dd:.2f}%

Winners:         {len(wins)} (Avg: ${total_profit/len(wins) if wins else 0:.2f})
Losers:          {len(losses)} (Avg: ${total_loss/len(losses) if losses else 0:.2f})
==================================================
        """
        print(report)
        logger.info(report)
        
        # Save to file
        with open(project_root / "backtest/report.txt", "w") as f:
            f.write(report)

if __name__ == "__main__":
    engine = BacktestEngine()
    csv_path = project_root / "data/historical/EURUSD_H1.csv"
    engine.run(str(csv_path))
