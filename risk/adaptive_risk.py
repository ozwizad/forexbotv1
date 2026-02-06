"""
Adaptive Risk Manager
Dynamically adjusts position sizing based on drawdown and consecutive losses.
Provides protection against deep drawdowns and helps preserve capital during losing streaks.
"""

# Risk management thresholds
DRAWDOWN_STOP_THRESHOLD = 0.15  # Stop trading at 15% drawdown
DRAWDOWN_HIGH_THRESHOLD = 0.10  # Reduce risk to 50% at 10% drawdown
DRAWDOWN_MED_THRESHOLD = 0.05   # Reduce risk to 75% at 5% drawdown
CONSECUTIVE_LOSS_HIGH = 5       # Reduce risk to 25% after 5 consecutive losses
CONSECUTIVE_LOSS_MED = 3        # Reduce risk to 50% after 3 consecutive losses


class AdaptiveRiskManager:
    """
    Adaptive risk management system that adjusts risk based on:
    1. Current drawdown from peak balance
    2. Consecutive losses
    
    This helps prevent catastrophic losses during unfavorable market conditions.
    """
    
    def __init__(self, base_risk=0.01):
        """
        Initialize the adaptive risk manager.
        
        Args:
            base_risk: Base risk percentage per trade (default 1% = 0.01)
        """
        self.base_risk = base_risk
        self.peak_balance = None
        self.consecutive_losses = 0
    
    def get_risk(self, current_balance):
        """
        Calculate the adjusted risk percentage based on current balance and drawdown.
        
        Args:
            current_balance: Current account balance
            
        Returns:
            Adjusted risk percentage (0.0 to base_risk)
        """
        # Initialize peak balance on first call
        if self.peak_balance is None:
            self.peak_balance = current_balance
        
        # Update peak balance if new high
        self.peak_balance = max(self.peak_balance, current_balance)
        
        # Calculate drawdown from peak
        drawdown = (self.peak_balance - current_balance) / self.peak_balance
        
        # Stop trading if drawdown >= 15%
        if drawdown >= DRAWDOWN_STOP_THRESHOLD:
            return 0.0
        
        # Reduce risk based on drawdown levels
        if drawdown >= DRAWDOWN_HIGH_THRESHOLD:
            risk_multiplier = 0.5
        elif drawdown >= DRAWDOWN_MED_THRESHOLD:
            risk_multiplier = 0.75
        else:
            risk_multiplier = 1.0
        
        # Further reduce risk based on consecutive losses
        if self.consecutive_losses >= CONSECUTIVE_LOSS_HIGH:
            risk_multiplier *= 0.25
        elif self.consecutive_losses >= CONSECUTIVE_LOSS_MED:
            risk_multiplier *= 0.5
        
        return self.base_risk * risk_multiplier
    
    def record_result(self, pnl):
        """
        Record the result of a trade to track consecutive losses.
        
        Args:
            pnl: Profit/loss of the trade
        """
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
