import os
import json
from typing import Dict, Any, Optional

class AIStockAnalyzer:
    def __init__(self):
        pass

    async def analyze(self, stock_data: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        AI 주식 분석 에이전트 실행:
        1) Gemini API Key가 유효하면 Gemini 모델을 호출하여 전문적인 AI 종합 보고서 생성
        2) 키가 없거나 실패 시 정교한 퀀트 룰 엔진(Deterministic Engine)으로 분석 보고서 생성
        """
        key_to_use = api_key or os.getenv("GEMINI_API_KEY")

        # 1. 퀀트 룰 기반 정량 스코어링 (기본 메트릭 계산)
        quant_result = self._evaluate_quantitative_scores(stock_data)

        if key_to_use:
            try:
                gemini_result = await self._call_gemini(stock_data, quant_result, key_to_use)
                return gemini_result
            except Exception as e:
                print(f"Gemini API call failed, falling back to Quant Engine: {e}")
                quant_result["engine"] = f"Quant Rule Engine (Gemini 오류: {str(e)[:50]}...)"
                return quant_result
        else:
            quant_result["engine"] = "AI Quant Rule Engine v1 (Deterministic)"
            return quant_result

    def _evaluate_quantitative_scores(self, data: Dict[str, Any]) -> Dict[str, Any]:
        info = data.get("info", {})
        tech = data.get("technical", {})
        news = data.get("news", [])
        
        current_price = info.get("current_price", 0)
        rsi = tech.get("rsi", 50.0)
        sma5 = tech.get("sma5")
        sma20 = tech.get("sma20")
        sma60 = tech.get("sma60")
        diff_rate = info.get("diff_rate", 0.0)
        vol_ratio = tech.get("volume_ratio_5d", 100.0)
        
        # 1) 기술적 점수 (0 ~ 25)
        tech_score = 12.0
        # RSI 채점
        if 40 <= rsi <= 60:
            tech_score += 4.0
        elif 60 < rsi <= 70:
            tech_score += 5.0 # 강한 모멘텀
        elif rsi > 70:
            tech_score += 2.0 # 과열 경계
        elif 30 <= rsi < 40:
            tech_score += 3.0
        else:
            tech_score += 3.0 # 과매도 반등 기대
            
        # 이동평균 배열 채점
        if sma5 and sma20 and sma60:
            if sma5 > sma20 > sma60:
                tech_score += 6.0 # 완전 정배열
            elif sma5 > sma20:
                tech_score += 4.0 # 단기 상승
            elif sma5 < sma20 < sma60:
                tech_score -= 4.0 # 완전 역배열
            else:
                tech_score += 1.0

        tech_score = max(5.0, min(25.0, tech_score))

        # 2) 밸류에이션 점수 (0 ~ 25)
        val_score = 13.0
        per_str = info.get("per", "")
        pbr_str = info.get("pbr", "")
        try:
            per = float(per_str.replace(",", "")) if per_str and per_str != "N/A" else None
            pbr = float(pbr_str.replace(",", "")) if pbr_str and pbr_str != "N/A" else None
        except Exception:
            per, pbr = None, None

        if per is not None:
            if 0 < per <= 10:
                val_score += 5.0 # 저평가 우수
            elif 10 < per <= 20:
                val_score += 4.0 # 적정
            elif 20 < per <= 40:
                val_score += 2.0 # 다소 고평가
            elif per > 40:
                val_score -= 2.0 # 고평가 부담
        else:
            val_score += 2.0

        if pbr is not None:
            if 0 < pbr <= 1.0:
                val_score += 5.0 # 저PBR 가치주
            elif 1.0 < pbr <= 2.5:
                val_score += 3.0
            elif pbr > 4.0:
                val_score -= 2.0

        val_score = max(5.0, min(25.0, val_score))

        # 3) 수급 동향 점수 (0 ~ 25)
        flow_score = 12.0
        deal_trends = info.get("deal_trend", [])
        if deal_trends:
            latest_deal = deal_trends[0]
            foreign_buy = latest_deal.get("foreignerPureBuyQuant", "0")
            organ_buy = latest_deal.get("organPureBuyQuant", "0")
            
            f_is_buy = "+" in foreign_buy or (not foreign_buy.startswith("-") and foreign_buy != "0")
            o_is_buy = "+" in organ_buy or (not organ_buy.startswith("-") and organ_buy != "0")
            
            if f_is_buy and o_is_buy:
                flow_score += 9.0 # 외인+기관 쌍끌이 매수
            elif f_is_buy or o_is_buy:
                flow_score += 5.0 # 외인 or 기관 단독 매수
            else:
                flow_score -= 3.0 # 동반 순매도
        flow_score = max(5.0, min(25.0, flow_score))

        # 4) 모멘텀 점수 (0 ~ 25)
        mom_score = 12.0
        if diff_rate > 2.0:
            mom_score += 4.0
        elif diff_rate > 0:
            mom_score += 2.0
        elif diff_rate < -3.0:
            mom_score -= 3.0

        if vol_ratio > 150.0:
            mom_score += 5.0 # 거래량 분출
        elif vol_ratio > 100.0:
            mom_score += 2.0
        elif vol_ratio < 50.0:
            mom_score -= 2.0 # 거래량 침체

        mom_score = max(5.0, min(25.0, mom_score))

        # 종합 점수 (100점 만점)
        total_score = round(tech_score + val_score + flow_score + mom_score, 1)

        # 투자의견 도출
        if total_score >= 80:
            opinion = "STRONG BUY"
            opinion_ko = "적극 매수"
            action_desc = "상승 추세와 밸류에이션, 수급 삼박자가 어우러진 강력한 진입 구간입니다."
        elif total_score >= 65:
            opinion = "BUY"
            opinion_ko = "매수 고려"
            action_desc = "긍정적 모멘텀이 유지되고 있으며 분할 매수 접근이 유효한 시점입니다."
        elif total_score >= 45:
            opinion = "HOLD"
            opinion_ko = "중립 / 관망"
            action_desc = "단기 방향성 탐색 구간으로 지지선 확인 후 추세 전환 시 진입을 권장합니다."
        elif total_score >= 30:
            opinion = "SELL"
            opinion_ko = "비중 축소"
            action_desc = "추세 이탈 또는 차익 실현 매물 출회에 따른 리스크 관리가 필요합니다."
        else:
            opinion = "STRONG SELL"
            opinion_ko = "적극 매도"
            action_desc = "하락 추세 지속 및 수급 이탈로 보수적 대응 및 손절매를 권고합니다."

        # 목표가 및 손절가 제안
        if current_price > 0:
            target_price_1 = int(current_price * 1.08)
            target_price_2 = int(current_price * 1.18)
            stop_loss = int(current_price * 0.94)
        else:
            target_price_1 = 0
            target_price_2 = 0
            stop_loss = 0

        # 요약 및 SWOT
        summary = [
            f"종합 투자 매력도 스코어는 100점 만점에 {total_score}점으로 [{opinion_ko}] 의견입니다.",
            f"현재 주가는 20일 이평선 대비 이격도 {tech.get('disparity_20', 100)}% 수준이며, RSI({tech.get('rsi', 50)})로 {tech.get('rsi_status', '중립')} 상태입니다.",
            f"{tech.get('ma_alignment', '추세 진행')} 속에서 거래량 배율 {vol_ratio}%로 시장의 관심이 유지되고 있습니다."
        ]

        swot = {
            "strengths": [
                f"{info.get('market', '')} 대표 종목으로서의 시장 유동성 및 입지",
                f"기술적 이평선 상태: {tech.get('ma_alignment', '안정적 추세')}",
                f"외국인 지분율 {info.get('foreigner_rate', '보통')} 보유로 글로벌 수급 기반 유지"
            ],
            "weaknesses": [
                f"PER {info.get('per', '-')}배, PBR {info.get('pbr', '-')}배 수준으로 밸류에이션 점검 필요",
                f"단기 변동성 확대로 인한 진입 시점 분할 매수 전략 요구"
            ],
            "opportunities": [
                f"전방 산업 사이클 회복 및 관련 테마 모멘텀 부각 가능성",
                f"거래량 유입 시 1차 목표가 {target_price_1:,}원 상향 돌파 시도 기대"
            ],
            "threats": [
                f"거시 경제 금리 변동 및 글로벌 증시 변동성 동조화 리스크",
                f"주요 지지선 이탈 시 손절 기준가 {stop_loss:,}원 수준에서의 리스크 대응 필요"
            ]
        }

        strategy = f"""
