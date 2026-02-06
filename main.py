import sys
import logging
from datetime import datetime
import time

from config import settings
from utils.logging import setup_logging
from utils.simulation import generate_mock_data, get_mock_balance, get_mock_tick_value
from data.indicators import add_indicators
from strategy.logic import EMATrendFollower, Signal
from risk.monitor import RiskMonitor
from execution.manager import PaperExecutionManager
from execution.orders import OrderRequest

logger = logging.getLogger(__name__)

def run_paper_trading_loop():
    """
    Executes a DRY RUN simulation of the bot logic.
    Uses mock data to ensure we do not connect to live Broker.
    """
    logger.info("--- STARTING PAPER TRADING FLOW ---")
    
    # 1. Initialize Subsystems
    strategy = EMATrendFollower()
    risk_monitor = RiskMonitor()
    execution_manager = PaperExecutionManager()
    
    # Mock Account State
    account_balance = get_mock_balance()
    open_positions_count = 0 # Assume 0 for start
    
    # 2. Loop through symbols (Simulated Single Pass)
    for symbol in settings.SYMBOLS:
        logger.info(f"Processing Symbol: {symbol}")
        
        # A. Get Data (Mocked for Safety)
        # In prod: df = loader.get_historical_data(symbol, settings.TIMEFRAME)
        df = generate_mock_data(symbol)
        logger.info(f"Loaded {len(df)} candles (Mock Data)")
        
        # B. Calculate Indicators
        df = add_indicators(
            df, 
            settings.EMA_FAST, 
            settings.EMA_SLOW, 
            settings.RSI_PERIOD, 
            settings.ATR_PERIOD
        )
        
        # C. Strategy Evaluation
        signal = strategy.categorize_signal(df)
        logger.info(f"Strategy Signal: {signal.value}")
        
        if signal == Signal.HOLD:
            logger.info("No Action. Skipping.")
            continue
            
        # D. Risk Monitor Check
        # Need current price for SL calculation
        current_price = df.iloc[-1]['close']
        atr_value = df.iloc[-1]['ATR']
        
        # Calculate SL distance (1.5 * ATR)
        sl_distance_points = 1.5 * atr_value / 0.00001 # Assuming 50000 points... wait. 
        # CAUTION: Point calculation depends on asset class. 
        # Standard Forex: 1.00000 -> 0.00001 is 1 point.
        # If ATR is 0.0020, distance is 0.0030. In points: 300.
        # For mock, we treat values as pure float.
        
        # Let's pass raw price distance to execution, but Risk needs 'points' for value calc?
        # Sizing input: sl_distance_points.
        # We need to know point size. Mocking it as 0.00001.
        point_size = 0.00001
        sl_dist_price = 1.5 * atr_value
        sl_dist_points = sl_dist_price / point_size
        
        tick_value = get_mock_tick_value()
        
        decision = risk_monitor.check_trade_allowed(
            account_balance=account_balance,
            open_positions_count=open_positions_count,
            sl_distance_points=sl_dist_points,
            tick_value=tick_value
        )
        
        logger.info(f"Risk Decision: {decision.reason}")
        
        if not decision.approved:
            logger.warning(f"Trade Rejected by Risk Module. Reason: {decision.reason}")
            continue
            
        # E. Paper Execution
        # Prepare SL/TP
        if signal == Signal.BUY:
            order_type = "BUY"
        else:
            order_type = "SELL"
            
        sl_price, tp_price = execution_manager.calculate_sl_tp(
            order_type, current_price, sl_dist_price, atr_value
        )
        
        order_request = OrderRequest(
            symbol=symbol,
            order_type=order_type,
            volume=decision.lot_size,
            price=current_price,
            sl=sl_price,
            tp=tp_price,
            magic=settings.MAGIC_NUMBER,
            comment="Paper Trade",
            timestamp=datetime.now()
        )
        
        execution_manager.execute_order(order_request)
        open_positions_count += 1
        
    logger.info("--- PAPER TRADING FLOW COMPLETE ---")

def main():
    # Setup Logging
    setup_logging(settings.LOG_DIR, settings.LOG_LEVEL)
    
    try:
        run_paper_trading_loop()
    except Exception as e:
        logging.error(f"Critical Failure: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
