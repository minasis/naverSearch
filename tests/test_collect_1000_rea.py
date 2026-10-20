import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from collect_1000_rea import (
    clean_text,
    clean_html_text,
    format_timestamp,
    parse_relative_time_to_dt,
    calculate_time_range,
    process_candidate_with_rea,
    fetch_candidates_from_openapi,
    fetch_search_candidates,
    remove_illegal_excel_chars,
)


class TestCollect1000Rea(unittest.TestCase):
    """collect_1000_rea 모듈에 대한 포괄적 단위 테스트 스위트."""

    def test_clean_html_text_basic(self):
        html_input = "<p>안녕하세요. <b>티맵</b> 업데이트 문의입니다.</p><br><div>내용입니다.</div>"
        result = clean_html_text(html_input)
        self.assertEqual(result, "안녕하세요. 티맵 업데이트 문의입니다. 내용입니다.")

    def test_clean_html_text_empty(self):
        self.assertEqual(clean_html_text(""), "")
        self.assertEqual(clean_html_text(None), "")

    def test_clean_html_text_length_limit(self):
        long_html = "<p>" + "A" * 35000 + "</p>"
        result = clean_html_text(long_html)
        self.assertTrue(len(result) <= 30100)
        self.assertTrue(result.endswith("[본문 축약]"))

    def test_format_timestamp(self):
        # 1792416356553 ms -> 2026-10-19 22:25:56 (KST, UTC+9)
        res = format_timestamp(1792416356553)
        self.assertEqual(res, "2026-10-19 22:25:56")

        # 초 단위 타임스탬프
        res_sec = format_timestamp(1792416356)
        self.assertEqual(res_sec, "2026-10-19 22:25:56")

        # None 및 무효값
        self.assertIsNone(format_timestamp(None))
        self.assertIsNone(format_timestamp("invalid"))

    def test_parse_relative_time_to_dt(self):
        self.assertIsNone(parse_relative_time_to_dt(""))
        self.assertIsNone(parse_relative_time_to_dt(None))

        # 표준 포맷
        dt = parse_relative_time_to_dt("2026-10-19 12:30:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 10)
        self.assertEqual(dt.day, 19)

        # 상대시간 포맷
        dt_min = parse_relative_time_to_dt("10분 전")
        self.assertIsNotNone(dt_min)

        dt_hour = parse_relative_time_to_dt("3시간 전")
        self.assertIsNotNone(dt_hour)

        dt_day = parse_relative_time_to_dt("2일 전")
        self.assertIsNotNone(dt_day)

    def test_calculate_time_range(self):
        # 빈 목록
        self.assertEqual(calculate_time_range([]), ("-", "-", "수집된 데이터 없음"))

        # 2개 이상 아이템
        items = [
            {"작성시간": "2026-10-19 22:30:00"},
            {"작성시간": "2026-10-18 10:00:00"}
        ]
        newest, oldest, summary = calculate_time_range(items)
        self.assertEqual(newest, "2026-10-19 22:30:00")
        self.assertEqual(oldest, "2026-10-18 10:00:00")
        self.assertIn("2026-10-19 22:30:00", summary)
        self.assertIn("2026-10-18 10:00:00", summary)

    @patch("collect_1000_rea.fetch_article_from_url")
    def test_process_candidate_rea_sale_article(self, mock_fetch):
        """REA Article API에서 saleInfo가 검출되면 거래글로 판별되어 제외."""
        mock_fetch.return_value = {
            "result": {
                "saleInfo": {"price": 10000},
                "article": {"subject": "네비게이션 팝니다"}
            }
        }
        cand = {
            "link": "https://cafe.naver.com/test/123",
            "cafename": "테스트카페",
            "title": "네비게이션 팝니다",
            "desc": "설명",
            "post_time": "1시간 전"
        }
        item, is_trade = process_candidate_with_rea(cand)
        self.assertTrue(is_trade)
        self.assertIsNone(item)

    @patch("collect_1000_rea.fetch_article_from_url")
    def test_process_candidate_rea_trade_keyword(self, mock_fetch):
        """saleInfo가 없더라도 본문에 가격 패턴이나 거래 키워드가 있으면 거래글 판별."""
        mock_fetch.return_value = {
            "result": {
                "saleInfo": None,
                "article": {
                    "subject": "티맵 단말기 양도",
                    "contentHtml": "<p>50,000원에 급매 판매합니다. 택포 가격입니다.</p>",
                    "writeDate": 1792416356553,
                    "writer": {"nick": "판매자"},
                    "commentCount": 1,
                    "readCount": 50,
                    "menu": {"name": "자유게시판"}
                }
            }
        }
        cand = {
            "link": "https://cafe.naver.com/test/124",
            "cafename": "테스트카페",
            "title": "티맵 단말기",
            "desc": "요약",
            "post_time": "방금 전"
        }
        item, is_trade = process_candidate_with_rea(cand)
        self.assertTrue(is_trade)
        self.assertIsNone(item)

    @patch("collect_1000_rea.fetch_article_from_url")
    def test_process_candidate_rea_valid_article(self, mock_fetch):
        """정상 일반 커뮤니티 글은 REA 상세 정보로 수집."""
        mock_fetch.return_value = {
            "result": {
                "saleInfo": None,
                "article": {
                    "subject": "티맵 이번 업데이트 어떤가요?",
                    "contentHtml": "<div>경로 탐색이 조금 빨라진 것 같은데 다들 어떠신가요?</div>",
                    "writeDate": 1792416356553,
                    "writer": {"nick": "드라이버1"},
                    "commentCount": 5,
                    "readCount": 120,
                    "menu": {"name": "자유토론"}
                },
                "comments": {"totalCount": 5}
            }
        }
        cand = {
            "link": "https://cafe.naver.com/test/125",
            "cafename": "차량동호회",
            "title": "티맵 이번 업데이트",
            "desc": "요약",
            "post_time": "10분 전"
        }
        item, is_trade = process_candidate_with_rea(cand)
        self.assertFalse(is_trade)
        self.assertIsNotNone(item)
        self.assertEqual(item["제목"], "티맵 이번 업데이트 어떤가요?")
        self.assertEqual(item["작성자"], "드라이버1")
        self.assertEqual(item["댓글수"], 5)
        self.assertEqual(item["조회수"], 120)
        self.assertEqual(item["게시판"], "자유토론")
        self.assertEqual(item["수집방식"], "REA Article API (상세)")
        self.assertEqual(item["작성시간"], "2026-10-19 22:25:56")

    @patch("collect_1000_rea.fetch_article_from_url")
    def test_process_candidate_fallback(self, mock_fetch):
        """Article API 응답이 없을 때(회원전용) 검색 결과 요약으로 자연스럽게 폴백."""
        mock_fetch.return_value = None
        cand = {
            "link": "https://cafe.naver.com/privatecafe/999",
            "cafename": "비공개카페",
            "title": "티맵 즐겨찾기 백업 방법",
            "desc": "비공개 카페 회원 전용 글 내용 요약입니다.",
            "post_time": "15분 전"
        }
        item, is_trade = process_candidate_with_rea(cand)
        self.assertFalse(is_trade)
        self.assertIsNotNone(item)
        self.assertEqual(item["제목"], "티맵 즐겨찾기 백업 방법")
        self.assertEqual(item["본문"], "비공개 카페 회원 전용 글 내용 요약입니다.")
        self.assertEqual(item["작성자"], "회원전용/미공개")
        self.assertEqual(item["수집방식"], "검색 요약 폴백 (회원전용)")
    @patch("collect_1000_rea.fetch_article_from_url")
    def test_process_candidate_fallback_trade(self, mock_fetch):
        """Article API 응답이 없더라도 검색 요약에 거래 키워드가 있으면 거래글 제외."""
        mock_fetch.return_value = None
        cand = {
            "link": "https://cafe.naver.com/joonggonara/888",
            "cafename": "중고나라",
            "title": "티맵 거치대 팝니다",
            "desc": "1만원에 팝니다",
            "post_time": "20분 전"
        }
        item, is_trade = process_candidate_with_rea(cand)
        self.assertTrue(is_trade)
        self.assertIsNone(item)

    def test_clean_text(self):
        raw = "<b>티맵</b> &amp; 카카오내비 &lt;비교&gt;"
        self.assertEqual(clean_text(raw), "티맵 & 카카오내비 <비교>")
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text(None), "")

    @patch("collect_1000_rea.os.getenv")
    @patch("collect_1000_rea.requests.get")
    def test_fetch_candidates_from_openapi(self, mock_get, mock_getenv):
        mock_getenv.side_effect = lambda k: "dummy_val" if "NAVER" in k else None
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "title": "<b>티맵</b> 추천",
                    "link": "https://cafe.naver.com/cafe1/101",
                    "description": "설명",
                    "cafename": "카페1"
                }
            ]
        }
        mock_get.return_value = mock_resp

        candidates = fetch_candidates_from_openapi("티맵", target_count=1)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["title"], "티맵 추천")
        self.assertEqual(candidates[0]["cafename"], "카페1")

    def test_remove_illegal_excel_chars(self):
        # 제어문자 \x00, \x0c, \x1f 등 포함된 문자열 테스트
        bad_str = "안녕\x00하세요\x0c반갑\x1f습니다"
        clean = remove_illegal_excel_chars(bad_str)
        self.assertEqual(clean, "안녕하세요반갑습니다")
        # 숫자는 그대로 유지
        self.assertEqual(remove_illegal_excel_chars(123), 123)
        self.assertIsNone(remove_illegal_excel_chars(None))


if __name__ == "__main__":
    unittest.main()
