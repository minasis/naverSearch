import requests
from bs4 import BeautifulSoup
import re
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

url = 'https://search.naver.com/search.naver?where=article&query=%ED%8B%B0%EB%A7%B5&nso=so:dd,p:1d'
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

items = []
# 네이버 VIEW/카페 검색 결과의 각 아이템 블록 탐색
# 보통 li 또는 div 컨테이너 안에 제목, 카페명, 날짜, 링크가 있음
for a in soup.select('a[data-heatmap-target=".title"], a[data-heatmap-target=".body"]'):
    title_span = a.select_one('span.sds-comps-text')
    if not title_span:
        continue
    title = title_span.get_text(strip=True)
    link = a.get('href', '')

    # 상위 컨테이너에서 날짜 및 출처(카페명) 찾기
    parent = a.find_parent('div', class_=re.compile(r'sds-comps-vertical-layout|type-basic'))
    grandparent = parent.parent if parent else a.parent

    source = ""
    date = ""
    if grandparent:
        profile = grandparent.select_one('[data-sds-comp="Profile"]') or grandparent.select_one('.sds-comps-profile')
        if profile:
            source_elem = profile.select_one('.sds-comps-profile-source, .sds-comps-profile-title, a')
            if source_elem:
                source = source_elem.get_text(strip=True)
            # 날짜는 보통 프로필 내의 서브 텍스트
            texts = [t.get_text(strip=True) for t in profile.select('.sds-comps-text') if t.get_text(strip=True)]
            for t in texts:
                if any(k in t for k in ['시간 전', '분 전', '일 전', '어제', '2026', '2025']):
                    date = t
                    break

    items.append({
        'title': title,
        'link': link,
        'source': source,
        'date': date
    })

print(f"총 {len(items)}건 발견")
for i, item in enumerate(items[:10], 1):
    print(f"[{i}] [{item['source']}] ({item['date']}) {item['title']}")
    print(f"    링크: {item['link']}")
