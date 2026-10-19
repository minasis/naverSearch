import unittest
import os
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock
import pandas as pd

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from crawler_engine import (
    validate_date_range,
    parse_date_str,
    CrawlerEngine,
    search_and_collect,
)


class TestCrawlerEngine(unittest.TestCase):
    """크롤링 엔진 모듈(crawler_engine.py) 단위 테스트 스위트."""

    # ----------------------------------------------------
    # 1. 날짜 파싱 및 유효성 검증 테스트
    # ----------------------------------------------------
    def test_parse_date_str_formats(self):
        """다양한 날짜 형식(YYYY-MM-DD, YYYYMMDD, YYYY.MM.DD) 파싱 검증."""
        d1 = parse_date_str("2026-10-15")
        self.assertEqual(d1, datetime(2026, 10, 15))

        d2 = parse_date_str("20261015")
        self.assertEqual(d2, datetime(2026, 10, 15))

        d3 = parse_date_str("2026.10.15")
        self.assertEqual(d3, datetime(2026, 10, 15))

    def test_parse_date_str_invalid(self):
        """잘못된 날짜 형식 입력 시 ValueError 발생 검증."""
        with self.assertRaises(ValueError):
            parse_date_str("invalid-date")
        with self.assertRaises(ValueError):
            parse_date_str("2026-13-45")

    def test_validate_date_range_valid(self):
        """1일~5일 이내 정상 범위 검증."""
        # 1일 (동일 날짜)
        s, e = validate_date_range("2026-10-15", "2026-10-15", max_days=5)
        self.assertEqual(s, datetime(2026, 10, 15))
        self.assertEqual(e, datetime(2026, 10, 15))

        # 정확히 5일 (15, 16, 17, 18, 19)
        s, e = validate_date_range("2026-10-15", "2026-10-19", max_days=5)
        self.assertEqual((e.date() - s.date()).days + 1, 5)

    def test_validate_date_range_exceed_max_days(self):
        """5일 초과(예: 6일) 선택 시 ValueError 발생 검증."""
        with self.assertRaises(ValueError) as ctx:
            validate_date_range("2026-10-15", "2026-10-20", max_days=5)
        self.assertIn("최대 5일", str(ctx.exception))

    def test_validate_date_range_start_after_end(self):
        """시작일이 종료일보다 늦은 역순 입력 시 ValueError 발생 검증."""
        with self.assertRaises(ValueError) as ctx:
            validate_date_range("2026-10-20", "2026-10-15", max_days=5)
        self.assertIn("시작일은 종료일보다 이전이어야 합니다", str(ctx.exception))

    # ----------------------------------------------------
    # 2. 거래글 제외 및 REA 상세 처리 검증
    # ----------------------------------------------------
    def test_process_candidate_trade_exclusion(self):
        """거래 키워드나 카페명이 포함된 글은 거래글로 제외되는지 검증."""
        engine = CrawlerEngine()
        trade_cand = {
            "link": "https://cafe.naver.com/joonggonara/123",
            "cafename": "중고나라",
            "title": "티맵 네비게이션 팝니다",
            "desc": "10000원에 판매합니다",
            "post_time": "1시간 전"
        }
        item, is_trade = engine.process_candidate(trade_cand)
        self.assertTrue(is_trade)
        self.assertIsNone(item)

    @patch('crawler_engine.fetch_article_from_url')
    def test_process_candidate_rea_sale_info_exclusion(self, mock_fetch):
        """Article API 응답에 saleInfo가 있는 경우 거래글로 100% 제외 검증."""
        mock_fetch.return_value = {
            "result": {
                "article": {"subject": "상품 안내"},
                "saleInfo": {"price": 30000}
            }
        }
        engine = CrawlerEngine()
        cand = {
            "link": "https://cafe.naver.com/testcafe/123",
            "cafename": "일반카페",
            "title": "상품 안내",
            "desc": "설명",
            "post_time": "1시간 전"
        }
        item, is_trade = engine.process_candidate(cand)
        self.assertTrue(is_trade)
        self.assertIsNone(item)

    @patch('crawler_engine.fetch_article_from_url')
    def test_process_candidate_normal_community_success(self, mock_fetch):
        """일반 커뮤니티 글은 REA 상세 정보와 함께 정상 추출 검증."""
        mock_fetch.return_value = {
            "result": {
                "article": {
                    "subject": "티맵 길안내 기능 추천합니다",
                    "contentHtml": "<p>티맵 이번 업데이트 아주 좋네요.</p>",
                    "writeDate": 1729000000000,
                    "writer": {"nick": "티맵러버"},
                    "commentCount": 3,
                    "readCount": 150,
                    "menu": {"name": "자유게시판"}
                },
                "saleInfo": None
            }
        }
        engine = CrawlerEngine()
        cand = {
            "link": "https://cafe.naver.com/testcafe/123",
            "cafename": "자동차동호회",
            "title": "티맵 길안내 기능 추천합니다",
            "desc": "요약",
            "post_time": "1시간 전"
        }
        item, is_trade = engine.process_candidate(cand)
        self.assertFalse(is_trade)
        self.assertIsNotNone(item)
        self.assertEqual(item["제목"], "티맵 길안내 기능 추천합니다")
        self.assertEqual(item["작성자"], "티맵러버")
        self.assertEqual(item["댓글수"], 3)
        self.assertEqual(item["조회수"], 150)
        self.assertEqual(item["본문"], "티맵 이번 업데이트 아주 좋네요.")

    # ----------------------------------------------------
    # 3. search_and_collect 통합 흐름 검증
    # ----------------------------------------------------
    @patch('crawler_engine.CrawlerEngine.fetch_candidates')
    @patch('crawler_engine.CrawlerEngine.process_candidate')
    def test_search_and_collect_workflow(self, mock_process, mock_fetch):
        """search_and_collect 실행 시 5일 검증, 후보 수집, REA 처리 및 DataFrame 생성 검증."""
        mock_fetch.return_value = [
            {"link": "https://cafe.naver.com/c1/1", "title": "글1"},
            {"link": "https://cafe.naver.com/c1/2", "title": "글2 (거래글)"},
        ]
        mock_process.side_effect = [
            ({"번호": 1, "제목": "글1", "카페명": "카페1", "작성시간": "2026-10-15 10:00:00"}, False),
            (None, True),  # 거래글 제외
        ]

        progress_calls = []

        def cb(curr, total, msg):
            progress_calls.append((curr, total, msg))

        df = search_and_collect(
            query="티맵",
            start_date="2026-10-15",
            end_date="2026-10-18",
            max_days=5,
            progress_callback=cb
        )

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.attrs["total_candidates"], 2)
        self.assertEqual(df.attrs["trade_excluded"], 1)
        self.assertEqual(df.attrs["valid_count"], 1)
        self.assertEqual(len(progress_calls), 4)


if __name__ == '__main__':
    unittest.main()
