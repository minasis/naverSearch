import requests
import re
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

r = requests.get('https://drive.google.com/drive/folders/16FgmNLjjcwXP42mUji6upaAmKOlwYJwJ', headers={'User-Agent': 'Mozilla/5.0'})
titles = re.findall(r'<title>(.*?)</title>', r.text)
print('Page Title:', titles)
og_titles = re.findall(r'property="og:title" content="(.*?)"', r.text)
print('OG Title:', og_titles)
