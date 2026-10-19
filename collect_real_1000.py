import os
import re
import html
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def clean_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def collect_1000_real_cafe_posts():
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }

    all_items = []
    seen_links = set()

    print("[공식 API] 티맵 최신 카페글 1,000건 수집 시작...")

    for start in range(1, 1001, 100):
        url = "https://openapi.naver.com/v1/search/cafearticle.json"
        params = {
            "query": "티맵",
            "display": 100,
            "start": start,
            "sort": "date"
        }

        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code != 200:
            print(f"API 오류: {res.status_code}")
            break

        data = res.json()
        items = data.get("items", [])
        for it in items:
            link = it.get("link", "")
            title = clean_html(it.get("title", ""))
            if link in seen_links or not title:
                continue
            seen_links.add(link)

            all_items.append({
                "번호": len(all_items) + 1,
                "카페명": clean_html(it.get("cafename", "")),
                "제목": title,
                "본문요약": clean_html(it.get("description", "")),
                "카페URL": it.get("cafeurl", ""),
                "게시글링크": link
            })

        print(f"  - 누적 {len(all_items)}건 수집 완료...")

    df = pd.DataFrame(all_items)
    df.to_excel("티맵_실제최신_1000건_정리.xlsx", index=False)
    print(f"[완료] 총 {len(df)}건의 실제 고유 게시글 저장 완료!")
    return df

if __name__ == "__main__":
    collect_1000_real_cafe_posts()
