"""
Adaptive Risk Manager
Dynamically adjusts position sizing based on drawdown and consecutive losses.
Provides protection against deep drawdowns and helps preserve capital during losing streaks.
"""


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
        if drawdown >= 0.15:
            return 0.0
        
        # Reduce risk based on drawdown levels
        if drawdown >= 0.10:
            risk_multiplier = 0.5
        elif drawdown >= 0.05:
            risk_multiplier = 0.75
        else:
            risk_multiplier = 1.0
        
        # Further reduce risk based on consecutive losses
        if self.consecutive_losses >= 5:
            risk_multiplier *= 0.25
        elif self.consecutive_losses >= 3:
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
