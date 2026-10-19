import pandas as pd
from collections import Counter
import re
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

df = pd.read_excel('티맵_최근24시간_전체수집_20261015_221255.xlsx')

# 키워드별 그룹핑 및 주제 도출
categories = {
    "1. 자동차 인포테인먼트 / 안드로이드 오토 / 애플 카플레이 연동 이슈": [
        "안드로이드오토", "안드로이드", "카플레이", "볼륨", "소리", "음악", "hud", "HUD", "블루투스", "내비", "내비게이션", "화면", "무선"
    ],
    "2. 자동차 보험 할인 및 안전운전 점수 특약": [
        "보험", "보험료", "안전운전", "점수", "할인", "특약", "다이렉트", "갱신", "삼성화재", "db", "DB", "kb", "KB"
    ],
    "3. 앱 업데이트 / 시스템 오류 / 길안내 및 접속 문제": [
        "업데이트", "오류", "버그", "접속", "안됨", "먹통", "속도", "길안내", "단속", "카메라", "재부팅", "다운로드"
    ],
    "4. 매장 마케팅 / 리뷰 유입 / 플레이스 등록 (자영업/소상공인)": [
        "리뷰", "플레이스", "소상공인", "매장", "창업", "고객", "등록", "외주", "카카오맵", "구글", "노출", "마케팅"
    ],
    "5. 신기능 및 모빌리티 서비스 (졸음방지, 대리운전, 포인트, AI)": [
        "졸음방지", "대리", "대리운전", "포인트", "숙박", "여행", "모빌리티", "신규", "혜택", "이벤트", "기능", "신한"
    ]
}

results = {cat: [] for cat in categories}

for idx, row in df.iterrows():
    text = f"{row['제목']} {row['본문요약']}".lower()
    matched_cats = []
    for cat, kws in categories.items():
        if any(kw.lower() in text for kw in kws):
            results[cat].append(row)

print("="*60)
print(f"총 분석 데이터 건수: {len(df)}건")
print("="*60)

for cat, rows in results.items():
    print(f"\n### {cat} (관련 게시글: {len(rows)}건, {len(rows)/len(df)*100:.1f}%)")
    # 중복 제거된 대표 글 3개 추출
    unique_rows = []
    seen_titles = set()
    for r in rows:
        if r['제목'] not in seen_titles:
            unique_rows.append(r)
            seen_titles.add(r['제목'])
        if len(unique_rows) >= 3:
            break

    for i, r in enumerate(unique_rows, 1):
        print(f"  {i}. [{r['카페명']}] {r['제목']} ({r['작성시간']})")
        print(f"     요약: {str(r['본문요약'])[:80]}...")
        print(f"     링크: {r['게시글링크']}")
