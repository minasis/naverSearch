# 네이버 카페 실시간 검색 및 거래글 필터링 웹 서비스 (REA 하이브리드)

네이버 카페 검색 결과를 실시간으로 수집하고, 거래글/광고성 글을 100% 자동 필터링하여 유효한 커뮤니티 알짜 게시글만 엑셀로 추출하는 웹 서비스 및 모듈형 크롤링 파이프라인입니다.

---

## ✨ 핵심 기능

1. **기간 선택 크롤링 엔진 (`crawler_engine.py`)**:
   - 시작일~종료일 범위 지정 (최대 5일 기간 제한 및 클라이언트/서버 이중 검증).
   - 네이버 검색 날짜 범위 필터(`nso=so:dd,p:from{start}to{end}`)를 통한 정확한 기간별 수집.
   - REA Article API 상세 정보(초 단위 작성시간, 작성자, 댓글수, 본문) 조회 및 비공개/회원전용 글 자연스러운 폴백 연동.
   - **거래글 100% 자동 제외**: `saleInfo` 객체 검증 + 중고거래 카페/키워드/가격 패턴 복합 필터링.
2. **모던 경량 웹 서비스 (`app.py` - Flask)**:
   - 깔끔하고 직관적인 모던 웹 UI (`templates/index.html`).
   - 검색어 입력(기본값: "티맵") 및 데이트피커 (시작일, 종료일, 최대 5일 검증 및 안내).
   - 비동기 검색 및 진행 스피너, 상위 10건 실시간 미리보기 테이블.
   - 원클릭 엑셀(`.xlsx`) 자동 다운로드.
3. **클라우드 배포 호환**:
   - `Procfile` (`web: gunicorn app:app`), `wsgi.py`, `requirements.txt` 구비로 Render, Railway, PythonAnywhere 즉시 배포 가능.

---

## 📁 프로젝트 구조

```text
naver_cafe_search/
├── app.py                   # Flask 경량 웹 애플리케이션 (검색 UI 및 API 라우트)
├── crawler_engine.py        # 단일 책임을 갖는 핵심 크롤링 엔진 모듈 (최대 5일 범위 수집)
├── wsgi.py                  # WSGI 진입점 (Gunicorn / 클라우드 호스팅 호환)
├── Procfile                 # 클라우드 배포 프로세스 정의 (web: gunicorn app:app)
├── templates/
│   └── index.html           # Tailwind CSS 기반 모던 반응형 검색 & 다운로드 UI
├── article_api.py           # REA 기반 네이버 카페 Article REST API 연동 및 saleInfo 검사
├── filters.py               # 거래글 및 작성시간 필터링 순수 비즈니스 로직
├── parser.py                # 네이버 카페 검색 결과 HTML 파싱 모듈
├── utils.py                 # 모듈 통합 인터페이스
├── collect_1000_rea.py      # 대량 REA 하이브리드 수집 스크립트
├── collect_recent_2h.py     # 최근 2시간 수집 스크립트
├── search_cafe_recent_24h.py# 최근 24시간 수집 스크립트
├── tests/                   # TDD 단위 테스트 스위트 (60개 테스트)
│   ├── __init__.py
│   ├── test_crawler_engine.py # 크롤링 엔진 및 5일 범위 검증 테스트 (9개)
│   ├── test_web_app.py      # Flask 웹 라우트 및 API 테스트 (8개)
│   ├── test_article_api.py  # Article API 및 saleInfo 검증 단위 테스트 (14개)
│   ├── test_filters.py      # 거래글/시간 파싱 단위 테스트 (10개)
│   ├── test_parser.py       # HTML 파서 및 거래글 제외 단위 테스트 (5개)
│   └── test_collect_1000_rea.py # 대량 수집 파이프라인 검증 테스트 (14개)
├── .pre-commit-config.yaml  # Git 커밋 전 코드 검증 및 테스트 강제 훅
├── .gitignore               # 데이터(.xlsx, .csv, downloads/) 및 가상환경 무시
├── requirements.txt         # 의존성 패키지 목록 (Flask, gunicorn 포함)
└── README.md                # 프로젝트 안내 문서
```

---

## 🚀 로컬 실행 방법

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 웹 서버 실행
```bash
python app.py
```
브라우저에서 `http://localhost:5000` 접속:
- 검색 키워드(기본값: "티맵") 입력
- 시작일과 종료일(최대 5일 이내) 선택
- **[검색 및 엑셀 다운로드]** 버튼 클릭 시 비동기 수집 후 엑셀 파일 자동 다운로드!

---

## ☁️ 무료 호스팅 1클릭 배포 가이드

본 프로젝트는 무상 배포를 지원하는 주요 클라우드 PaaS 환경에 즉시 배포할 수 있도록 구성되어 있습니다.

### 1. Render (추천)
1. [Render.com](https://render.com) 회원가입 및 GitHub 리포지토리 연동.
2. **New +** -> **Web Service** 선택.
3. 빌드 및 시작 명령어 확인:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app` (또는 `Procfile` 자동 감지)
4. **Deploy Web Service** 클릭 시 수 분 내 전 세계 접속 가능한 공개 URL 발급.

### 2. Railway
1. [Railway.app](https://railway.app) 접속 후 **Deploy from GitHub repo** 선택.
2. `Procfile` 및 `requirements.txt`가 자동 감지되어 별도 설정 없이 즉시 빌드 및 실행.

### 3. PythonAnywhere
1. PythonAnywhere 대시보드 -> **Web** 탭에서 **Add a new web app** 선택.
2. Framework: **Flask** (Python 3.10+) 선택.
3. WSGI 설정 파일에 `from app import app as application` 지정 후 Reload.

---

## 🧪 TDD 단위 테스트 검증

모든 기능은 엄격한 TDD(테스트 주도 개발) 단위 테스트를 통과하도록 작성되었습니다.

```bash
# 전체 단위 테스트 실행 (60개 항목 100% Green)
python -m unittest discover tests -v

# 크롤링 엔진 단위 테스트
python -m unittest tests/test_crawler_engine.py -v

# Flask 웹 애플리케이션 API 단위 테스트
python -m unittest tests/test_web_app.py -v
```

### Pre-commit 무결성 검사
```bash
pre-commit run --all-files
```

---

## 💡 Python 모듈로 직접 사용하기 (`crawler_engine.py`)

다른 파이썬 코드에서 크롤링 엔진을 단독으로 가져와 활용할 수 있습니다:

```python
from crawler_engine import search_and_collect

# 5일 이내 기간 지정 검색 (100% 거래글 자동 제외)
df = search_and_collect(
    query="티맵",
    start_date="2026-10-15",
    end_date="2026-10-19",
    max_days=5
)

print(f"총 유효 게시글: {len(df)}건")
print(f"제외된 거래글: {df.attrs['trade_excluded']}건")

# 엑셀로 저장
df.to_excel("tmap_result.xlsx", index=False)
```
