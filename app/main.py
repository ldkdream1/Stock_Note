import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from app.stock_service import stock_service
from app.ai_analyzer import ai_analyzer

app = FastAPI(title="AI Stock Analysis Agent v1", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class AnalyzeRequest(BaseModel):
    ticker: str
    gemini_api_key: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    # 백그라운드로 KRX 마스터 캐시 사전 로드
    import asyncio
    asyncio.create_task(stock_service.initialize())

@app.get("/")
async def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Stock Analysis Agent v1 is running."}

@app.get("/api/search")
async def search_stock(q: str = Query(..., min_length=1)):
    await stock_service.initialize()
    candidates = stock_service.search_candidates(q, limit=8)
    return {"candidates": candidates}

@app.post("/api/analyze")
async def analyze_stock(req: AnalyzeRequest):
    if not req.ticker or not req.ticker.strip():
        raise HTTPException(status_code=400, detail="종목명 또는 티커를 입력해주세요.")
    
    try:
        # 1. 데이터 수집
        stock_data = await stock_service.get_stock_data(req.ticker.strip())
        
        # 2. AI 분석 에이전트 실행
        ai_report = await ai_analyzer.analyze(stock_data, api_key=req.gemini_api_key)
        
        return {
            "success": True,
            "data": stock_data,
            "ai_report": ai_report
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "cached_corps": len(stock_service.corp_map),
        "initialized": stock_service.is_initialized,
        "has_gemini_key": bool(os.getenv("GEMINI_API_KEY"))
    }