1. **진입 및 비중 전략**: 현재 지표상 {opinion_ko}({total_score}점) 구간으로, 일시적 눌림목에서 분할 매수 관점 유효.
2. **목표가 설정**: 1차 단기 목표가 **{target_price_1:,}원**, 2차 중기 목표가 **{target_price_2:,}원** 설정 권고.
3. **리스크 관리**: 주요 지지선이자 손절 기준가 **{stop_loss:,}원**을 하향 이탈할 경우 리스크 관리 차원의 비중 축소 요망.
        """.strip()

        return {
            "score": total_score,
            "opinion": opinion,
            "opinion_ko": opinion_ko,
            "action_desc": action_desc,
            "scores_breakdown": {
                "technical": round(tech_score, 1),
                "valuation": round(val_score, 1),
                "flow": round(flow_score, 1),
                "momentum": round(mom_score, 1)
            },
            "target_price_1": target_price_1,
            "target_price_2": target_price_2,
            "stop_loss": stop_loss,
            "summary": summary,
            "swot": swot,
            "strategy": strategy,
            "engine": "AI Quant Rule Engine v1"
        }

    async def _call_gemini(self, stock_data: Dict[str, Any], quant_result: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        """Gemini 2.5 Flash를 이용한 고도화 AI 분석 생성"""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        info = stock_data["info"]
        tech = stock_data["technical"]
        news = stock_data.get("news", [])
        discussions = stock_data.get("discussions", [])
        news_titles = [f"- {n['title']} ({n['source']})" for n in news[:4]]
        disc_titles = [f"- [{d['author']}] {d['title']}" for d in discussions[:5]]

        prompt = f"""
