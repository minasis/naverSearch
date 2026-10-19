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
from datetime import datetime
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
    "게시글링크",
    "수집방식",
]


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


def format_timestamp(ts: int | float | None) -> str | None:
    """밀리초(ms) 또는 초 단위 타임스탬프를 'YYYY-MM-DD HH:MM:SS' 형식으로 변환."""
    if not ts:
        return None
    try:
        sec = ts / 1000.0 if ts > 1e11 else float(ts)
        return datetime.fromtimestamp(sec).strftime('%Y-%m-%d %H:%M:%S')
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

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.last_summary: dict = {}

    def fetch_candidates(
        self,
        query: str,
        start_dt: datetime,
        end_dt: datetime,
        max_candidates: int = 1000,
        delay: float = 0.1
    ) -> list[dict]:
        """네이버 웹 검색 카페 탭에서 지정된 날짜 범위의 게시글 후보군 목록을 수집."""
        start_nso = start_dt.strftime("%Y%m%d")
        end_nso = end_dt.strftime("%Y%m%d")
        nso = f"so:dd,p:from{start_nso}to{end_nso}"

        candidates = []
        seen_links = set()
        start = 1
        page_size = 30

        while len(candidates) < max_candidates:
            url = (
                f"https://search.naver.com/search.naver?"
                f"ssc=tab.cafe.all&query={urllib.parse.quote(query)}&sort=date&nso={nso}&start={start}"
            )
            try:
                res = self.session.get(url, headers=DEFAULT_HEADERS, timeout=10)
                if res.status_code != 200:
                    break

                # 파서 호출 (초기 파싱 단계에서는 거래글도 포함하여 candidate로 수집한 뒤 REA 단계에서 정확히 집계)
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
                    if len(candidates) >= max_candidates:
                        break

                if added == 0:
                    break

                start += page_size
                time.sleep(delay)
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
        max_candidates: int = 1000
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

        for idx, cand in enumerate(candidates, start=1):
            item, is_trade = self.process_candidate(cand)
            if is_trade:
                trade_count += 1
            elif item:
                item["번호"] = len(valid_items) + 1
                valid_items.append(item)

            if progress_callback:
                progress_callback(
                    idx,
                    total_candidates,
                    f"[{idx}/{total_candidates}] REA 분석 및 거래글 필터링 중..."
                )

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
    session: requests.Session | None = None
) -> pd.DataFrame:
    """search_and_collect 편의 함수."""
    engine = CrawlerEngine(session=session)
    return engine.search_and_collect(
        query=query,
        start_date=start_date,
        end_date=end_date,
        max_days=max_days,
        progress_callback=progress_callback,
        max_candidates=max_candidates
    )
