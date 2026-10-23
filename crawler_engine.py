"""네이버 카페 검색 및 REA 하이브리드 크롤링 엔진 모듈.

단일 책임을 갖는 핵심 수집 엔진으로, 다음 기능을 통합 제공합니다:
1. 시작일~종료일 범위 검증 (최대 5일 제한, 5일 초과 시 ValueError)
2. 네이버 검색 날짜 범위 필터 (nso=so:dd,p:from{start}to{end})를 통한 후보군 수집
3. REA Article API 상세 메타데이터 조회 및 비공개/회원전용 글 자연스러운 폴백
4. 거래글 100% 자동 필터링 (saleInfo 객체 유무 + 거래 키워드 및 카페명 복합 검증)
5. 진행률 콜백(progress_callback) 및 pandas DataFrame 반환
"""

import html
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Callable

import pandas as pd
import requests
from bs4 import BeautifulSoup
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from article_api import fetch_article_from_url, is_sale_article
from filters import is_trade_post
from parser import parse_cafe_search_results

DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}

COLUMNS = [
    "번호",
    "작성시간",
    "카페명",
    "게시판",
    "제목",
    "작성자",
    "댓글수",
    "조회수",
    "본문",
    "이미지수",
    "이미지목록",
    "게시글링크",
    "수집방식",
]


def extract_images_from_html(html_str: str | None) -> list[str]:
    """HTML 본문에서 유효한 첨부 이미지 URL 목록을 추출 (중복 제거 및 순서 보장).

    - <img> 태그의 data-url, data-src, data-lazy-src, data-original, src 속성 탐색
    - 1x1 트래킹 픽셀, 기본 아이콘, 스티커/이모티콘, 공백 이미지 필터링
    - naver cafe 이미지 CDN(pstatic.net, cafeptthumb, phinf 등) 보존
    - 순서 보장 중복 제거
    """
    if not html_str or not isinstance(html_str, str):
        return []

    soup = BeautifulSoup(html_str, 'html.parser')
    images = []
    seen = set()

    for img in soup.find_all('img'):
        # 1x1 또는 0x0 추적 픽셀 필터링
        w = str(img.get('width', '')).strip()
        h = str(img.get('height', '')).strip()
        if w in ('0', '1') or h in ('0', '1'):
            continue

        # 유효한 URL 속성 후보군 (data-url, data-src, data-lazy-src, src 순서)
        candidate_urls = []
        for attr in ('data-url', 'data-src', 'data-lazy-src', 'data-original', 'src'):
            val = img.get(attr)
            if val and isinstance(val, str) and val.strip():
                candidate_urls.append(val.strip())

        chosen_url = None
        for raw_url in candidate_urls:
            raw_url = html.unescape(raw_url).strip()
            if raw_url.startswith('//'):
                raw_url = 'https:' + raw_url

            if not (raw_url.startswith('http://') or raw_url.startswith('https://')):
                continue

            lower_url = raw_url.lower()

            # 트래킹 픽셀, 기본 아이콘, 스티커/이모티콘 필터링
            ignore_keywords = [
                'blank.gif', 'spacer.gif', 'pixel.gif', 'transparent.gif', '1x1',
                '/static/cafe/icon', '/static/pstatic/', 'emoticon', 'sticker',
                'ico_', 'btn_', 'spinner', 'loading'
            ]
            if any(k in lower_url for k in ignore_keywords):
                continue

            chosen_url = raw_url
            break

        if chosen_url and chosen_url not in seen:
            seen.add(chosen_url)
            images.append(chosen_url)

    return images


def format_df_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """엑셀 저장을 위해 리스트 형태의 열(이미지목록 등)을 줄바꿈 문자열로 변환한 사본 반환."""
    excel_df = df.copy()
    if "이미지목록" in excel_df.columns:
        excel_df["이미지목록"] = excel_df["이미지목록"].apply(
            lambda x: "\n".join(x) if isinstance(x, (list, tuple)) else (str(x) if x else "")
        )
    return excel_df


