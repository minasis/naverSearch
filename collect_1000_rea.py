"""네이버 카페 최근 1,000건 REA 기반 하이브리드 수집 모듈.

- 1차: OpenAPI(또는 검색 탭)를 통해 최근 1,000건 후보 게시글 링크 확보
- 2차: REA(Article API)를 통해 상세 본문, 정확한 작성시간(초 단위), 작성자, 댓글수, 거래글(saleInfo) 검증
- 3차: 거래글 100% 필터링 (saleInfo is not None 또는 제목/본문 거래 키워드)
- 4차: 비공개/회원전용 글의 경우 검색 요약으로 자연스럽게 폴백(Fallback) 유지
- 5차: 엑셀 및 CSV로 저장하고 통계(소요시간, 시간범위, 거래글/유효글 건수) 집계 및 보고
"""

import os
import re
import sys
import time
import html
import random
from datetime import datetime
import requests
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from article_api import (
    fetch_article_from_url,
    is_sale_article,
)
from filters import is_trade_post
from parser import parse_cafe_search_results

load_dotenv()

# Windows 콘솔 UTF-8 출력 대응
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}


# 엑셀(openpyxl) 비호환 제어문자 제거 정규식
ILLEGAL_EXCEL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]')


def remove_illegal_excel_chars(val: object) -> object:
    """엑셀에 저장할 수 없는 제어문자를 안전하게 제거."""
    if isinstance(val, str):
        return ILLEGAL_EXCEL_CHARS_RE.sub('', val)
    return val


