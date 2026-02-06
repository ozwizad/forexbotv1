"""
Break-Even Management Module

Fiyat TP yolunun %50'sini kat ettiğinde SL'i Entry fiyatına çeker.
Bu sayede işlem "risk-free" hale gelir.
"""

def check_breakeven(position: dict, current_price: float, atr: float) -> dict:
    """
    Break-even kontrolü yapar. Fiyat 1.0 ATR (TP yolunun %50'si) kat ettiğinde
    SL'i Entry fiyatına çeker.
    
    Args:
        position: Pozisyon dict'i (type, entry_price, sl, tp, size, entry_time)
        current_price: Mevcut fiyat (genelde close)
        atr: Mevcut ATR değeri
        
    Returns:
        Updated position dict - SL değişmiş olabilir
    """
    if position is None:
        return position
    
    # Breakeven zaten aktifse tekrar kontrol etme
    if position.get('breakeven_active', False):
        return position
    
    # TP yolunun %50'si = 1.0 ATR (çünkü TP = 2.0 ATR)
    breakeven_threshold = atr * 1.0
    
    if position['type'] == 'BUY':
        # Fiyat yukarı hareket etti mi?
        move = current_price - position['entry_price']
        
        # Threshold aşıldıysa ve SL henüz entry'nin altındaysa
        if move >= breakeven_threshold and position['sl'] < position['entry_price']:
            position['sl'] = position['entry_price']
            position['breakeven_active'] = True
    
    elif position['type'] == 'SELL':
        # Fiyat aşağı hareket etti mi?
        move = position['entry_price'] - current_price
        
        # Threshold aşıldıysa ve SL henüz entry'nin üstündeyse
        if move >= breakeven_threshold and position['sl'] > position['entry_price']:
            position['sl'] = position['entry_price']
            position['breakeven_active'] = True
    
    return position


def calculate_sl_tp(order_type: str, entry_price: float, atr: float) -> tuple:
    """
    Yeni Risk:Ödül oranına göre SL ve TP hesaplar.
    
    SL = 1.5 × ATR
    TP = 2.0 × ATR
    RRR = 2.0 / 1.5 = 1.33:1 (Pozitif EV)
    
    Args:
        order_type: 'BUY' veya 'SELL'
        entry_price: Giriş fiyatı
        atr: Mevcut ATR değeri
        
    Returns:
        (sl, tp) tuple
    """
    sl_distance = atr * 1.5
    tp_distance = atr * 2.0
    
    if order_type == 'BUY':
        sl = entry_price - sl_distance
        tp = entry_price + tp_distance
    elif order_type == 'SELL':
        sl = entry_price + sl_distance
        tp = entry_price - tp_distance
    else:
        sl = 0.0
        tp = 0.0
    
    return sl, tp


# XAUUSD Spread Constants
XAUUSD_SPREAD = 0.30  # 30 cent sabit spread


def apply_spread(close_price: float, order_type: str, symbol: str = 'XAUUSD') -> float:
    """
    Entry fiyatına spread ekler.
    
    BUY: Close + Spread (Ask fiyatından alış)
    SELL: Close (Bid fiyatından satış, spread yok)
    
    Args:
        close_price: Mum kapanış fiyatı
        order_type: 'BUY' veya 'SELL'
        symbol: İşlem çifti (şimdilik sadece XAUUSD)
        
    Returns:
        Spread uygulanmış entry fiyatı
    """
    if symbol == 'XAUUSD':
        spread = XAUUSD_SPREAD
    else:
        spread = 0.0  # Diğer semboller için spread tanımlanmamış
    
    if order_type == 'BUY':
        return close_price + spread
    else:
        return close_price
