import pandas as pd
import re
import os
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 원본 1,000건 데이터 로드
df = pd.read_excel('티맵_실제최신_1000건_정리.xlsx')

# 거래글 필터링 조건
trade_cafes = ['중고나라', '직거래', '당근', '장터', '마켓', '아나바다', '번개장터', '벼룩시장']
trade_keywords = [
    '팝니다', '삽니다', '판매합니다', '구매합니다', '양도합니다', '급매', '미개봉 새제품',
    '택포', '운포', '착불', '네고', '일괄', '각개', '예약중', '거래완료', '판매완료', '구매원함',
    '원 판매', '만원에 팝니다', '만원에 판매'
]
price_pattern = re.compile(r'\b\d{1,3}(,\d{3})+원|\b\d+만원\b')

def is_trade_post(row):
    cafe = str(row['카페명'])
    title = str(row['제목'])
    desc = str(row['본문요약'])
    text = f"{title} {desc}".lower()

    # 1. 카페명에 중고거래 관련 단어가 들어있는 경우
    if any(tc in cafe for tc in trade_cafes):
        return True

    # 2. 제목/본문에 명시적인 거래 키워드가 있는 경우
    if any(kw in text for kw in trade_keywords):
        return True

    # 3. 제목에 가격 패턴이 노출된 경우 (예: 50,000원, 15만원 등)
    if price_pattern.search(title):
        return True

    return False

# 필터링 적용
is_trade = df.apply(is_trade_post, axis=1)
df_clean = df[~is_trade].copy()
df_trade = df[is_trade].copy()

print(f"전체 수집: {len(df)}건")
print(f"제외된 거래글: {len(df_trade)}건")
print(f"거래글 제외 완료: {len(df_clean)}건")

# 번호 재부여
df_clean['번호'] = range(1, len(df_clean) + 1)

# 타겟 구글 드라이브 폴더
target_dir = r"G:\내 드라이브\독후감소스"
target_xlsx = os.path.join(target_dir, "티맵_네이버카페_최신검색_거래글제외.xlsx")
target_csv = os.path.join(target_dir, "티맵_네이버카페_최신검색_거래글제외.csv")

df_clean.to_excel(target_xlsx, index=False)
df_clean.to_csv(target_csv, index=False, encoding='utf-8-sig')

print(f"\n[성공] 구글 드라이브 폴더에 저장 완료!")
print(f"- 엑셀: {target_xlsx}")
print(f"- CSV : {target_csv}")