당신은 대한민국 최고 수준의 공인 금융투자분석사(CFA)이자 AI 주식 분석 에이전트입니다.
다음 제공된 주식의 정량적 데이터, 기술적 지표, 수급, 최근 뉴스, 네이버 주주 토론방 여론 및 사전 정량 분석 결과를 바탕으로 심도 있는 종합 투자 분석 보고서를 JSON 형식으로 작성해주세요.

[종목 기본 정보]
- 종목명: {info.get('stock_name')} ({info.get('code')})
- 소속 시장: {info.get('market')} / 업종: {info.get('sector')}
- 현재가: {info.get('current_price'):,}원 (등락률: {info.get('diff_rate')}%)
- 시가총액: {info.get('market_cap')} (순위: {info.get('market_cap_rank')})
- 52주 최고/최저: {info.get('high_52w')} / {info.get('low_52w')}
- PER: {info.get('per')} / PBR: {info.get('pbr')} / 배당수익률: {info.get('dividend_yield')}
- 외국인 지분율: {info.get('foreigner_rate')}

[기술적 분석 지표]
- 5일 이평선: {tech.get('sma5')} / 20일 이평선: {tech.get('sma20')} / 60일 이평선: {tech.get('sma60')}
- 이평선 정배열 상태: {tech.get('ma_alignment')}
- RSI(14): {tech.get('rsi')} ({tech.get('rsi_status')})
- 볼린저 밴드: 상단 {tech.get('bollinger_upper')}, 중단 {tech.get('bollinger_mid')}, 하단 {tech.get('bollinger_lower')} (위치 %B: {tech.get('bollinger_pct_b')}%)
- 크로스 신호: {tech.get('cross_signal')}
- 5일 평균 대비 거래량 배율: {tech.get('volume_ratio_5d')}%

[최근 주요 뉴스 헤드라인]
{chr(10).join(news_titles) if news_titles else "최근 특이 뉴스 없음"}

[네이버 주주 토론방 최신 여론 및 개인투자자 심리]
{chr(10).join(disc_titles) if disc_titles else "토론방 특이 게시글 없음"}

[정량 퀀트 스코어 참고치]
- 종합 점수: {quant_result['score']}점 (기술적 {quant_result['scores_breakdown']['technical']}, 밸류 {quant_result['scores_breakdown']['valuation']}, 수급 {quant_result['scores_breakdown']['flow']}, 모멘텀 {quant_result['scores_breakdown']['momentum']})

반드시 아래 JSON 스키마를 준수하여 순수 JSON(마크다운 코드블록 포함 가능)으로만 응답해주세요:
{{
  "score": 0~100 사이 숫자 (정밀 종합 매력도 점수),
  "opinion": "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL",
  "opinion_ko": "적극 매수" | "매수 고려" | "중립 / 관망" | "비중 축소" | "적극 매도",
  "action_desc": "투자 행동에 대한 직관적인 1줄 문장",
  "scores_breakdown": {{
    "technical": 0~25 사이 숫자,
    "valuation": 0~25 사이 숫자,
    "flow": 0~25 사이 숫자,
    "momentum": 0~25 사이 숫자
  }},
  "target_price_1": 1차 목표가 (원화 정수),
  "target_price_2": 2차 목표가 (원화 정수),
  "stop_loss": 손절가 (원화 정수),
  "summary": [
    "핵심 요약 포인트 1 (수익성/가치)",
    "핵심 요약 포인트 2 (차트/기술적 추세)",
    "핵심 요약 포인트 3 (수급 및 모멘텀)"
  ],
  "swot": {{
    "strengths": ["강점1", "강점2"],
    "weaknesses": ["약점1", "약점2"],
    "opportunities": ["기회1", "기회2"],
    "threats": ["위협1", "위협2"]
  }},
  "strategy": "상세한 투자 매매 전략 및 포트폴리오 비중 관리 가이드 (마크다운 포맷)"
}}
""".strip()

        # 모델 호출
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        res_text = response.text.strip()
        parsed = json.loads(res_text)
        parsed["engine"] = "Gemini 2.5 Flash AI Agent"
        return parsed

ai_analyzer = AIStockAnalyzer()
