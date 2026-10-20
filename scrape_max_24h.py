import os
import re
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))

# Windows 콘솔 UTF-8 출력 대응
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def scrape_cafe_max(query: str = "티맵", target_max: int = 1500):
    """
    네이버 카페 검색에서 최근 24시간 이내 글을 네이버 제공 한도 끝까지 수집
    """
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://search.naver.com/',
        'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Upgrade-Insecure-Requests': '1'
    }

    items = []
    seen_links = set()
    start = 1
    page_size = 30
    consecutive_empty = 0

    print(f"\n============================================================")
    print(f"[최대치 수집 시작] 최근 24시간 이내 '{query}' 카페글 전수 수집...")
    print(f"============================================================")

    while len(items) < target_max:
        url = f"https://search.naver.com/search.naver?ssc=tab.cafe.all&query={requests.utils.quote(query)}&sort=date&nso=so:dd,p:1d&start={start}"

        try:
            res = session.get(url, headers=headers, timeout=12)

            if res.status_code == 403:
                print(f"\n[안내] 일시적 요청 제한 감지. 2초 대기 후 재시도...")
                time.sleep(2.5)
                res = session.get(url, headers=headers, timeout=12)
                if res.status_code != 200:
                    print(f"[종료] 네이버 최대 노출 한도에 도달했습니다. (HTTP {res.status_code})")
                    break
            elif res.status_code != 200:
                print(f"[종료] HTTP {res.status_code} 응답으로 수집 완료")
                break

            soup = BeautifulSoup(res.text, 'html.parser')
            bx_list = [b for b in soup.select('li.bx') if b.select_one('a.title_link')]

            if not bx_list:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    print("  - 더 이상 최근 24시간 검색 결과가 없습니다.")
                    break
                start += page_size
                time.sleep(0.8)
                continue
            else:
                consecutive_empty = 0

            added_this_page = 0
            for bx in bx_list:
                title_elem = bx.select_one('a.title_link')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '')

                # 중복 게시글 제외
                if link in seen_links:
                    continue
                seen_links.add(link)

                desc_elem = bx.select_one('div.dsc_area, a.dsc_link')
                desc = desc_elem.get_text(strip=True) if desc_elem else ""

                cafe_elem = bx.select_one('a.name')
                cafename = cafe_elem.get_text(strip=True) if cafe_elem else ""

                time_elem = bx.select_one('span.sub')
                post_time = time_elem.get_text(strip=True) if time_elem else ""

                items.append({
                    "번호": len(items) + 1,
                    "작성시간": post_time,
                    "카페명": cafename,
                    "제목": title,
                    "본문요약": desc,
                    "게시글링크": link
                })
                added_this_page += 1

                if len(items) >= target_max:
                    break

            print(f"  - [{start}번째 페이지] 누적 {len(items)}건 수집 완료 (최근 글: {items[-1]['작성시간']})")

            if start >= 1000:
                print("  - 네이버 검색엔진이 제공하는 최대 노출 페이지(1,000건 한도)에 도달했습니다.")
                break

            start += page_size
            time.sleep(0.7)  # 네이버 봇 차단 방지용 안전 딜레이

        except Exception as e:
            print(f"[경고] 수집 중 오류: {e}")
            break

    return items

def main():
    query = "티맵"
    items = scrape_cafe_max(query=query, target_max=1500)

    if not items:
        print("수집된 게시글이 없습니다.")
        return

    df = pd.DataFrame(items)

    timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    out_xlsx = f"티맵_최근24시간_전체수집_{timestamp}.xlsx"
    out_csv = f"티맵_최근24시간_전체수집_{timestamp}.csv"

    df.to_excel(out_xlsx, index=False)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print("\n" + "="*60)
    print(f"🎉 [수집 완료] 최근 24시간 이내 티맵 카페글 총 {len(df)}건 최대치 수집 성공!")
    print(f"📊 엑셀 파일: {os.path.abspath(out_xlsx)}")
    print(f"📄 CSV 파일 : {os.path.abspath(out_csv)}")
    print("="*60)

if __name__ == "__main__":
    main()
