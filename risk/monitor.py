from datetime import date, datetime
import logging
from dataclasses import dataclass
from typing import Optional, Literal
from config import settings

logger = logging.getLogger(__name__)

@dataclass
class RiskDecision:
    approved: bool
    reason: str
    lot_size: float = 0.0

class RiskMonitor:
    """
    The Gatekeeper. Tracks state and enforces trading limits.
    """
    def __init__(self):
        self.last_reset_date: date = datetime.now().date()
        
        # State Variables
        self.daily_trades_count: int = 0
        self.daily_realized_pnl: float = 0.0
        self.is_kill_switch_active: bool = False
        
        # We also need to track external state passed in (like current open positions)
        
    def _check_new_day(self):
        """
        Resets counters if the trading day has changed.
        """
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            logger.info("New trading day detected. Resetting Risk Monitor counters.")
            self.daily_trades_count = 0
            self.daily_realized_pnl = 0.0
            self.is_kill_switch_active = False
            self.last_reset_date = current_date

    def update_pnl(self, pnl: float):
        """
        Call this when a trade closes to update daily PnL.
        """
        self._check_new_day()
        self.daily_realized_pnl += pnl
        self.daily_trades_count += 1
        
        # Check Kill Switch trigger (Hard Stop)
        # Assuming we need account balance to calc % or just using absolute logic if specified?
        # Specification says: "Daily loss limit of 3%".
        # We need the starting balance of the day to be strictly accurate, 
        # but for now we can check against current balance passed in validate_entry 
        # or store a 'start_of_day_balance'.
        pass 

    def check_trade_allowed(
        self, 
        account_balance: float, 
        open_positions_count: int,
        sl_distance_points: float,
        tick_value: float
    ) -> RiskDecision:
        """
        Main Gatekeeper function.
        
        Args:
            account_balance: Current Account Balance.
            open_positions_count: Number of currently open trades.
            sl_distance_points: Calculated Stop Loss distance in Points.
            tick_value: Monetary value of 1 point for 1 lot.
            
        Returns:
            RiskDecision object (Approved/Rejected).
        """
        self._check_new_day()

        # 1. Kill Switch Check
        if self.is_kill_switch_active:
            return RiskDecision(False, "REJECT: Daily Loss Limit Hit (Kill Switch Active)")

        # 2. Daily Loss Limit Check (Dynamic)
        # Threshold calculation: 3% of current balance. 
        # Note: Ideally this is 3% of START OF DAY balance, but current balance is a safer proxy for immediate protection.
        daily_loss_limit = account_balance * settings.MAX_DAILY_LOSS_PCT
        if self.daily_realized_pnl <= -daily_loss_limit:
            self.is_kill_switch_active = True
            logger.warning(f"Daily loss limit hit! PnL: {self.daily_realized_pnl}, Limit: {daily_loss_limit}")
            return RiskDecision(False, "REJECT: Daily Loss Limit Breached")

        # 3. Max Daily Trades Check
        if self.daily_trades_count >= settings.MAX_DAILY_TRADES:
            return RiskDecision(False, f"REJECT: Max Daily Trades ({settings.MAX_DAILY_TRADES}) Reached")

        # 4. Max Open Positions Check
        if open_positions_count >= settings.MAX_OPEN_TRADES:
            return RiskDecision(False, f"REJECT: Max Open Positions ({settings.MAX_OPEN_TRADES}) Limit")

        # 5. Position Sizing Calculation
        from risk.sizing import calculate_position_size
        lot_size = calculate_position_size(
            account_balance=account_balance,
            risk_pct=settings.RISK_PCT,
            sl_distance_points=sl_distance_points,
            tick_value=tick_value,
            point_value=1.0 # tick_value is usually point_value adj, simplifying for interface
        )

        if lot_size <= 0:
            return RiskDecision(False, "REJECT: Calculated Lot Size is Zero (Risk too low or SL too tight)")

        # 6. Safety: Check if we have enough margin? 
        # (This is usually broker side, but good to note. Skipping for strict scope 1-5 requirements)

        return RiskDecision(True, "APPROVED", lot_size)

    def force_kill_switch(self):
        """
        Manual override to stop trading.
        """
        self.is_kill_switch_active = True
        logger.warning("Kill switch activated manually.")
