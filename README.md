# 📈 AI 주식 분석 에이전트 v1 (AI Stock Analysis Agent v1)

한국 주식 종목명 1개(예: **삼성전자**, **현대엘리베이터**, **산일전기**) 또는 6자리 종목코드를 입력하면, 실시간 시세·재무 지표·기술적 분석 지표(이동평균선, RSI, 볼린저 밴드, 거래량 모멘텀)와 외인/기관 수급 데이터를 수집하여 **AI 종합 투자 진단 보고서**를 생성하는 에이전트 시스템입니다.

---

## 🌟 주요 특징

1. **유연한 종목 입력 & 자동완성**
   - 종목명(삼성전자, 현대엘리베이터, 산일전기, SK하이닉스 등) 및 6자리 종목코드(005930, 017800, 062040 등) 즉시 매핑
   - 실시간 자동완성 검색 드롭다운 지원
2. **정밀 기술적 지표 자동 산출**
   - 60~100 영업일 캔들 차트 분석
   - 5일, 20일, 60일 단순 이동평균선(SMA) 및 완전 정배열/역배열/골든크로스/데드크로스 감지
   - RSI (14일 상대강도지수) 및 과매수/과매도 판정
   - 볼린저 밴드 (상단, 20MA 중단, 하단) 및 %B 밴드폭 위치 계산
   - 20일선 이격도 및 5일 평균 대비 거래량 폭발 배율
3. **Dual AI 분석 엔진 지원**
   - **Gemini 2.5 Flash AI Agent**: Gemini API Key 설정 시 LLM 기반의 금융 애널리스트 심층 리포트 생성
   - **Deterministic Quant Rule Engine**: API Key가 없어도 4대 축(기술적 추세, 밸류에이션, 외인/기관 수급, 모멘텀)을 정량 평가(100점 만점)하여 투자의견, 1차/2차 목표가, 손절가, SWOT 분석을 100% 자체 산출
4. **모던 핀테크 대시보드 UI**
   - Tailwind CSS 기반 반응형 다크 테마
   - Chart.js 인터랙티브 복합 차트 (종가 라인 + 5/20/60일 이평선 + 하단 거래량 바)
   - 외인/기관 5거래일 매매동향 및 최근 종목 뉴스 피드 제공

---

## 📁 디렉토리 구조

```
Stock/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 서버 엔트리포인트 (REST API & 정적 파일 서빙)
│   ├── stock_service.py     # KRX 마스터 캐싱, 실시간 시세·캔들·재무·뉴스 수집
│   ├── ai_analyzer.py       # AI 분석 에이전트 (Gemini API + 정량 퀀트 룰 엔진)
│   ├── technical.py         # SMA, RSI, 볼린저밴드, 모멘텀 등 기술적 지표 계산 모듈
│   ├── krx_cache.json       # 국내 상장 2,700+ 종목 고속 매핑 캐시
│   └── static/
│       ├── index.html       # Tailwind CSS 대시보드 UI
│       └── app.js           # 프론트엔드 비동기 통신, Chart.js 렌더링, 상태 관리
├── requirements.txt         # 패키지 의존성 목록
├── run.py                   # 원클릭 서버 실행 스크립트
└── README.md
```

---

## 🚀 빠른 시작 가이드

### 1. 패키지 설치 (기존 환경 또는 venv)
```bash
pip install -r requirements.txt
```

### 2. 서버 실행
```bash
python run.py
```
또는
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 브라우저 접속
웹 브라우저를 열고 다음 주소로 접속합니다:
👉 **http://localhost:8000**

---

## 🔍 API 명세

| Method | Endpoint | 설명 |
|---|---|---|
| `GET` | `/` | 메인 대시보드 HTML 웹 페이지 |
| `GET` | `/api/search?q={query}` | 종목명/코드 자동완성 추천 목록 반환 |
| `POST` | `/api/analyze` | 종목 티커 1개를 전달받아 시세/지표/AI 분석 리포트 반환 |
| `GET` | `/api/health` | 서버 및 캐시 초기화 상태 확인 |

### `POST /api/analyze` 요청 예시:
```json
{
  "ticker": "현대엘리베이터",
  "gemini_api_key": "선택사항 (미입력 시 내장 퀀트 룰 엔진으로 동작)"
}
```
