import pandas as pd
import json

df = pd.read_excel('티맵_최근24시간_전체수집_20261015_221255.xlsx')

categories = {
    "트렌드 1. 차량 인포테인먼트 연동 및 음량/오디오 버그 (안드로이드 오토, 카플레이, HUD)": {
        "keywords": ["안드로이드오토", "안드로이드", "카플레이", "볼륨", "소리", "음악", "hud", "HUD", "블루투스", "내비", "내비게이션", "화면", "무선"],
        "desc": "스마트폰과 차량(안드로이드 오토, 애플 카플레이, HUD, 블루투스)을 연결했을 때 티맵 안내 음성과 미디어(음악, 유튜브) 볼륨 간의 충돌 및 강제 축소, 무선 연결 끊김 현상 등에 대한 불편 호소 및 세팅 해결 팁."
    },
    "트렌드 2. 앱 업데이트 오류, 버전 호환성 및 단속/지도 반영 문제": {
        "keywords": ["업데이트", "오류", "버그", "접속", "안됨", "먹통", "속도", "길안내", "단속", "카메라", "재부팅", "다운로드", "설치"],
        "desc": "최근 티맵 앱 업데이트 이후 발생하는 다운로드 멈춤, 스마트폰 OS별 설치 불가 이슈, 계기판과 티맵 간 속도 편차, 최신 단속 카메라 반영 지연에 대한 문의와 대처법 공유."
    },
    "트렌드 3. 소상공인·자영업자의 지도 플레이스 및 리뷰 마케팅 채널 확장": {
        "keywords": ["리뷰", "플레이스", "소상공인", "매장", "창업", "고객", "등록", "외주", "카카오맵", "구글", "노출", "마케팅", "유입"],
        "desc": "요식업·창업·소상공인 카페를 중심으로 네이버 플레이스 단일 채널을 넘어 티맵, 카카오맵, 구글 지도에 매장을 등록하고 길안내 목적지 검색 및 리뷰를 늘려 매출을 올리는 마케팅 사례."
    },
    "트렌드 4. 신규 기능(졸음방지 챌린지) 및 AI·대리운전 모빌리티 확장": {
        "keywords": ["졸음방지", "대리", "대리운전", "포인트", "숙박", "여행", "모빌리티", "신규", "혜택", "이벤트", "기능", "신한", "ai", "AI"],
        "desc": "티맵이 최근 공개한 '졸음방지 기능(졸음 시 주유비 벌금성 위약 챌린지)'의 실사용 바이럴 반응, 정부 '2026 거대 AI 사업'에 티맵모빌리티 참여 소식, 티맵 대리운전 기사 및 이용자 커뮤니티 글."
    },
    "트렌드 5. 자동차 보험 갱신 및 티맵 안전운전 점수 할인 특약": {
        "keywords": ["보험", "보험료", "안전운전", "점수", "할인", "특약", "다이렉트", "갱신", "삼성화재", "db", "DB", "kb", "KB"],
        "desc": "가을/연말 자동차 보험 만기를 앞두고 삼성화재, DB손해보험, KB손해보험 등 다이렉트 자동차보험에서 티맵 안전운전 점수(80~90점대)를 달성해 10~27% 보험료를 할인받은 실제 후기와 점수 관리법."
    }
}

output_data = {}

for cat_name, info in categories.items():
    kws = info["keywords"]
    matches = []
    seen_titles = set()

    for idx, row in df.iterrows():
        text = f"{row['제목']} {row['본문요약']}".lower()
        if any(kw.lower() in text for kw in kws):
            # 중복 제목 제거
            clean_t = str(row['제목']).strip()
            if clean_t not in seen_titles:
                matches.append({
                    "cafename": str(row['카페명']),
                    "title": clean_t,
                    "time": str(row['작성시간']),
                    "desc": str(row['본문요약']),
                    "link": str(row['게시글링크'])
                })
                seen_titles.add(clean_t)

    output_data[cat_name] = {
        "total_count": len(matches),
        "desc": info["desc"],
        "top10": matches[:10]
    }

with open("top5_trends_10links.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print("Extracted top 5 trends and 10 links each successfully!")
