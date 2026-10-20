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
    format_timestamp,
    CrawlerEngine,
    search_and_collect,
    extract_images_from_html,
    format_df_for_excel,
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

    def test_format_timestamp_kst(self):
        """서버 타임존(UTC)과 무관하게 KST(UTC+9)로 정확히 변환되는지 검증."""
        # 1792416356553 ms = 2026-10-19 13:25:56 UTC -> 2026-10-19 22:25:56 KST
        res = format_timestamp(1792416356553)
        self.assertEqual(res, "2026-10-19 22:25:56")

        res_sec = format_timestamp(1792416356)
        self.assertEqual(res_sec, "2026-10-19 22:25:56")

        self.assertIsNone(format_timestamp(None))
        self.assertIsNone(format_timestamp("invalid"))

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
        self.assertEqual(item["이미지수"], 0)
        self.assertEqual(item["이미지목록"], [])

    @patch('crawler_engine.fetch_article_from_url')
    def test_process_candidate_with_images_success(self, mock_fetch):
        """본문에 첨부 이미지가 있는 커뮤니티 글의 이미지 수 및 목록 추출 검증."""
        mock_fetch.return_value = {
            "result": {
                "article": {
                    "subject": "티맵 HUD 장착 사진 공유합니다",
                    "contentHtml": (
                        '<p>HUD 연결 화면입니다.</p>'
                        '<img src="https://cafeptthumb-phinf.pstatic.net/test1.jpg?type=w800">'
                        '<img data-src="https://phinf.pstatic.net/test2.png">'
                        '<img src="https://cafeptthumb-phinf.pstatic.net/test1.jpg?type=w800">'  # 중복
                    ),
                    "writeDate": 1729000000000,
                    "writer": {"nick": "티맵유저"},
                    "commentCount": 5,
                    "readCount": 200,
                    "menu": {"name": "포토갤러리"}
                },
                "saleInfo": None
            }
        }
        engine = CrawlerEngine()
        cand = {
            "link": "https://cafe.naver.com/testcafe/456",
            "cafename": "자동차동호회",
            "title": "티맵 HUD 장착 사진 공유합니다",
            "desc": "요약",
            "post_time": "1시간 전"
        }
        item, is_trade = engine.process_candidate(cand)
        self.assertFalse(is_trade)
        self.assertIsNotNone(item)
        self.assertEqual(item["이미지수"], 2)
        self.assertEqual(item["이미지목록"], [
            "https://cafeptthumb-phinf.pstatic.net/test1.jpg?type=w800",
            "https://phinf.pstatic.net/test2.png"
        ])

    def test_process_candidate_fallback_images(self):
        """회원전용 폴백 글의 이미지수(0) 및 빈 이미지목록([]) 검증."""
        engine = CrawlerEngine()
        cand = {
            "link": "https://cafe.naver.com/privatecafe/999",
            "cafename": "비공개카페",
            "title": "비공개 글 제목",
            "desc": "검색 스니펫 설명",
            "post_time": "2026-10-18"
        }
        item, is_trade = engine.process_candidate(cand)
        self.assertFalse(is_trade)
        self.assertEqual(item["이미지수"], 0)
        self.assertEqual(item["이미지목록"], [])

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

    # ----------------------------------------------------
    # 4. fetch_candidates 비동기 무한스크롤(s.search) 연쇄 수집 검증
    # ----------------------------------------------------
    def test_fetch_candidates_single_page_no_async_url(self):
        """1페이지 결과만 있고 비동기 다음 페이지 URL이 없는 경우 1페이지만 정상 반환 후 종료 검증."""
        mock_session = MagicMock()
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.text = """
        <li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/1">제목 1</a><a class="name">카페1</a></li>
        """
        mock_session.get.return_value = mock_res

        engine = CrawlerEngine(session=mock_session)
        cands = engine.fetch_candidates("티맵", datetime(2026, 10, 15), datetime(2026, 10, 15), delay=0)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["title"], "제목 1")
        self.assertEqual(mock_session.get.call_count, 1)

    def test_fetch_candidates_token_chained_multi_page(self):
        """s.search 무한스크롤 연쇄 토큰 페이징을 통해 30건을 초과하는 다중 페이지 수집 및 Referer 헤더 검증."""
        mock_session = MagicMock()

        # 1페이지 (HTML 내 &amp; 포함된 s.search URL 추출)
        res_p1 = MagicMock()
        res_p1.status_code = 200
        res_p1.text = """
        <li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/1">글 1</a><a class="name">카페1</a></li>
        <script>var next = "https://s.search.naver.com/p/cafe/48/search.naver?query=test&amp;start=31";</script>
        """

        # 2페이지 (JSON 응답 및 다음 페이지 3 URL 포함)
        res_p2 = MagicMock()
        res_p2.status_code = 200
        res_p2.json.return_value = {
            "collection": [{
                "html": '<li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/2">글 2</a><a class="name">카페1</a></li>'
            }],
            "url": "https://s.search.naver.com/p/cafe/48/search.naver?query=test&start=61"
        }
        res_p2.text = ""

        # 3페이지 (JSON 응답 및 더 이상 다음 URL 없음)
        res_p3 = MagicMock()
        res_p3.status_code = 200
        res_p3.json.return_value = {
            "collection": [{
                "html": '<li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/3">글 3</a><a class="name">카페1</a></li>'
            }],
            "url": None
        }
        res_p3.text = ""

        mock_session.get.side_effect = [res_p1, res_p2, res_p3]

        engine = CrawlerEngine(session=mock_session)
        cands = engine.fetch_candidates("티맵", datetime(2026, 10, 15), datetime(2026, 10, 15), delay=0)

        self.assertEqual(len(cands), 3)
        self.assertEqual([c["title"] for c in cands], ["글 1", "글 2", "글 3"])
        self.assertEqual(mock_session.get.call_count, 3)

        # 2페이지 호출 시 Referer 헤더 및 &amp; 치환 검증
        call2_args, call2_kwargs = mock_session.get.call_args_list[1]
        self.assertTrue(call2_args[0].startswith("https://s.search.naver.com/p/cafe/48/search.naver?query=test&start=31"))
        self.assertIn("Referer", call2_kwargs["headers"])
        self.assertIn("search.naver.com", call2_kwargs["headers"]["Referer"])

    def test_fetch_candidates_max_candidates_limit(self):
        """max_candidates 목표 수량 도달 시 즉시 중단 검증."""
        mock_session = MagicMock()
        res_p1 = MagicMock()
        res_p1.status_code = 200
        res_p1.text = """
        <li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/1">글 1</a><a class="name">카페1</a></li>
        <li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/2">글 2</a><a class="name">카페1</a></li>
        <script>var next = "https://s.search.naver.com/p/cafe/48/search.naver?query=test&start=31";</script>
        """
        res_p2 = MagicMock()
        res_p2.status_code = 200
        res_p2.json.return_value = {
            "collection": [{
                "html": (
                    '<li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/3">글 3</a><a class="name">카페1</a></li>'
                    '<li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/4">글 4</a><a class="name">카페1</a></li>'
                )
            }],
            "url": "https://s.search.naver.com/p/cafe/48/search.naver?query=test&start=61"
        }
        mock_session.get.side_effect = [res_p1, res_p2]

        engine = CrawlerEngine(session=mock_session)
        cands = engine.fetch_candidates(
            "티맵", datetime(2026, 10, 15), datetime(2026, 10, 15), max_candidates=3, delay=0
        )
        self.assertEqual(len(cands), 3)
        self.assertEqual([c["title"] for c in cands], ["글 1", "글 2", "글 3"])

    def test_fetch_candidates_deduplication(self):
        """페이지 간 중복 URL(쿼리스트링 차이 포함) 중복 제거 검증."""
        mock_session = MagicMock()
        res_p1 = MagicMock()
        res_p1.status_code = 200
        res_p1.text = """
        <li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/1?param=a">글 1</a><a class="name">카페1</a></li>
        <script>var next = "https://s.search.naver.com/p/cafe/48/search.naver?query=test&start=31";</script>
        """
        res_p2 = MagicMock()
        res_p2.status_code = 200
        res_p2.json.return_value = {
            "collection": [{
                "html": (
                    '<li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/1?param=b">글 1 중복</a><a class="name">카페1</a></li>'
                    '<li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/2">글 2 신규</a><a class="name">카페1</a></li>'
                )
            }],
            "url": None
        }
        mock_session.get.side_effect = [res_p1, res_p2]

        engine = CrawlerEngine(session=mock_session)
        cands = engine.fetch_candidates("티맵", datetime(2026, 10, 15), datetime(2026, 10, 15), delay=0)
        self.assertEqual(len(cands), 2)
        self.assertEqual(cands[0]["title"], "글 1")
        self.assertEqual(cands[1]["title"], "글 2 신규")

    def test_fetch_candidates_fallback_on_network_error(self):
        """후속 비동기 요청 실패 시 예외 없이 기수집된 후보군을 안전하게 반환하는지 검증."""
        mock_session = MagicMock()
        res_p1 = MagicMock()
        res_p1.status_code = 200
        res_p1.text = """
        <li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/1">글 1</a><a class="name">카페1</a></li>
        <script>var next = "https://s.search.naver.com/p/cafe/48/search.naver?query=test&start=31";</script>
        """
        res_p2 = MagicMock()
        res_p2.status_code = 500
        mock_session.get.side_effect = [res_p1, res_p2]

        engine = CrawlerEngine(session=mock_session)
        cands = engine.fetch_candidates("티맵", datetime(2026, 10, 15), datetime(2026, 10, 15), delay=0)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["title"], "글 1")

    def test_fetch_candidates_next_url_from_regex_in_response_text(self):
        """data['url']이 비어있어도 응답 텍스트 내 정규식으로 다음 페이지 URL을 추출하여 연속 수집 검증."""
        mock_session = MagicMock()
        res_p1 = MagicMock()
        res_p1.status_code = 200
        res_p1.text = """
        <li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/1">글 1</a><a class="name">카페1</a></li>
        <script>var next = "https://s.search.naver.com/p/cafe/48/search.naver?query=test&start=31";</script>
        """
        res_p2 = MagicMock()
        res_p2.status_code = 200
        res_p2.json.return_value = {
            "collection": [{
                "html": '<li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/2">글 2</a><a class="name">카페1</a></li>'
            }],
            "url": None
        }
        res_p2.text = '{"url": null, "next": "https://s.search.naver.com/p/cafe/48/search.naver?query=test&start=61"}'

        res_p3 = MagicMock()
        res_p3.status_code = 200
        res_p3.json.return_value = {
            "collection": [{
                "html": '<li class="bx"><a class="title_link" href="https://cafe.naver.com/c1/3">글 3</a><a class="name">카페1</a></li>'
            }],
            "url": None
        }
        res_p3.text = "{}"

        mock_session.get.side_effect = [res_p1, res_p2, res_p3]
        engine = CrawlerEngine(session=mock_session)
        cands = engine.fetch_candidates("티맵", datetime(2026, 10, 15), datetime(2026, 10, 15), delay=0)
        self.assertEqual(len(cands), 3)

    # ----------------------------------------------------
    # 5. 이미지 추출 및 엑셀 포맷팅 단위 테스트
    # ----------------------------------------------------
    def test_extract_images_empty_or_none(self):
        """None, 빈 문자열, 비문자열 입력 시 빈 리스트 반환 검증."""
        self.assertEqual(extract_images_from_html(None), [])
        self.assertEqual(extract_images_from_html(""), [])
        self.assertEqual(extract_images_from_html(12345), [])  # type: ignore

    def test_extract_images_various_attributes(self):
        """data-url, data-src, data-lazy-src, src 등 다양한 이미지 속성 추출 검증."""
        html_sample = """
        <div>
            <img src="https://cafeptthumb-phinf.pstatic.net/img_src.jpg">
            <img data-src="https://phinf.pstatic.net/img_data_src.png">
            <img data-url="https://postfiles.pstatic.net/img_data_url.jpg">
            <img data-lazy-src="https://phinf.pstatic.net/img_lazy.webp">
        </div>
        """
        images = extract_images_from_html(html_sample)
        self.assertEqual(len(images), 4)
        self.assertEqual(images[0], "https://cafeptthumb-phinf.pstatic.net/img_src.jpg")
        self.assertEqual(images[1], "https://phinf.pstatic.net/img_data_src.png")
        self.assertEqual(images[2], "https://postfiles.pstatic.net/img_data_url.jpg")
        self.assertEqual(images[3], "https://phinf.pstatic.net/img_lazy.webp")

    def test_extract_images_protocol_relative_and_unescape(self):
        """// 로 시작하는 프로토콜 상대 URL을 https: 로 정규화하고 HTML 엔티티를 디코딩하는지 검증."""
        html_sample = '<img src="//cafeptthumb-phinf.pstatic.net/test.jpg?a=1&amp;b=2">'
        images = extract_images_from_html(html_sample)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0], "https://cafeptthumb-phinf.pstatic.net/test.jpg?a=1&b=2")

    def test_extract_images_deduplication_preserving_order(self):
        """동일한 이미지 URL 중복 등장 시 최초 등장 순서를 유지하며 중복 제거 검증."""
        html_sample = """
        <img src="https://phinf.pstatic.net/pic1.jpg">
        <img src="https://phinf.pstatic.net/pic2.jpg">
        <img src="https://phinf.pstatic.net/pic1.jpg">
        <img src="https://phinf.pstatic.net/pic3.jpg">
        <img src="https://phinf.pstatic.net/pic2.jpg">
        """
        images = extract_images_from_html(html_sample)
        self.assertEqual(images, [
            "https://phinf.pstatic.net/pic1.jpg",
            "https://phinf.pstatic.net/pic2.jpg",
            "https://phinf.pstatic.net/pic3.jpg"
        ])

    def test_extract_images_filter_tracking_and_emojis(self):
        """1x1 트래킹 픽셀, 스티커/이모티콘, 공백 이미지를 정확히 필터링하고 실제 사진만 유지하는지 검증."""
        html_sample = """
        <div>
            <img src="https://ssl.pstatic.net/static/cafe/icon/blank.gif" width="1" height="1">
            <img src="https://storep-phinf.pstatic.net/sticker/ogq_123.png">
            <img src="https://static.naver.net/cafe/emoticon_456.gif">
            <img src="https://ssl.pstatic.net/static/cafe/ico_arrow.gif">
            <img src="blank.gif" data-src="https://cafeptthumb-phinf.pstatic.net/real_photo.jpg">
            <img src="https://phinf.pstatic.net/good_car_photo.jpg">
        </div>
        """
        images = extract_images_from_html(html_sample)
        self.assertEqual(images, [
            "https://cafeptthumb-phinf.pstatic.net/real_photo.jpg",
            "https://phinf.pstatic.net/good_car_photo.jpg"
        ])

    def test_format_df_for_excel(self):
        """format_df_for_excel 호출 시 이미지목록 리스트가 줄바꿈 문자열로 변환되는지 검증."""
        df = pd.DataFrame([
            {
                "번호": 1,
                "제목": "글1",
                "이미지목록": ["https://img1.jpg", "https://img2.jpg"]
            },
            {
                "번호": 2,
                "제목": "글2",
                "이미지목록": []
            }
        ])
        excel_df = format_df_for_excel(df)
        self.assertEqual(excel_df["이미지목록"].iloc[0], "https://img1.jpg\nhttps://img2.jpg")
        self.assertEqual(excel_df["이미지목록"].iloc[1], "")
        # 원본 DataFrame의 리스트 보존 확인
        self.assertIsInstance(df["이미지목록"].iloc[0], list)


if __name__ == '__main__':
    unittest.main()
