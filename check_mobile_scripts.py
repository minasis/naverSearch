import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'}
r = requests.get('https://m.cafe.naver.com/jmeat/1017417', headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
for i, s in enumerate(soup.select('script')):
    print(f"Script {i}: src={s.get('src')} len={len(s.get_text())}")
    if s.get_text():
        print(s.get_text()[:300])
