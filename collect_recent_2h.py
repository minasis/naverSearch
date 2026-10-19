import os
import re
import sys
import time
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

# Windows 콘솔 UTF-8 출력 대응
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from utils import is_trade_post, is_within_hours, is_within_2_hours, parse_cafe_search_results

def collect_recent_2h_cafe(query: str = "티맵"):
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://search.naver.com/',
    }

    items = []
    seen_links = set()
    start = 1
    page_size = 30
    stop_scraping = False

    print(f"\n[수집 시작] 최근 2시간 이내 '{query}' 네이버 카페 글 수집 (거래글 자동 제외)...")

    while not stop_scraping:
        url = f"https://search.naver.com/search.naver?ssc=tab.cafe.all&query={requests.utils.quote(query)}&sort=date&nso=so:dd,p:1d&start={start}"

        try:
            res = session.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                print(f"[오류] HTTP {res.status_code} 발생")
                break

            parsed_items = parse_cafe_search_results(res.text)
            if not parsed_items:
                print("  - 더 이상 검색 결과가 없습니다.")
                break

            for item in parsed_items:
                title = item["title"]
                link = item["link"]
                post_time = item["post_time"]
                desc = item["desc"]
                cafename = item["cafename"]

                if link in seen_links:
                    continue
                seen_links.add(link)

                # 2시간 초과 여부 검사
                if post_time:
                    # 3시간 전 이상이면 수집 중단
                    m_hour = re.search(r'(\d+)\s*시간\s*전', post_time)
                    if m_hour and int(m_hour.group(1)) > 2:
                        print(f"  - 2시간 경계선 도달: '{post_time}' ({title[:25]}...)")
                        stop_scraping = True
                        break
                    if any(k in post_time for k in ['일 전', '어제', '일전']):
                        stop_scraping = True
                        break

                if not is_within_hours(post_time, max_hours=2):
                    continue

                # 거래글 제외 검사
                if is_trade_post(cafename, title, desc):
                    continue

                items.append({
                    "번호": len(items) + 1,
                    "작성시간": post_time,
                    "카페명": cafename,
                    "제목": title,
                    "본문요약": desc,
                    "게시글링크": link
                })

            print(f"  - [{start}페이지 탐색] 2시간 이내 유효 글 누적: {len(items)}건...")
            start += page_size
            time.sleep(0.6)

        except Exception as e:
            print(f"[경고] 수집 중 오류: {e}")
            break

    return items

def main():
    items = collect_recent_2h_cafe(query="티맵")

    if not items:
        print("최근 2시간 이내 작성된 유효 글이 없습니다.")
        return

    df = pd.DataFrame(items)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_xlsx = f"티맵_최근2시간_카페글_{timestamp}.xlsx"
    df.to_excel(local_xlsx, index=False)

    # 구글 드라이브(독후감소스) 동시 저장
    gdrive_dir = r"G:\내 드라이브\독후감소스"
    if os.path.exists(gdrive_dir):
        gdrive_xlsx = os.path.join(gdrive_dir, f"티맵_최근2시간_카페글_{timestamp}.xlsx")
        gdrive_latest = os.path.join(gdrive_dir, "티맵_최근2시간_최신글.xlsx")
        df.to_excel(gdrive_xlsx, index=False)
        df.to_excel(gdrive_latest, index=False)
        print(f"\n[성공] 구글 드라이브({gdrive_dir})에 자동 저장 완료!")
        print(f"  - {gdrive_latest}")

    print("\n" + "="*60)
    print(f"🎉 최근 2시간 이내 티맵 카페글 총 {len(df)}건 수집 완료! (거래글 제외)")
    print(f"로컬 파일: {os.path.abspath(local_xlsx)}")
    print("="*60)

    print("\n[수집된 최근 2시간 글 전체 목록]")
    for idx, row in df.iterrows():
        print(f"[{row['번호']}] ({row['작성시간']}) [{row['카페명']}] {row['제목']}")
        print(f"    링크: {row['게시글링크']}")

if __name__ == "__main__":
    main()
