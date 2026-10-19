import requests
from bs4 import BeautifulSoup
import re
import json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

url = 'https://search.naver.com/search.naver?ssc=tab.cafe.all&query=%ED%8B%B0%EB%A7%B5&sort=date&nso=so:dd,p:1d'
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

items = []
# li.bx 아이템들 탐색
for bx in soup.select('li.bx'):
    title_elem = bx.select_one('a.title_link, a.api_txt_lines.total_tit, a.title')
    if not title_elem:
        continue

    title = title_elem.get_text(strip=True)
    link = title_elem.get('href', '')

    # 본문 요약
    desc_elem = bx.select_one('div.dsc_area, div.detail_box, a.api_txt_lines.dsc_txt, .dsc')
    desc = desc_elem.get_text(strip=True) if desc_elem else ""

    # 카페명 및 작성일
    cafe_elem = bx.select_one('a.name, .sub_txt.sub_name, .source_txt')
    cafename = cafe_elem.get_text(strip=True) if cafe_elem else ""

    date_elem = bx.select_one('span.sub_time, span.txt_inline, .date, .time')
    post_time = date_elem.get_text(strip=True) if date_elem else ""

    items.append({
        'cafename': cafename,
        'title': title,
        'time': post_time,
        'desc': desc,
        'link': link
    })

print(f"총 {len(items)}건 파싱됨")
for i, it in enumerate(items[:10], 1):
    print(f"[{i}] [{it['cafename']}] ({it['time']}) {it['title']}")
    print(f"    요약: {it['desc'][:70]}")
    print(f"    링크: {it['link']}")