def clean_text(raw_text: str | None) -> str:
    """HTML 태그 제거 후 엔티티 디코딩 및 공백/엑셀 제어문자 정리."""
    if not raw_text:
        return ""
    text = re.sub(r'<[^>]+>', '', raw_text)
    text = html.unescape(text)
    text = ILLEGAL_CHARACTERS_RE.sub('', text)
    return re.sub(r'\s+', ' ', text).strip()


def clean_html_text(html_content: str | None, max_len: int = 30000) -> str:
    """HTML 본문 텍스트 정제 (Excel 셀 한도 감안 최대 30,000자 제한 및 제어문자 제거)."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    text = ILLEGAL_CHARACTERS_RE.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "... [본문 축약]"
    return text


KST = timezone(timedelta(hours=9))


def format_timestamp(ts: int | float | None) -> str | None:
    """밀리초(ms) 또는 초 단위 타임스탬프를 한국 표준시(KST, UTC+9) 'YYYY-MM-DD HH:MM:SS' 형식으로 변환."""
    if not ts:
        return None
    try:
        sec = ts / 1000.0 if ts > 1e11 else float(ts)
        return datetime.fromtimestamp(sec, tz=KST).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def parse_date_str(date_str: str) -> datetime:
    """문자열 형태의 날짜(YYYY-MM-DD, YYYY.MM.DD, YYYYMMDD)를 datetime 객체로 변환."""
    if not date_str or not isinstance(date_str, str):
        raise ValueError("날짜 문자열이 비어있거나 올바르지 않습니다.")
    clean = re.sub(r'[^0-9]', '', date_str.strip())
    if len(clean) != 8:
        raise ValueError(f"유효하지 않은 날짜 형식입니다: '{date_str}' (YYYY-MM-DD 또는 YYYYMMDD 필요)")
    try:
        return datetime.strptime(clean, "%Y%m%d")
    except ValueError as e:
        raise ValueError(f"유효하지 않은 날짜 값입니다: '{date_str}'") from e


def validate_date_range(start_date: str, end_date: str, max_days: int = 5) -> tuple[datetime, datetime]:
    """시작일과 종료일의 범위를 검증하고 datetime 튜플을 반환.

    - 시작일이 종료일보다 늦으면 ValueError.
    - 선택된 날짜 기간(포함 일수)이 max_days를 초과하면 ValueError.
    """
    start_dt = parse_date_str(start_date)
    end_dt = parse_date_str(end_date)

    if start_dt > end_dt:
        raise ValueError("시작일은 종료일보다 이전이어야 합니다.")

    diff_days = (end_dt.date() - start_dt.date()).days + 1
    if diff_days > max_days:
        raise ValueError(
            f"검색 기간은 최대 {max_days}일까지만 선택 가능합니다. (선택된 기간: {diff_days}일)"
        )

    return start_dt, end_dt


class CrawlerEngine:
    """네이버 카페 REA 하이브리드 크롤링 엔진 클래스."""

    def __init__(self, session: requests.Session | None = None, max_workers: int = 20):
        if session:
            self.session = session
        else:
            self.session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=40, pool_maxsize=40, max_retries=1)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
        self.max_workers = max_workers
        self.last_summary: dict = {}

    def fetch_candidates(
        self,
        query: str,
        start_dt: datetime,
        end_dt: datetime,
        max_candidates: int = 1000,
        delay: float = 0.1
    ) -> list[dict]:
        """네이버 웹 검색 카페 탭에서 비동기 무한스크롤(s.search) 연동으로 후보군 목록을 수집."""
        start_nso = start_dt.strftime("%Y%m%d")
        end_nso = end_dt.strftime("%Y%m%d")
        nso = f"so:dd,p:from{start_nso}to{end_nso}"

        candidates = []
        seen_links = set()

        page1_url = (
            f"https://search.naver.com/search.naver?"
            f"ssc=tab.cafe.all&query={urllib.parse.quote(query)}&sort=date&nso={nso}"
        )

        # 1. 1페이지 수집 및 초기 후보군 추출
        try:
            res = self.session.get(page1_url, headers=DEFAULT_HEADERS, timeout=10)
            if res.status_code != 200:
                return candidates

            items = parse_cafe_search_results(res.text, exclude_trade=False)
            for it in items:
                link = it.get("link", "")
                base_link = link.split("?")[0] if link else ""
                if not base_link or base_link in seen_links:
                    continue
                seen_links.add(base_link)
                candidates.append(it)
                if len(candidates) >= max_candidates:
                    return candidates

            # 1페이지 HTML에서 s.search 비동기 무한스크롤 다음 페이지 URL 추출
            match = re.search(r'https://s\.search\.naver\.com/p/cafe/\d+/search\.naver\?[^\s"\'<>]+', res.text)
            next_url = html.unescape(match.group(0)) if match else None
        except Exception:
            return candidates

        # 2. 2페이지 이상 후속 비동기 무한스크롤 페이지 연쇄 수집 (Token-Chained Pagination)
        while next_url and len(candidates) < max_candidates:
            time.sleep(delay)
            try:
                headers = {**DEFAULT_HEADERS, 'Referer': page1_url}
                res = self.session.get(next_url, headers=headers, timeout=10)
                if res.status_code != 200:
                    break

                data = res.json()
                collections = data.get("collection", [{}])
                items_html = ""
                if isinstance(collections, list) and collections and isinstance(collections[0], dict):
                    items_html = collections[0].get("html", "")
                elif isinstance(collections, dict):
                    items_html = collections.get("html", "")

                if not items_html:
                    break

                items = parse_cafe_search_results(items_html, exclude_trade=False)
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
                    if len(candidates) >= max_candidates:
                        break

                if added == 0:
                    break

                # 3페이지 이후 다음 URL 추출 (data['url'] 우선, 미존재 시 응답 텍스트 정규식 검색)
                next_candidate = data.get("url")
                if next_candidate:
                    next_url = html.unescape(str(next_candidate))
                    if next_url.startswith("//"):
                        next_url = "https:" + next_url
                    elif next_url.startswith("/"):
                        next_url = "https://s.search.naver.com" + next_url
                else:
                    m = re.search(r'https://s\.search\.naver\.com/p/cafe/\d+/search\.naver\?[^\s"\'<>]+', res.text)
                    next_url = html.unescape(m.group(0)) if m else None

                if not next_url:
                    break
            except Exception:
                break

        return candidates

    def process_candidate(self, candidate: dict) -> tuple[dict | None, bool]:
        """개별 후보 게시글에 대해 REA Article API 및 거래글 필터를 적용.

        Returns:
            (item_dict, is_trade)
            - is_trade: True이면 거래글로 판별되어 제외 (item_dict는 None)
            - is_trade: False이면 정상 수집 딕셔너리 반환
        """
        url = candidate.get("link", "")
        cafename = clean_text(candidate.get("cafename", ""))
        orig_title = clean_text(candidate.get("title", ""))
        orig_desc = clean_text(candidate.get("desc", ""))
        orig_time = candidate.get("post_time", "")

        # 1. 1차 기본 키워드/카페명 필터링 (가장 빠른 탈락)
        if is_trade_post(cafename, orig_title, orig_desc):
            return None, True

        # 2. REA Article API 상세 조회
        article_json = None
        try:
            article_json = fetch_article_from_url(url, session=self.session)
        except Exception:
            pass

        if article_json and article_json.get("result"):
            # 2-1. REA saleInfo 객체 검증 (100% 확실한 거래글)
            if is_sale_article(article_json):
                return None, True

            res_data = article_json["result"]
            art = res_data.get("article", {})
            subject = clean_text(art.get("subject") or orig_title)
            content_html = art.get("contentHtml", "")
            content_text = clean_html_text(content_html) if content_html else orig_desc

            # 2-2. 상세 본문 대상 2차 거래 키워드 필터링
            if is_trade_post(cafename, subject, content_text):
                return None, True

            write_ts = art.get("writeDate")
            exact_time = format_timestamp(write_ts) or orig_time

            writer_info = art.get("writer", {})
            writer_nick = clean_text(writer_info.get("nick")) if isinstance(writer_info, dict) else "비공개"

            comment_count = res_data.get("comments", {}).get("totalCount")
            if comment_count is None:
                comment_count = art.get("commentCount", 0)

            read_count = art.get("readCount", 0)
            menu_info = art.get("menu", {})
            menu_name = clean_text(menu_info.get("name", "")) if isinstance(menu_info, dict) else ""

            images = extract_images_from_html(content_html) if content_html else []

            return {
                "번호": 0,
                "작성시간": exact_time,
                "카페명": cafename,
                "게시판": menu_name,
                "제목": subject,
                "작성자": writer_nick,
                "댓글수": comment_count,
                "조회수": read_count,
                "본문": content_text,
                "이미지수": len(images),
                "이미지목록": images,
                "게시글링크": url,
                "수집방식": "REA Article API (상세)"
            }, False

        # 3. 비공개/회원전용 글 폴백 (검색 요약 활용)
        return {
            "번호": 0,
            "작성시간": orig_time if orig_time and orig_time != "-" else "회원전용 (비공개)",
            "카페명": cafename,
            "게시판": "",
            "제목": orig_title,
            "작성자": "회원전용/미공개",
            "댓글수": 0,
            "조회수": 0,
            "본문": orig_desc,
            "이미지수": 0,
            "이미지목록": [],
            "게시글링크": url,
            "수집방식": "검색 요약 폴백 (회원전용)"
        }, False

    def search_and_collect(
        self,
        query: str,
        start_date: str,
        end_date: str,
        max_days: int = 5,
        progress_callback: Callable[[int, int, str], None] | None = None,
        max_candidates: int = 1000,
        max_workers: int | None = None
    ) -> pd.DataFrame:
        """지정된 기간(최대 5일)의 네이버 카페 검색 결과를 수집하고 DataFrame으로 반환."""
        start_dt, end_dt = validate_date_range(start_date, end_date, max_days=max_days)

        if progress_callback:
            progress_callback(0, 0, f"'{query}' 네이버 카페 검색 후보군 수집 시작 ({start_date} ~ {end_date})...")

        candidates = self.fetch_candidates(
            query=query,
            start_dt=start_dt,
            end_dt=end_dt,
            max_candidates=max_candidates
        )

        total_candidates = len(candidates)
        valid_items = []
        trade_count = 0
        workers = max_workers or self.max_workers

        if total_candidates > 0:
            results = [None] * total_candidates
            completed_count = 0
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(self.process_candidate, cand): idx
                    for idx, cand in enumerate(candidates)
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    results[idx] = future.result()
                    completed_count += 1
                    if progress_callback:
                        progress_callback(
                            completed_count,
                            total_candidates,
                            f"[{completed_count}/{total_candidates}] REA 분석 및 거래글 필터링 중..."
                        )

            for item, is_trade in results:
                if is_trade:
                    trade_count += 1
                elif item:
                    item["번호"] = len(valid_items) + 1
                    valid_items.append(item)

        if valid_items:
            df = pd.DataFrame(valid_items, columns=COLUMNS)
        else:
            df = pd.DataFrame(columns=COLUMNS)

        summary = {
            "query": query,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "total_candidates": total_candidates,
            "trade_excluded": trade_count,
            "valid_count": len(valid_items),
        }
        df.attrs = summary
        self.last_summary = summary

        if progress_callback:
            progress_callback(
                total_candidates,
                total_candidates,
                f"수집 완료: 총 {total_candidates}건 중 유효 {len(valid_items)}건 (거래글 {trade_count}건 제외)"
            )

        return df


def search_and_collect(
    query: str,
    start_date: str,
    end_date: str,
    max_days: int = 5,
    progress_callback: Callable[[int, int, str], None] | None = None,
    max_candidates: int = 1000,
    session: requests.Session | None = None,
    max_workers: int = 20
) -> pd.DataFrame:
    """search_and_collect 편의 함수."""
    engine = CrawlerEngine(session=session, max_workers=max_workers)
    return engine.search_and_collect(
        query=query,
        start_date=start_date,
        end_date=end_date,
        max_days=max_days,
        progress_callback=progress_callback,
        max_candidates=max_candidates,
        max_workers=max_workers
    )
