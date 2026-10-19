# 네이버 카페 실시간 검색 및 거래글 필터링 파이프라인

네이버 카페 검색 결과를 실시간으로 수집하고, 거래글/광고성 글을 자동 필터링하여 유효한 커뮤니티 반응 및 트렌드 데이터를 분석하기 위한 경량화 데이터 수집 엔진입니다.

## 📁 프로젝트 구조

```text
naver_cafe_search/
├── filters.py               # 거래글 및 작성시간 필터링 순수 비즈니스 로직
├── parser.py                # 네이버 카페 검색 결과 HTML 파싱 모듈
├── utils.py                 # filters 및 parser 모듈 통합 인터페이스
├── collect_recent_2h.py     # 최근 2시간 이내 비거래글 수집 및 엑셀 저장
├── search_cafe_recent_24h.py# 최근 24시간 이내 글 수집
├── tests/                   # TDD 단위 테스트 스위트
│   ├── __init__.py
│   ├── test_filters.py      # 거래글/시간 파싱 단위 테스트 (10개)
│   └── test_parser.py       # HTML 파서 및 거래글 제외 단위 테스트 (5개)
├── .pre-commit-config.yaml  # Git 커밋 전 코드 검증 및 테스트 강제 훅
├── .gitignore               # 데이터(.xlsx, .csv, .json) 및 가상환경 무시
├── requirements.txt         # 의존성 패키지 목록
└── README.md                # 프로젝트 안내 문서
```

---

## 🛠 설치 및 환경 구성

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. Pre-commit 훅 설치
커밋 전 코드 포맷팅 및 단위 테스트를 자동으로 검증하도록 훅을 설치합니다:
```bash
pre-commit install
```

전체 파일 대상 수동 검증:
```bash
pre-commit run --all-files
```

---

## 🧪 TDD 단위 테스트 실행법

Python 표준 라이브러리 `unittest`를 사용하여 외부 의존성 없이 즉시 테스트할 수 있습니다.

### 전체 테스트 실행
```bash
python -m unittest discover tests -v
```

### 개별 테스트 실행
```bash
# 필터링 로직 테스트
python -m unittest tests/test_filters.py -v

# HTML 파서 및 거래글 제외 테스트
python -m unittest tests/test_parser.py -v
```

---

## 🚀 주요 모듈 사용법

### 1. 필터링 (`filters.py`)
```python
from filters import is_trade_post, is_within_hours

# 거래글 여부 확인 (카페명, 제목, 본문 기반)
is_trade = is_trade_post("중고나라", "티맵 HUD 거치대 팝니다", "택포 2만원")
# -> True

# 최근 N시간 이내 작성 여부 확인
is_recent = is_within_hours("1시간 전", max_hours=2)
# -> True
```

### 2. HTML 파싱 (`parser.py`)
검색 결과 파싱 시 거래글(중고거래 카페, 팝니다/삽니다 키워드, 구체적 가격 표기 등)을 기본적으로 자동 제외합니다.

```python
from parser import parse_cafe_search_results

# 거래글 자동 제외 (기본 동작: exclude_trade=True)
items = parse_cafe_search_results(html_content)
for item in items:
    print(item["cafename"], item["title"], item["post_time"])

# 거래글 포함하여 전체 파싱이 필요한 경우
all_items = parse_cafe_search_results(html_content, exclude_trade=False)
```

### 3. 실시간 카페글 수집 스크립트 실행
- **최근 2시간 수집**:
  ```bash
  python collect_recent_2h.py
  ```
  `collect_recent_2h_cafe(query="티맵", exclude_trade=True)` 함수를 통해 2시간 이내 비거래글만 수집하여 엑셀 및 구글 드라이브에 저장합니다.

- **최근 24시간 수집**:
  ```bash
  python search_cafe_recent_24h.py
  ```
  `search_cafe_recent_24h(query="티맵", max_count=1500, exclude_trade=True)`를 통해 24시간 내 게시글을 거래글 제외 상태로 전수 수집합니다.
