
import pandas as pd
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugExcel")

filename = r"c:\Users\Ozai\Desktop\Klasörler\Protop\XAUUSD_H1.xlsx"

try:
    logger.info(f"Reading {filename}...")
    df = pd.read_excel(filename)
    logger.info("Columns found:")
    for col in df.columns:
        logger.info(f" - '{col}' (Type: {type(col)})")
    
    logger.info("First 5 rows:")
    print(df.head())
    
except Exception as e:
    logger.error(f"Error: {e}")
