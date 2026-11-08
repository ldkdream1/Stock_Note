# Python 3.11 슬림 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 및 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 및 캐시 복사
COPY . .

# 포트 노출 (기본값 8000, 클라우드 환경에서는 PORT 환경변수에 따름)
ENV PORT=8000
EXPOSE 8000

# 서버 시작 명령어
CMD ["python", "run.py"]
