import os
import re
import sys
import time
import html
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from utils import parse_cafe_search_results

# Windows 콘솔 출력 UTF-8 대응
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def search_cafe_recent_24h(query: str = "티맵", max_count: int = 1500, exclude_trade: bool = True):
    """
    네이버 카페 탭에서 최근 24시간 이내(p:1d) 최신순(so:dd) 게시글 끝까지 수집
    - exclude_trade: 거래글 자동 제외 여부 (기본값 True)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    items = []
    seen_links = set()
    start = 1
    page_size = 30

    trade_text = " (거래글 자동 제외)" if exclude_trade else ""
    print(f"\n[검색 시작] 최근 24시간 이내 '{query}' 네이버 카페 글 전수 수집 시작{trade_text}...")

    while len(items) < max_count:
        url = f"https://search.naver.com/search.naver?ssc=tab.cafe.all&query={requests.utils.quote(query)}&sort=date&nso=so:dd,p:1d&start={start}"

        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 403:
                print("  - 일시적 요청 제한 감지, 2초 대기 후 재시도...")
                time.sleep(2.0)
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code != 200:
                    print(f"[오류] 재시도 실패: HTTP {res.status_code}")
                    break
            elif res.status_code != 200:
                print(f"[오류] HTTP {res.status_code} 발생")
                break

            parsed_items = parse_cafe_search_results(res.text, exclude_trade=exclude_trade)
            if not parsed_items:
                print("  - 더 이상 최근 24시간 이내 검색 결과가 없습니다.")
                break

            new_count = 0
            for item in parsed_items:
                base_link = item["link"].split("?")[0]
                if base_link in seen_links:
                    continue
                seen_links.add(base_link)

                items.append({
                    "카페명": item["cafename"],
                    "작성시간": item["post_time"],
                    "제목": item["title"],
                    "본문요약": item["desc"],
                    "게시글링크": item["link"]
                })
                new_count += 1

                if len(items) >= max_count:
                    break

            if new_count == 0:
                print("  - 중복 없는 새로운 게시글이 더 이상 없습니다. 수집을 완료합니다.")
                break

            print(f"  - 현재 {len(items)}건 수집 중... (최근 작성: {items[-1]['작성시간']})")
            start += page_size
            time.sleep(0.5)

            # 네이버 웹 검색 결과 상한 (start > 1000)
            if start > 1000:
                print("  - 네이버 검색 제공 최대 페이지(약 1,000건)에 도달했습니다.")
                break

        except Exception as e:
            print(f"[경고] 수집 중 오류: {e}")
            break

    return items

def main():
    query = "티맵"
    items = search_cafe_recent_24h(query=query, max_count=2000)


    if not items:
        print("최근 24시간 이내 작성된 글이 없습니다.")
        return

    df = pd.DataFrame(items)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_xlsx = f"티맵_최근24시간_카페글_{timestamp}.xlsx"
    out_csv = f"티맵_최근24시간_카페글_{timestamp}.csv"

    df.to_excel(out_xlsx, index=False)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print("\n" + "="*60)
    print(f"[완료] 최근 24시간 이내 티맵 카페글 총 {len(df)}건 수집 완료!")
    print(f"엑셀 파일: {os.path.abspath(out_xlsx)}")
    print(f"CSV 파일 : {os.path.abspath(out_csv)}")
    print("="*60)

    print("\n[최근 24시간 이내 주요 글 목록 미리보기 (상위 10건)]")
    for idx, row in df.head(10).iterrows():
        print(f"\n{idx+1}. [{row['카페명']}] ({row['작성시간']}) {row['제목']}")
        print(f"   요약: {row['본문요약'][:80]}...")
        print(f"   링크: {row['게시글링크']}")

if __name__ == "__main__":
    main()