def clean_text(raw_text: str | None) -> str:
    """HTML 태그 제거 후 엔티티 디코딩 및 공백/제어문자 정리."""
    if not raw_text:
        return ""
    text = re.sub(r'<[^>]+>', '', raw_text)
    text = html.unescape(text)
    text = ILLEGAL_EXCEL_CHARS_RE.sub('', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_html_text(html_content: str | None) -> str:
    """HTML 태그 제거 및 텍스트 정제 (Excel 셀 한도 감안 최대 30,000자 제한 및 제어문자 제거)."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    text = ILLEGAL_EXCEL_CHARS_RE.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 30000:
        text = text[:30000] + "... [본문 축약]"
    return text


def format_timestamp(ts: int | float | None) -> str | None:
    """밀리초(ms) 또는 초 단위 타임스탬프를 'YYYY-MM-DD HH:MM:SS' 형식으로 변환."""
    if not ts:
        return None
    try:
        if ts > 1e11:  # milliseconds
            sec = ts / 1000.0
        else:
            sec = float(ts)
        return datetime.fromtimestamp(sec).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def parse_relative_time_to_dt(time_str: str) -> datetime | None:
    """작성시간 문자열(상대시간 또는 절대시간)을 datetime 객체로 변환 시도."""
    if not time_str or time_str in ("-", "회원전용", "비공개"):
        return None
    time_str = time_str.strip()
    now = datetime.now()

    # 1. 'YYYY-MM-DD HH:MM:SS'
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass

    # 2. 'YYYY.MM.DD.'
    m_date = re.match(r'(\d{4})\.(\d{1,2})\.(\d{1,2})\.?', time_str)
    if m_date:
        try:
            return datetime(int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3)))
        except ValueError:
            pass

    # 3. 방금 전 / 초 전
    if '방금' in time_str or '초 전' in time_str:
        return now

    # 4. 'N분 전'
    m_min = re.search(r'(\d+)\s*분\s*전', time_str)
    if m_min:
        return datetime.fromtimestamp(now.timestamp() - int(m_min.group(1)) * 60)

    # 5. 'N시간 전'
    m_hour = re.search(r'(\d+)\s*시간\s*전', time_str)
    if m_hour:
        return datetime.fromtimestamp(now.timestamp() - int(m_hour.group(1)) * 3600)

    # 6. 'N일 전'
    m_day = re.search(r'(\d+)\s*일\s*전', time_str)
    if m_day:
        return datetime.fromtimestamp(now.timestamp() - int(m_day.group(1)) * 86400)

    return None


def calculate_time_range(items: list[dict]) -> tuple[str, str, str]:
    """수집된 게시글 목록에서 최신 및 가장 오래된 글의 시간 범위 계산.

    Returns:
        (newest_time_str, oldest_time_str, human_readable_summary)
    """
    if not items:
        return "-", "-", "수집된 데이터 없음"

    valid_dts = []
    for it in items:
        raw_str = it.get("작성시간", "")
        dt = parse_relative_time_to_dt(raw_str)
        if dt:
            valid_dts.append((dt, raw_str))

    now = datetime.now()

    def _format_diff(dt: datetime | None, fallback: str) -> str:
        if not dt:
            return fallback
        diff_sec = max(0, int((now - dt).total_seconds()))
        if diff_sec < 60:
            return f"{diff_sec}초 전"
        if diff_sec < 3600:
            return f"{diff_sec // 60}분 전"
        if diff_sec < 86400:
            hours = diff_sec // 3600
            return f"{hours}시간 전"
        days = diff_sec / 86400.0
        return f"{days:.1f}일 전"

    if valid_dts:
        dt_newest, newest_str = max(valid_dts, key=lambda x: x[0])
        dt_oldest, oldest_str = min(valid_dts, key=lambda x: x[0])
        desc_newest = _format_diff(dt_newest, newest_str)
        desc_oldest = _format_diff(dt_oldest, oldest_str)
    else:
        newest_str = items[0].get("작성시간", "-")
        oldest_str = items[-1].get("작성시간", "-")
        desc_newest = newest_str
        desc_oldest = oldest_str

    summary = f"{desc_newest} ({newest_str}) ~ {desc_oldest} ({oldest_str})"
    return newest_str, oldest_str, summary


def fetch_candidates_from_openapi(
    query: str = "티맵",
    target_count: int = 1000,
    session: requests.Session | None = None
) -> list[dict]:
    """네이버 OpenAPI를 통해 최신순 게시글 1,000건 링크 확보."""
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        return []

    req = session.get if session else requests.get
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    candidates = []
    seen_links = set()

    print(f"\n[1단계: OpenAPI 후보군 링크 확보] '{query}' 최신 게시글 {target_count}건 수집 중...")

    # OpenAPI는 display 최대 100, start 최대 1000
    for start in range(1, target_count + 1, 100):
        url = "https://openapi.naver.com/v1/search/cafearticle.json"
        display = min(100, target_count - len(candidates))
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": "date"
        }

        try:
            res = req(url, headers=headers, params=params, timeout=10)
            if res.status_code != 200:
                print(f"[경고] OpenAPI 오류: HTTP {res.status_code}")
                break

            data = res.json()
            items = data.get("items", [])
            if not items:
                break

            for it in items:
                link = it.get("link", "")
                base_link = link.split("?")[0] if link else ""
                if not base_link or base_link in seen_links:
                    continue
                seen_links.add(base_link)

                candidates.append({
                    "link": link,
                    "title": clean_text(it.get("title", "")),
                    "desc": clean_text(it.get("description", "")),
                    "cafename": clean_text(it.get("cafename", "")),
                    "post_time": "-"
                })
                if len(candidates) >= target_count:
                    break

            print(f"  - [{start:>4}/1000] 후보군 누적: {len(candidates)}건...")
            time.sleep(0.05)

        except Exception as e:
            print(f"[오류] OpenAPI 수집 중 예외 발생: {e}")
            break

    print(f"[1단계 완료] 총 {len(candidates)}건의 고유 후보 게시글 링크 확보 완료.\n")
    return candidates


def fetch_candidates_from_web(
    query: str = "티맵",
    target_count: int = 1000,
    session: requests.Session | None = None,
    delay: float = 0.15
) -> list[dict]:
    """네이버 웹 검색 탭에서 최신순(sort=date) 게시글 후보군 수집 (폴백용)."""
    req = session.get if session else requests.get
    candidates = []
    seen_links = set()
    start = 1
    page_size = 30

    print(f"\n[1단계: 웹 검색 후보군 링크 확보] '{query}' 최신 게시글 {target_count}건 수집 중...")

    while len(candidates) < target_count:
        url = (
            f"https://search.naver.com/search.naver?"
            f"ssc=tab.cafe.all&query={requests.utils.quote(query)}&sort=date&start={start}"
        )
        try:
            res = req(url, headers=DEFAULT_HEADERS, timeout=10)
            if res.status_code != 200:
                print(f"[경고] 검색 응답 코드: {res.status_code}")
                break

            items = parse_cafe_search_results(res.text, exclude_trade=False)
            if not items:
                break

            added = 0
            for it in items:
                link = it.get("link", "")
                base_link = link.split("?")[0] if link else ""
                if not base_link or base_link in seen_links:
                    continue
                seen_links.add(base_link)
                candidates.append(it)
                added += 1
                if len(candidates) >= target_count:
                    break

            if added == 0:
                break

            start += page_size
            time.sleep(delay)

        except Exception as e:
            print(f"[오류] 후보 링크 수집 중 예외: {e}")
            break

    print(f"[1단계 완료] 총 {len(candidates)}건의 후보 링크 확보 완료.\n")
    return candidates


def fetch_search_candidates(
    query: str = "티맵",
    target_count: int = 1000,
    session: requests.Session | None = None
) -> list[dict]:
    """OpenAPI 우선 시도 후, 결과가 부족한 경우 웹 검색으로 후보군 확보."""
    if os.getenv("NAVER_CLIENT_ID") and os.getenv("NAVER_CLIENT_SECRET"):
        candidates = fetch_candidates_from_openapi(query=query, target_count=target_count, session=session)
        if len(candidates) >= min(target_count, 100):
            return candidates
    return fetch_candidates_from_web(query=query, target_count=target_count, session=session)


def process_candidate_with_rea(
    candidate: dict,
    session: requests.Session | None = None
) -> tuple[dict | None, bool]:
    """개별 후보 게시글에 대해 REA Article API를 적용하여 상세 메타데이터 추출 및 거래글 판별.

    Returns:
        (item_dict, is_trade)
        - is_trade가 True이면 item_dict는 None (거래글 제외)
        - is_trade가 False이면 정상 수집 데이터 반환
    """
    url = candidate.get("link", "")
    cafename = candidate.get("cafename", "")
    orig_title = candidate.get("title", "")
    orig_desc = candidate.get("desc", "")
    orig_time = candidate.get("post_time", "")

    article_json = None
    try:
        article_json = fetch_article_from_url(url, session=session)
    except Exception:
        pass

    if article_json and article_json.get("result"):
        # 1. REA 거래글 객체(saleInfo) 검증
        if is_sale_article(article_json):
            return None, True

        res_data = article_json["result"]
        art = res_data.get("article", {})
        subject = art.get("subject") or orig_title
        content_html = art.get("contentHtml", "")
        content_text = clean_html_text(content_html) if content_html else orig_desc

        # 2. 거래 키워드 및 카페명 복합 필터링
        if is_trade_post(cafename, subject, content_text):
            return None, True

        # 상세 메타데이터 추출
        write_ts = art.get("writeDate")
        exact_time = format_timestamp(write_ts) or orig_time

        writer_info = art.get("writer", {})
        writer_nick = writer_info.get("nick") if isinstance(writer_info, dict) else "비공개"

        comment_count = res_data.get("comments", {}).get("totalCount")
        if comment_count is None:
            comment_count = art.get("commentCount", 0)

        read_count = art.get("readCount", 0)
        menu_name = art.get("menu", {}).get("name", "") if isinstance(art.get("menu"), dict) else ""

        return {
            "작성시간": exact_time,
            "카페명": cafename,
            "게시판": menu_name,
            "제목": subject,
            "작성자": writer_nick,
            "댓글수": comment_count,
            "조회수": read_count,
            "본문": content_text,
            "게시글링크": url,
            "수집방식": "REA Article API (상세)"
        }, False

    # Fallback (비공개/회원전용/API 미응답)
    # 거래글 검증
    if is_trade_post(cafename, orig_title, orig_desc):
        return None, True

    return {
        "작성시간": orig_time if orig_time != "-" else "회원전용 (비공개)",
        "카페명": cafename,
        "게시판": "",
        "제목": orig_title,
        "작성자": "회원전용/미공개",
        "댓글수": 0,
        "조회수": 0,
        "본문": orig_desc,
        "게시글링크": url,
        "수집방식": "검색 요약 폴백 (회원전용)"
    }, False


def collect_1000_rea(
    query: str = "티맵",
    target_count: int = 1000,
    delay_range: tuple[float, float] = (0.15, 0.25)
) -> dict:
    """최근 1,000건 게시글을 REA Article API 및 100% 거래글 필터링으로 하이브리드 수집."""
    t_start = time.time()
    session = requests.Session()

    # 1단계: 1,000건 후보 게시글 링크 수집
    candidates = fetch_search_candidates(query=query, target_count=target_count, session=session)

    # 2단계: REA Article API 적용 및 거래글 필터링
    print(f"[2단계: REA Article API 상세 수집 및 거래글 판별 시작] 총 {len(candidates)}건...")
    valid_items = []
    trade_count = 0
    fallback_count = 0
    rea_count = 0

    for idx, cand in enumerate(candidates, start=1):
        item, is_trade = process_candidate_with_rea(cand, session=session)

        if is_trade:
            trade_count += 1
        elif item:
            item["번호"] = len(valid_items) + 1
            valid_items.append(item)
            if item.get("수집방식", "").startswith("REA"):
                rea_count += 1
            else:
                fallback_count += 1

        # 100건 단위 진행률 로그
        if idx % 100 == 0 or idx == len(candidates):
            pct = (idx / len(candidates)) * 100
            print(
                f"  - [{idx:>4}/{len(candidates)}] ({pct:5.1f}%) "
                f"유효 커뮤니티 글: {len(valid_items):>3}건 | "
                f"거래글 제외: {trade_count:>3}건 | "
                f"REA 상세: {rea_count:>3}건 | "
                f"폴백: {fallback_count:>3}건"
            )

        # IP 안전 딜레이 적용 (0.15 ~ 0.25초)
        sleep_time = random.uniform(delay_range[0], delay_range[1])
        time.sleep(sleep_time)

    elapsed_sec = time.time() - t_start
    elapsed_min = elapsed_sec / 60.0

    # 3단계: 시간 범위 계산
    newest_time, oldest_time, time_range_str = calculate_time_range(valid_items)

    # 4단계: 엑셀 및 CSV 저장
    df = pd.DataFrame(valid_items)
    # 컬럼 순서 정렬
    col_order = [
        "번호", "작성시간", "카페명", "게시판", "제목",
        "작성자", "댓글수", "조회수", "본문", "게시글링크", "수집방식"
    ]
    existing_cols = [c for c in col_order if c in df.columns]
    df = df[existing_cols]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_xlsx = f"티맵_최근1000건_REA_{timestamp}.xlsx"
    out_csv = f"티맵_최근1000건_REA_{timestamp}.csv"

    # 엑셀 저장 전 모든 문자열 컬럼의 비호환 제어문자 일괄 정제
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(remove_illegal_excel_chars)

    df.to_excel(out_xlsx, index=False)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    # 구글 드라이브(독후감소스) 동시 백업
    gdrive_dir = r"G:\내 드라이브\독후감소스"
    if os.path.exists(gdrive_dir):
        try:
            gdrive_xlsx = os.path.join(gdrive_dir, out_xlsx)
            gdrive_latest = os.path.join(gdrive_dir, "티맵_최근1000건_최신_REA.xlsx")
            df.to_excel(gdrive_xlsx, index=False)
            df.to_excel(gdrive_latest, index=False)
            print(f"[백업] 구글 드라이브 동시 백업 완료: {gdrive_latest}")
        except Exception as e:
            print(f"[경고] 구글 드라이브 백업 중 예외: {e}")

    # 결과 통계 출력
    print("\n" + "=" * 65)
    print(f"🎉 티맵 최근 {len(candidates)}건 REA 하이브리드 수집 완료!")
    print(f"  - 엑셀 파일: {os.path.abspath(out_xlsx)}")
    print(f"  - CSV 파일 : {os.path.abspath(out_csv)}")
    print(f"  - 총 소요 시간: {elapsed_sec:.1f}초 ({elapsed_min:.2f}분)")
    print(f"  - 수집 시간 범위: {time_range_str}")
    print(f"  - 거래글 제외 건수: {trade_count}건 (100% 필터링 적용)")
    print(f"  - 유효 커뮤니티 글: {len(valid_items)}건 (REA: {rea_count}건, 폴백: {fallback_count}건)")
    print("=" * 65 + "\n")

    return {
        "excel_path": os.path.abspath(out_xlsx),
        "csv_path": os.path.abspath(out_csv),
        "total_candidates": len(candidates),
        "valid_count": len(valid_items),
        "trade_excluded_count": trade_count,
        "rea_count": rea_count,
        "fallback_count": fallback_count,
        "elapsed_seconds": elapsed_sec,
        "elapsed_minutes": elapsed_min,
        "newest_time": newest_time,
        "oldest_time": oldest_time,
        "time_range_str": time_range_str,
    }


def main():
    collect_1000_rea(query="티맵", target_count=1000)


if __name__ == "__main__":
    main()
