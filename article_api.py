"""네이버 카페 Article API 연동 및 거래글 상세 식별 모듈.

REA(역공학) 분석을 통해 규명된 네이버 카페 비공개 내부 REST API:
- Endpoint: https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{cafeId}/articles/{articleId}
- 특징: 게시글 본문, 작성자 메타데이터 및 거래글 전용 saleInfo 객체를 JSON으로 제공.
"""

import re
import urllib.parse
import requests

DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}

# clubname -> cafeId 메모리 캐시
_CAFE_ID_CACHE: dict[str, int] = {}


def extract_art_token(url: str | None) -> str | None:
    """게시글 URL의 쿼리 스트링에서 'art' 인증 토큰 추출."""
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        art_list = qs.get('art')
        if art_list and art_list[0]:
            return art_list[0]
    except Exception:
        pass
    return None


def extract_ids_from_url(url: str | None) -> tuple[int | str | None, int | None]:
    """네이버 카페 URL에서 cafe_id (또는 clubname)와 article_id를 추출.

    지원하는 URL 형태:
    1. https://cafe.naver.com/ca-fe/cafes/{cafeId}/articles/{articleId}
    2. https://m.cafe.naver.com/ca-fe/web/cafes/{cafeId}/articles/{articleId}
    3. https://cafe.naver.com/ArticleRead.nhn?clubid={cafeId}&articleid={articleId}
    4. https://cafe.naver.com/{clubname}/{articleId}
    """
    if not url or not isinstance(url, str):
        return None, None

    url = url.strip()
    if not url:
        return None, None

    parsed = urllib.parse.urlparse(url)

    # 1. 쿼리 파라미터 기반 (ArticleRead.nhn, ArticleShow.nhn 등)
    if 'clubid' in parsed.query.lower() and 'articleid' in parsed.query.lower():
        qs = urllib.parse.parse_qs(parsed.query)
        # 대소문자 무시 추출
        club_id = None
        article_id = None
        for k, v in qs.items():
            k_lower = k.lower()
            if k_lower == 'clubid' and v:
                try:
                    club_id = int(v[0])
                except ValueError:
                    club_id = v[0]
            elif k_lower == 'articleid' and v:
                try:
                    article_id = int(v[0])
                except ValueError:
                    pass
        if club_id is not None and article_id is not None:
            return club_id, article_id

    # 2. 경로 패턴 1: cafes/{cafeId}/articles/{articleId}
    m = re.search(r'cafes/(\d+)/articles/(\d+)', parsed.path)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 3. 경로 패턴 2: /{clubname}/{articleId}
    # ex) /suddenattackskincafe/5143198
    segments = [s for s in parsed.path.strip('/').split('/') if s]
    if len(segments) >= 2:
        clubname_candidate = segments[0]
        article_candidate = segments[1]
        # ArticleRead.nhn 등 배제
        if not clubname_candidate.lower().endswith('.nhn') and article_candidate.isdigit():
            art_id = int(article_candidate)
            if clubname_candidate.isdigit():
                return int(clubname_candidate), art_id
            return clubname_candidate, art_id

    return None, None


def resolve_cafe_id(cafe_id_or_clubname: int | str, session: requests.Session | None = None) -> int | None:
    """clubname(문자열)을 고유 숫자 cafeId로 변환 (이미 숫자면 즉시 반환)."""
    if not cafe_id_or_clubname:
        return None

    if isinstance(cafe_id_or_clubname, int):
        return cafe_id_or_clubname

    str_val = str(cafe_id_or_clubname).strip()
    if str_val.isdigit():
        return int(str_val)

    if str_val in _CAFE_ID_CACHE:
        return _CAFE_ID_CACHE[str_val]

    req = session.get if session else requests.get

    # 1. CafeGateInfo API 시도
    gate_api_url = f"https://apis.naver.com/cafe-web/cafe2/CafeGateInfo.json?cluburl={str_val}"
    try:
        res = req(gate_api_url, headers=DEFAULT_HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            cid = data.get("message", {}).get("result", {}).get("cafeInfoView", {}).get("cafeId")
            if cid:
                cid_int = int(cid)
                _CAFE_ID_CACHE[str_val] = cid_int
                return cid_int
    except Exception:
        pass

    # 2. HTML 메타 태그 정규식 폴백 시도
    try:
        res = req(f"https://cafe.naver.com/{str_val}", headers=DEFAULT_HEADERS, timeout=5)
        if res.status_code == 200:
            m = re.search(r'g_sClubId\s*=\s*["\'](\d+)["\']|clubid["\':\s=]+(\d+)', res.text, re.IGNORECASE)
            if m:
                found_id = m.group(1) or m.group(2)
                if found_id:
                    cid_int = int(found_id)
                    _CAFE_ID_CACHE[str_val] = cid_int
                    return cid_int
    except Exception:
        pass

    return None


def fetch_article_detail(
    cafe_id: int | str,
    article_id: int | str,
    art: str | None = None,
    session: requests.Session | None = None
) -> dict | None:
    """네이버 카페 Article API를 호출하여 게시글 상세 JSON을 가져옵니다.

    Args:
        cafe_id: 숫자 형태의 cafeId (문자열 clubname일 경우 내부에서 숫자 변환 시도)
        article_id: 게시글 번호
        art: 검색 결과에서 전달된 'art' 인증 파라미터 (있는 경우 통과율 증가)
        session: 재사용 가능한 requests.Session (선택)

    Returns:
        성공 시 API 응답 dict, 실패 시 None
    """
    if not cafe_id or not article_id:
        return None

    numeric_cafe_id = resolve_cafe_id(cafe_id, session=session)
    if not numeric_cafe_id:
        return None

    api_url = f"https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{numeric_cafe_id}/articles/{article_id}"

    headers = dict(DEFAULT_HEADERS)
    headers['Referer'] = f"https://cafe.naver.com/ca-fe/cafes/{numeric_cafe_id}/articles/{article_id}"

    params = {}
    if art:
        params['art'] = art

    req = session.get if session else requests.get

    try:
        res = req(api_url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            return res.json()
        return None
    except requests.RequestException:
        return None


def fetch_article_from_url(url: str, session: requests.Session | None = None) -> dict | None:
    """URL에서 cafe_id, article_id 및 art 토큰을 자동 추출하여 상세 정보를 조회."""
    cafe_id, article_id = extract_ids_from_url(url)
    if not cafe_id or not article_id:
        return None
    art = extract_art_token(url)
    return fetch_article_detail(cafe_id, article_id, art=art, session=session)


def is_sale_article(article_data: dict | None) -> bool:
    """Article API 응답 데이터를 기반으로 해당 글이 중고거래/판매글인지 판별.

    네이버 카페 Article API 스펙:
    - 일반 게시글: result.saleInfo is None (또는 누락)
    - 중고거래 판매글: result.saleInfo 에 가격(price), 상품상태 등 객체 포함
    """
    if not article_data or not isinstance(article_data, dict):
        return False

    result = article_data.get("result")
    if isinstance(result, dict):
        return result.get("saleInfo") is not None

    return article_data.get("saleInfo") is not None
