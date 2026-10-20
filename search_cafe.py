import os
import re
import sys
import html
import argparse
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

KST = timezone(timedelta(hours=9))

# Windows 콘솔 인코딩 대응
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# .env 파일이 있으면 로드
load_dotenv()

def clean_html(text: str) -> str:
    """HTML 특수문자 및 태그 제거"""
    if not text:
        return ""
    # &quot;, &amp; 등 언이스케이프
    text = html.unescape(text)
    # 태그 제거 (<b>, </b> 등)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def search_naver_cafe(client_id: str, client_secret: str, query: str, total_count: int = 100, sort: str = "date"):
    """
    네이버 카페 검색 API 호출 (페이지네이션 지원)
    - query: 검색 키워드
    - total_count: 가져올 총 개수 (최대 1000개)
    - sort: 'date'(최신순) 또는 'sim'(정확도순)
    """
    base_url = "https://openapi.naver.com/v1/search/cafearticle.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }

    items = []
    display_per_page = 100
    start = 1

    print(f"\n[검색] '[{query}]' 카페 검색 시작 (정렬: {'최신순' if sort == 'date' else '정확도순'}, 목표: {total_count}건)...")

    while start <= total_count and start <= 1000:
        fetch_display = min(display_per_page, total_count - len(items))
        if fetch_display <= 0:
            break

        params = {
            "query": query,
            "display": fetch_display,
            "start": start,
            "sort": sort
        }

        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                print(f"[오류] API 호출 실패 (HTTP {response.status_code}): {response.text}")
                break

            data = response.json()
            total_available = data.get("total", 0)
            current_items = data.get("items", [])

            if not current_items:
                break

            for it in current_items:
                items.append({
                    "카페명": clean_html(it.get("cafename", "")),
                    "제목": clean_html(it.get("title", "")),
                    "요약": clean_html(it.get("description", "")),
                    "카페URL": it.get("cafeurl", ""),
                    "게시글링크": it.get("link", "")
                })

            print(f"  - {len(items)}건 수집 완료 (검색된 전체 게시글: {total_available:,}건)")

            # 다음 페이지로
            start += fetch_display
            if start > total_available:
                break

        except Exception as e:
            print(f"[경고] 요청 중 오류 발생: {e}")
            break

    return items

def main():
    parser = argparse.ArgumentParser(description="네이버 카페 티맵/키워드 검색기")
    parser.add_argument("--query", "-q", type=str, default="티맵", help="검색 키워드 (기본: 티맵)")
    parser.add_argument("--count", "-c", type=int, default=100, help="가져올 게시글 수 (기본: 100, 최대: 1000)")
    parser.add_argument("--sort", "-s", type=str, default="date", choices=["date", "sim"], help="정렬 방식: date(최신순), sim(정확도순)")
    parser.add_argument("--client-id", type=str, help="네이버 Client ID (미지정 시 .env 또는 입력창)")
    parser.add_argument("--client-secret", type=str, help="네이버 Client Secret")
    args = parser.parse_args()

    # Client ID / Secret 확인
    client_id = args.client_id or os.getenv("NAVER_CLIENT_ID")
    client_secret = args.client_secret or os.getenv("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("\n" + "="*50)
        print("[인증] 네이버 개발자 센터에서 발급받은 키를 입력해 주세요.")
        print("="*50)
        if not client_id:
            client_id = input("Client ID 입력: ").strip()
        if not client_secret:
            client_secret = input("Client Secret 입력: ").strip()

    if not client_id or not client_secret:
        print("[오류] Client ID 또는 Client Secret이 입력되지 않았습니다.")
        return

    # 검색 실행
    results = search_naver_cafe(
        client_id=client_id,
        client_secret=client_secret,
        query=args.query,
        total_count=args.count,
        sort=args.sort
    )

    if not results:
        print("\n검색 결과가 없거나 수집하지 못했습니다.")
        return

    df = pd.DataFrame(results)

    # 결과 파일 저장
    timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    clean_query_filename = re.sub(r'[\/:*?"<>|]', '_', args.query)

    output_xlsx = f"카페검색_{clean_query_filename}_{timestamp}.xlsx"
    output_csv = f"카페검색_{clean_query_filename}_{timestamp}.csv"

    df.to_excel(output_xlsx, index=False)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print("\n" + "="*50)
    print(f"[완료] 총 {len(df)}건의 검색 결과 저장 완료!")
    print(f"엑셀 파일: {os.path.abspath(output_xlsx)}")
    print(f"CSV 파일 : {os.path.abspath(output_csv)}")
    print("="*50)

    print("\n[상위 5건 미리보기]")
    for idx, row in df.head(5).iterrows():
        print(f"\n[{idx+1}] [{row['카페명']}] {row['제목']}")
        print(f"    요약: {row['요약'][:80]}...")
        print(f"    링크: {row['게시글링크']}")

if __name__ == "__main__":
    main()
