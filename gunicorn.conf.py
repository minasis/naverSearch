# ==============================================================================
# Gunicorn 프로덕션 설정 파일 (gunicorn.conf.py)
# Render, Railway 등 PaaS 환경에서 CLI 인자와 무관하게 최우선 강제 적용됩니다.
# ==============================================================================

import os

# 1. 3~5일 대량 데이터 수집 타임아웃 방어 (기본 30초 -> 120초 확장)
timeout = 120

# 2. 워커 및 스레드 풀 최적화
workers = int(os.environ.get("GUNICORN_WORKERS", 2))
threads = int(os.environ.get("GUNICORN_THREADS", 4))

# 3. HTTP 연결 유지
keepalive = 5

# 4. 메모리 누수 방지 (주기적 워커 리사이클)
max_requests = 1000
max_requests_jitter = 50

# 5. 로깅
loglevel = "info"
accesslog = "-"
errorlog = "-"
