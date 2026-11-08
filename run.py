import uvicorn
import os
import sys
from dotenv import load_dotenv

# .env 파일이 있으면 자동 로드
load_dotenv()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[*] AI Stock Analysis Agent v1 is starting on http://localhost:{port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
