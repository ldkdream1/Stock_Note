import asyncio
import re
import json
import os
from typing import Dict, Any, List, Optional
import httpx
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from app.technical import analyze_technical_signals

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "krx_cache.json")

class StockService:
    def __init__(self):
        self.corp_map: Dict[str, Dict[str, str]] = {} # name -> {code, market, sector}
        self.code_map: Dict[str, str] = {} # code -> name
        self.client_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://finance.naver.com/"
        }
        self.is_initialized = False

    async def initialize(self):
        """KRX 상장사 목록을 캐시 또는 웹에서 로드"""
        if self.is_initialized:
            return

        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.corp_map = data.get("corp_map", {})
                    self.code_map = data.get("code_map", {})
                    if self.corp_map:
                        self.is_initialized = True
                        print(f"Loaded {len(self.corp_map)} companies from local cache.")
                        return
            except Exception as e:
                print(f"Cache load error: {e}")

        # 캐시가 없으면 KRX에서 상장종목 마스터 다운로드
        await self._fetch_krx_master()
        self.is_initialized = True

    async def _fetch_krx_master(self):
        url = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
        try:
            async with httpx.AsyncClient(headers=self.client_headers, timeout=15.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    rows = soup.find_all("tr")
                    for r in rows[1:]:
                        cols = [td.text.strip() for td in r.find_all("td")]
                        if len(cols) >= 4:
                            name = cols[0]
                            market = cols[1]
                            code = cols[2].zfill(6)
                            sector = cols[3]
                            product = cols[4] if len(cols) > 4 else ""
                            
                            self.corp_map[name] = {
                                "code": code,
                                "name": name,
                                "market": market,
                                "sector": sector,
                                "product": product
                            }
                            self.code_map[code] = name

                    # 기본 주요 대형주 fallback 보강 (만약 KRX에 누락되어도 작동 보장)
                    preset = {
                        "삼성전자": "005930",
                        "SK하이닉스": "000660",
                        "현대차": "005380",
                        "현대엘리베이터": "017800",
                        "산일전기": "062040",
                        "LG에너지솔루션": "373220",
                        "삼성바이오로직스": "207940",
                        "알테오젠": "196170",
                        "셀트리온": "068270",
                        "기아": "000270",
                        "KB금융": "105560",
                        "NAVER": "035420",
                        "카카오": "035720",
                        "POSCO홀딩스": "005490",
                        "에코프로비엠": "247540",
                        "한화에어로스페이스": "012450"
                    }
                    for n, c in preset.items():
                        if n not in self.corp_map:
                            self.corp_map[n] = {"code": c, "name": n, "market": "KOSPI", "sector": "제조업", "product": ""}
                            self.code_map[c] = n

                    with open(CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump({"corp_map": self.corp_map, "code_map": self.code_map}, f, ensure_ascii=False, indent=2)
                    print(f"KRX master fetched and cached: {len(self.corp_map)} companies.")
        except Exception as e:
            print(f"Failed to fetch KRX master: {e}")

    def resolve_ticker(self, query: str) -> Optional[Dict[str, str]]:
        """
        사용자 입력 query(종목명 또는 6자리 코드)를 해석하여 {name, code, market, sector} 반환
        """
        q = query.strip()
        if not q:
            return None

        # 1. 6자리 숫자 코드 입력인 경우
        if q.isdigit() and len(q) == 6:
            code = q
            name = self.code_map.get(code, f"종목({code})")
            info = self.corp_map.get(name, {})
            return {
                "name": name,
                "code": code,
                "market": info.get("market", "KOSPI/KOSDAQ"),
                "sector": info.get("sector", "기타")
            }

        # 2. 정확한 종목명 일치
        if q in self.corp_map:
            return self.corp_map[q]

        # 3. 대소문자 무시 일치
        for name, info in self.corp_map.items():
            if name.lower() == q.lower():
                return info

        # 4. 부분 일치 검색 (앞부분 일치 우선, 그 다음 포함)
        prefix_matches = [info for name, info in self.corp_map.items() if name.startswith(q)]
        if prefix_matches:
            return prefix_matches[0]

        contains_matches = [info for name, info in self.corp_map.items() if q in name]
        if contains_matches:
            return contains_matches[0]

        return None

    def search_candidates(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """자동완성용 추천 후보 목록"""
        q = query.strip()
        if not q:
            return []
        
        matches = []
        for name, info in self.corp_map.items():
            if q.lower() in name.lower() or (q in info["code"]):
                matches.append({
                    "name": name,
                    "code": info["code"],
                    "market": info.get("market", ""),
                    "sector": info.get("sector", "")
                })
                if len(matches) >= limit:
                    break
        return matches

    async def get_stock_data(self, ticker: str) -> Dict[str, Any]:
        """
        종목의 실시간 데이터, 캔들 히스토리, 기술적 지표, 뉴스 등 전체 데이터를 통합 수집
        """
        await self.initialize()
        resolved = self.resolve_ticker(ticker)
        if not resolved:
            raise ValueError(f"'{ticker}'에 해당하는 주식 종목을 찾을 수 없습니다. 종목명이나 6자리 코드를 확인해주세요.")

        code = resolved["code"]
        stock_name = resolved["name"]
        market = resolved.get("market", "")
        sector = resolved.get("sector", "")

        async with httpx.AsyncClient(headers=self.client_headers, timeout=12.0) as client:
            # 1. 통합 정보 API 호출
            int_url = f"https://m.stock.naver.com/api/stock/{code}/integration"
            # 2. 캔들 차트 (최근 100일)
            chart_url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=100&requestType=0"
            # 3. 뉴스 API
            news_url = f"https://m.stock.naver.com/api/news/stock/{code}?page=1&pageSize=6"
            # 4. 주주 토론방 API
            disc_url = f"https://stock.naver.com/api/community/discussion/posts?itemCode={code}"

            int_task = client.get(int_url)
            chart_task = client.get(chart_url)
            news_task = client.get(news_url)
            disc_task = client.get(disc_url)

            int_res, chart_res, news_res, disc_res = await asyncio.gather(
                int_task, chart_task, news_task, disc_task, return_exceptions=True
            )

        # 1) 통합 기본 정보 파싱
        base_info = {
            "stock_name": stock_name,
            "code": code,
            "market": market,
            "sector": sector,
            "current_price": 0,
            "price_diff": 0,
            "diff_rate": 0.0,
            "volume": 0,
            "trading_value": "0",
            "market_cap": "N/A",
            "market_cap_rank": "N/A",
            "per": "N/A",
            "pbr": "N/A",
            "dividend_yield": "N/A",
            "eps": "N/A",
            "bps": "N/A",
            "high_52w": "N/A",
            "low_52w": "N/A",
            "foreigner_rate": "N/A",
            "deal_trend": []
        }

        if not isinstance(int_res, Exception) and int_res.status_code == 200:
            int_data = int_res.json()
            if "stockName" in int_data:
                base_info["stock_name"] = int_data["stockName"]
                
            total_infos = int_data.get("totalInfos", [])
            for item in total_infos:
                code_key = item.get("code")
                val = item.get("value", "")
                if code_key == "marketValue":
                    base_info["market_cap"] = val
                elif code_key == "per":
                    base_info["per"] = val
                elif code_key == "pbr":
                    base_info["pbr"] = val
                elif code_key == "dividendYieldRatio":
                    base_info["dividend_yield"] = val
                elif code_key == "eps":
                    base_info["eps"] = val
                elif code_key == "bps":
                    base_info["bps"] = val
                elif code_key == "highPriceOf52Weeks":
                    base_info["high_52w"] = val
                elif code_key == "lowPriceOf52Weeks":
                    base_info["low_52w"] = val
                elif code_key == "foreignRate":
                    base_info["foreigner_rate"] = val
                elif code_key == "accumulatedTradingVolume":
                    base_info["volume"] = self._parse_num(val)
                elif code_key == "accumulatedTradingValue":
                    base_info["trading_value"] = val

            deal_trends = int_data.get("dealTrendInfos", [])
            base_info["deal_trend"] = deal_trends[:5]

            # 최신 현재가 및 등락 추출 (dealTrendInfos[0] 또는 totalInfos)
            if deal_trends:
                latest = deal_trends[0]
                cur_p = self._parse_num(latest.get("closePrice", "0"))
                diff_p = self._parse_num(latest.get("compareToPreviousClosePrice", "0"))
                base_info["current_price"] = cur_p
                base_info["price_diff"] = diff_p
                # 등락률 계산
                prev_p = cur_p - diff_p
                if prev_p > 0:
                    base_info["diff_rate"] = round((diff_p / prev_p) * 100, 2)

        # 2) 캔들 차트 파싱 (XML fchart)
        candles = []
        if not isinstance(chart_res, Exception) and chart_res.status_code == 200:
            soup = BeautifulSoup(chart_res.text, "html.parser")
            items = soup.find_all("item")
            for it in items:
                raw_data = it.get("data", "")
                parts = raw_data.split("|")
                if len(parts) >= 6:
                    # date|open|high|low|close|volume
                    raw_date = parts[0]
                    formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
                    c = {
                        "date": formatted_date,
                        "open": float(parts[1]),
                        "high": float(parts[2]),
                        "low": float(parts[3]),
                        "close": float(parts[4]),
                        "volume": float(parts[5])
                    }
                    candles.append(c)

        # 최신 종가 보정 (오늘 장중 시세가 totalInfos에 있으면 최신 반영)
        if base_info["current_price"] and candles:
            candles[-1]["close"] = float(base_info["current_price"])

        # 3) 기술적 지표 산출
        technical_data = analyze_technical_signals(candles)

        # 4) 뉴스 파싱
        news_items = []
        if not isinstance(news_res, Exception) and news_res.status_code == 200:
            import html
            try:
                news_data = news_res.json()
                raw_items = []
                if isinstance(news_data, list):
                    for group in news_data:
                        if isinstance(group, dict) and "items" in group:
                            raw_items.extend(group["items"])
                        elif isinstance(group, dict) and "title" in group:
                            raw_items.append(group)
                elif isinstance(news_data, dict):
                    raw_items = news_data.get("items", news_data.get("newsList", []))

                for n in raw_items[:6]:
                    if isinstance(n, dict):
                        raw_title = n.get("title", n.get("tit", ""))
                        clean_title = html.unescape(re.sub(r'<[^>]+>', '', raw_title)).strip()
                        dt = str(n.get("datetime", n.get("dt", "")))
                        if len(dt) == 12:
                            dt = f"{dt[:4]}.{dt[4:6]}.{dt[6:8]} {dt[8:10]}:{dt[10:]}"
                        oid = n.get("officeId", n.get("oid", ""))
                        aid = n.get("articleId", n.get("aid", ""))
                        origin = n.get("officeName", n.get("oname", "증권뉴스"))
                        url = f"https://n.news.naver.com/mnews/article/{oid}/{aid}" if oid and aid else ""
                        if clean_title:
                            news_items.append({
                                "title": clean_title,
                                "date": dt,
                                "source": origin,
                                "url": url
                            })
            except Exception as e:
                print(f"News parsing error: {e}")

        # 5) 주주 토론방 파싱
        discussions = []
        if not isinstance(disc_res, Exception) and disc_res.status_code == 200:
            import html
            try:
                disc_data = disc_res.json()
                raw_posts = disc_data.get("posts", [])
                for p in raw_posts[:8]:
                    p_id = p.get("id", "")
                    raw_title = p.get("title", "")
                    clean_title = html.unescape(raw_title).strip()
                    writer_obj = p.get("writer", {})
                    author = writer_obj.get("nickname", "주주")
                    is_holder = bool(writer_obj.get("isHolderVerified") or p.get("isHolderVerified"))
                    written_at = p.get("writtenAt", "")
                    if written_at and "T" in written_at:
                        parts = written_at.split("T")
                        date_str = parts[0].replace("-", ".")
                        time_str = parts[1][:5]
                        formatted_dt = f"{date_str} {time_str}"
                    else:
                        formatted_dt = written_at
                    
                    body_text = p.get("contentSwReplacedButImg", "")
                    if not body_text:
                        body_text = p.get("body", "")
                    body_snippet = html.unescape(re.sub(r'<[^>]+>', '', body_text)).strip()
                    if len(body_snippet) > 80:
                        body_snippet = body_snippet[:80] + "..."

                    post_url = f"https://stock.naver.com/domestic/stock/{code}/discussion/{p_id}" if p_id else ""
                    
                    discussions.append({
                        "id": p_id,
                        "title": clean_title,
                        "content": body_snippet,
                        "author": author,
                        "is_holder": is_holder,
                        "date": formatted_dt,
                        "recommend_count": p.get("recommendCount", 0),
                        "comment_count": p.get("commentCount", 0),
                        "url": post_url
                    })
            except Exception as e:
                print(f"Discussion parsing error: {e}")

        return {
            "info": base_info,
            "technical": technical_data,
            "candles": candles[-60:], # 차트용 최근 60개 캔들
            "news": news_items,
            "discussions": discussions
        }

    def _parse_num(self, val: str) -> int:
        clean = re.sub(r'[^\d\-]', '', str(val))
        return int(clean) if clean and clean != '-' else 0

    def _parse_float(self, val: str) -> float:
        clean = re.sub(r'[^\d\.\-]', '', str(val))
        return float(clean) if clean and clean != '-' else 0.0

stock_service = StockService()
