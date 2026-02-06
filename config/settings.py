import os
from pathlib import Path

# Project Root
BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------------------
# ACCOUNT & BROKER SETTINGS
# ------------------------------------------------------------------------------
# In production, load these from environment variables or a secrets.yaml file
MT5_LOGIN = int(os.getenv("MT5_LOGIN", 0))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", "") # Optional: Path to terminal64.exe

# ------------------------------------------------------------------------------
# TRADING UNIVERSE & TIMEFRAME
# ------------------------------------------------------------------------------
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
TIMEFRAME = "H1"  # Logic handles conversion to MT5 constant (e.g. mt5.TIMEFRAME_H1)

# ------------------------------------------------------------------------------
# STRATEGY PARAMETERS (ALGORITHM SPEC)
# ------------------------------------------------------------------------------
EMA_FAST = 50
EMA_SLOW = 200
RSI_PERIOD = 14
ATR_PERIOD = 14
RISK_PCT = 0.01          # 1% per trade
MAX_OPEN_TRADES = 1
MAX_DAILY_TRADES = 3
MAX_DAILY_LOSS_PCT = 0.03 # 3%

# ------------------------------------------------------------------------------
# EXECUTION SETTINGS
# ------------------------------------------------------------------------------
SLIPPAGE = 10            # Points (not pips)
MAGIC_NUMBER = 123456
DEVIATION = 20           # Order deviation in points

# ------------------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_LEVEL = "INFO"
