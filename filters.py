import re

# 거래글 필터링 키워드 및 카페 목록
TRADE_CAFES = ['중고나라', '직거래', '당근', '장터', '마켓', '아나바다', '번개장터', '벼룩시장']
TRADE_KEYWORDS = [
    '팝니다', '삽니다', '판매합니다', '구매합니다', '양도합니다', '급매', '미개봉',
    '택포', '운포', '착불', '네고', '일괄', '각개', '예약중', '거래완료', '판매완료', '구매원함',
    '원 판매', '만원에 팝니다', '만원에 판매'
]
PRICE_PATTERN = re.compile(r'\d{1,3}(,\d{3})+원|\d+만원')


def is_trade_post(cafename: str, title: str, desc: str = "") -> bool:
    """거래글 여부 판별 함수

    - 카페명에 중고거래 관련 키워드가 포함되어 있는지 확인
    - 제목 및 본문 요약에 거래 키워드(팝니다, 삽니다 등)가 포함되어 있는지 확인
    - 제목이나 본문에 구체적 가격 패턴(예: 10,000원, 5만원)이 포함되어 있는지 확인
    """
    cafename = cafename or ""
    title = title or ""
    desc = desc or ""
    text = f"{title} {desc}".lower()

    if any(tc in cafename for tc in TRADE_CAFES):
        return True
    if any(kw in text for kw in TRADE_KEYWORDS):
        return True
    if PRICE_PATTERN.search(title) or PRICE_PATTERN.search(desc):
        return True
    return False


def is_within_hours(time_str: str, max_hours: int = 2) -> bool:
    """작성시간 문자열 파싱 및 기준 시간 이내 여부 판별.

    예:
      - '방금', '방금 전', '10초 전', '10분 전', '1시간 전', '2시간 전' -> True (max_hours=2 기준)
      - '3시간 전', '1일 전', '어제', '2026.10.15.' -> False
    """
    if not time_str:
        return False
    time_str = time_str.strip()
    if not time_str:
        return False

    # 초 전, 분 전, 방금
    if any(k in time_str for k in ['초 전', '초전', '분 전', '분전', '방금']):
        return True

    # 시간 전
    m = re.search(r'(\d+)\s*시간\s*전', time_str)
    if m:
        hours = int(m.group(1))
        return hours <= max_hours

    return False


def is_within_2_hours(time_str: str) -> bool:
    """최근 2시간 이내 작성 여부 판별 (하위 호환성 래퍼)"""
    return is_within_hours(time_str, max_hours=2)
