import pandas as pd
import json

df = pd.read_excel('티맵_실제최신_1000건_정리.xlsx')

categories = {
    "1. 차량 인포테인먼트 연동 및 음량/오디오 이슈 (안드로이드 오토, 카플레이, HUD)": {
        "keywords": ["안드로이드오토", "안드로이드 오토", "카플레이", "carplay", "볼륨", "소리", "음악", "hud", "HUD", "블루투스", "순정", "헤드업", "인포테인먼트"],
        "desc": "차량과 스마트폰을 연동(안드로이드 오토, 애플 카플레이, 헤드업 디스플레이, 블루투스)하여 티맵을 사용할 때 발생하는 안내 음성 먹통/볼륨 충돌, 화면 끊김, HUD 길안내 연동 세팅 문제."
    },
    "2. 자동차 보험 갱신 및 안전운전 점수 할인 특약": {
        "keywords": ["보험", "보험료", "안전운전", "점수", "할인", "특약", "다이렉트", "갱신", "삼성화재", "db손해", "kb손해", "캐롯", "현대해상"],
        "desc": "자동차 보험 만기 및 갱신 시 티맵 운전점수(80~90점대)를 달성하여 10~27% 보험료를 할인받은 실제 인증, 급감속/야간주행 감점 방지 팁 및 각 보험사별 할인율 비교."
    },
    "3. 티맵 앱 업데이트, 길안내 품질 및 경로 비교 (카카오내비, 네이버지도)": {
        "keywords": ["카카오", "네이버지도", "네이버 지도", "비교", "길안내", "우회", "경로", "업데이트", "단속", "카메라", "재부팅", "속도", "도착예정"],
        "desc": "티맵 앱 업데이트 후 체감 반응, 카카오내비나 네이버지도와의 길안내 경로/도착 예정시간 비교, 최신 신설도로 및 단속 카메라 반영 속도에 대한 실사용 평가."
    },
    "4. 매장 플레이스 등록, 리뷰 마케팅 및 배달/대리 모빌리티 활용": {
        "keywords": ["리뷰", "플레이스", "소상공인", "매장", "창업", "배달", "쿠팡", "배민", "대리", "대리운전", "기사", "콜", "유입", "상권"],
        "desc": "자영업자들의 티맵 목적지 등록 및 매장 리뷰 마케팅 사례, 그리고 배민커넥트·쿠팡이츠 배달 라이더와 티맵 대리운전 기사들의 실제 운행 거리 측정 및 콜 배정 경험 공유."
    },
    "5. 티맵 신규 기능(졸음방지 챌린지) 및 AI·포인트 혜택": {
        "keywords": ["졸음방지", "졸음", "포인트", "숙박", "여행", "이벤트", "신규", "혜택", "모빌리티", "ai", "AI", "누구", "nugu"],
        "desc": "티맵의 신규 '졸음방지 기능(주유비 위약 챌린지)' 바이럴 반응, 티맵 포인트 적립 및 숙박/주유 할인 혜택, 누구(NUGU) 음성 AI 비서 활용 등 모빌리티 라이프스타일 기능."
    }
}

output = {}

for cat_title, info in categories.items():
    kws = info["keywords"]
    matches = []
    seen_titles = set()

    for idx, row in df.iterrows():
        text = f"{row['제목']} {row['본문요약']}".lower()
        if any(kw.lower() in text for kw in kws):
            clean_t = str(row['제목']).strip()
            if clean_t not in seen_titles:
                matches.append({
                    "cafename": str(row['카페명']),
                    "title": clean_t,
                    "desc": str(row['본문요약']),
                    "link": str(row['게시글링크'])
                })
                seen_titles.add(clean_t)

    output[cat_title] = {
        "total_count": len(matches),
        "desc": info["desc"],
        "top10": matches[:10]
    }

with open("trends_result.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("Classification completed:")
for cat, d in output.items():
    print(f"- {cat}: {d['total_count']} posts (extracted top {len(d['top10'])})")
