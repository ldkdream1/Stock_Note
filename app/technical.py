import math
from typing import List, Dict, Any, Tuple

def calculate_sma(prices: List[float], period: int) -> List[float]:
    """단순 이동평균(SMA) 계산"""
    if len(prices) < period:
        return [None] * len(prices)
    
    sma = [None] * (period - 1)
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        sma.append(round(sum(window) / period, 2))
    return sma

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """상대강도지수(RSI) 계산"""
    if len(prices) <= period:
        return [None] * len(prices)
    
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    
    rsi = [None] * period
    
    # 첫 평균
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        rsi.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi.append(round(100 - (100 / (1 + rs)), 2))
        
    for i in range(period, len(deltas)):
        gain = gains[i]
        loss = losses[i]
        
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(round(100 - (100 / (1 + rs)), 2))
            
    return rsi

def calculate_bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0) -> Dict[str, List[float]]:
    """볼린저 밴드 (상단, 중단, 하단) 계산"""
    mid = calculate_sma(prices, period)
    upper = [None] * len(prices)
    lower = [None] * len(prices)
    
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        mean = mid[i]
        variance = sum((p - mean) ** 2 for p in window) / period
        std_dev = math.sqrt(variance)
        upper[i] = round(mean + (std_dev * num_std), 2)
        lower[i] = round(mean - (std_dev * num_std), 2)
        
    return {
        "upper": upper,
        "middle": mid,
        "lower": lower
    }

def analyze_technical_signals(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    최근 캔들 데이터를 바탕으로 핵심 기술적 지표 및 시그널 종합 산출
    candles: [ { date, open, high, low, close, volume }, ... ] (시간순 오름차순)
    """
    if not candles:
        return {}
    
    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]
    current_price = closes[-1]
    
    sma5 = calculate_sma(closes, 5)
    sma20 = calculate_sma(closes, 20)
    sma60 = calculate_sma(closes, 60)
    sma120 = calculate_sma(closes, 120)
    
    rsi_list = calculate_rsi(closes, 14)
    current_rsi = rsi_list[-1] if rsi_list and rsi_list[-1] is not None else 50.0
    
    bb = calculate_bollinger_bands(closes, 20, 2.0)
    bb_upper = bb["upper"][-1]
    bb_mid = bb["middle"][-1]
    bb_lower = bb["lower"][-1]
    
    # 볼린저 밴드 %B
    if bb_upper and bb_lower and (bb_upper - bb_lower) > 0:
        pct_b = round((current_price - bb_lower) / (bb_upper - bb_lower) * 100, 2)
    else:
        pct_b = 50.0
        
    # 이동평균선 배열 상태 (정배열 / 역배열 / 혼조)
    curr_sma5 = sma5[-1]
    curr_sma20 = sma20[-1]
    curr_sma60 = sma60[-1]
    
    ma_alignment = "혼조세"
    if curr_sma5 and curr_sma20 and curr_sma60:
        if curr_sma5 > curr_sma20 > curr_sma60:
            ma_alignment = "완전 정배열 (강한 상승 추세)"
        elif curr_sma5 < curr_sma20 < curr_sma60:
            ma_alignment = "완전 역배열 (강한 하락 추세)"
        elif curr_sma5 > curr_sma20:
            ma_alignment = "단기 골든크로스 / 상승 전환"
        elif curr_sma5 < curr_sma20:
            ma_alignment = "단기 데드크로스 / 조정 국면"
            
    # 골든크로스 / 데드크로스 감지 (최근 5봉 이내 5일선-20일선 크로스)
    cross_signal = "없음"
    if len(sma5) >= 3 and len(sma20) >= 3:
        if sma5[-2] and sma20[-2] and sma5[-1] and sma20[-1]:
            if sma5[-2] <= sma20[-2] and sma5[-1] > sma20[-1]:
                cross_signal = "최근 5일선이 20일선을 상향 돌파 (골든크로스)"
            elif sma5[-2] >= sma20[-2] and sma5[-1] < sma20[-1]:
                cross_signal = "최근 5일선이 20일선을 하향 이탈 (데드크로스)"

    # 거래량 모멘텀 (최근 5일 평균 대비 오늘 거래량)
    recent_vols = [v for v in volumes[-5:] if v > 0]
    avg_vol_5d = sum(recent_vols) / len(recent_vols) if recent_vols else 1.0
    vol_ratio = round((volumes[-1] / avg_vol_5d) * 100, 1) if avg_vol_5d > 0 else 100.0
    
    # 20일 이격도
    disparity_20 = round((current_price / curr_sma20) * 100, 2) if curr_sma20 else 100.0
    
    # 최근 20일 고가/저가
    recent_20_closes = closes[-20:] if len(closes) >= 20 else closes
    high_20d = max(recent_20_closes)
    low_20d = min(recent_20_closes)
    
    return {
        "current_price": current_price,
        "sma5": curr_sma5,
        "sma20": curr_sma20,
        "sma60": curr_sma60,
        "sma120": sma120[-1] if sma120 else None,
        "rsi": current_rsi,
        "rsi_status": "과매수 (조정 위험)" if current_rsi >= 70 else ("과매도 (반등 기회)" if current_rsi <= 30 else "중립 (30~70)"),
        "bollinger_upper": bb_upper,
        "bollinger_mid": bb_mid,
        "bollinger_lower": bb_lower,
        "bollinger_pct_b": pct_b,
        "ma_alignment": ma_alignment,
        "cross_signal": cross_signal,
        "disparity_20": disparity_20,
        "volume_ratio_5d": vol_ratio,
        "high_20d": high_20d,
        "low_20d": low_20d,
        "all_sma5": sma5,
        "all_sma20": sma20,
        "all_sma60": sma60,
        "all_rsi": rsi_list,
        "all_bb": bb
    }
