import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from article_api import (
    extract_ids_from_url,
    extract_art_token,
    resolve_cafe_id,
    fetch_article_detail,
    fetch_article_from_url,
    is_sale_article,
)


class TestArticleApi(unittest.TestCase):
    """네이버 카페 Article API 및 URL 파싱 단위 테스트 스위트."""

    # ----------------------------------------------------
    # 1. extract_ids_from_url 테스트
    # ----------------------------------------------------
    def test_extract_ids_standard_cafe_url(self):
        """표준 웹/모바일 cafeId 형식 URL에서 ID 추출 검증."""
        url = "https://cafe.naver.com/ca-fe/cafes/12345678/articles/98765"
        cafe_id, article_id = extract_ids_from_url(url)
        self.assertEqual(cafe_id, 12345678)
        self.assertEqual(article_id, 98765)

        url_m = "https://m.cafe.naver.com/ca-fe/web/cafes/12345678/articles/98765"
        cafe_id_m, article_id_m = extract_ids_from_url(url_m)
        self.assertEqual(cafe_id_m, 12345678)
        self.assertEqual(article_id_m, 98765)

    def test_extract_ids_query_param_url(self):
        """ArticleRead.nhn 형태의 쿼리 스트링 URL에서 ID 추출 검증."""
        url = "https://cafe.naver.com/ArticleRead.nhn?clubid=12345678&articleid=98765"
        cafe_id, article_id = extract_ids_from_url(url)
        self.assertEqual(cafe_id, 12345678)
        self.assertEqual(article_id, 98765)

        url_upper = "https://cafe.naver.com/ArticleShow.nhn?clubId=87654321&articleId=11111"
        cafe_id2, article_id2 = extract_ids_from_url(url_upper)
        self.assertEqual(cafe_id2, 87654321)
        self.assertEqual(article_id2, 11111)

    def test_extract_ids_clubname_url(self):
        """cafe.naver.com/{clubname}/{articleId} 형태 URL에서 ID 추출 검증."""
        url = "https://cafe.naver.com/suddenattackskincafe/5143198?art=xyz123"
        cafe_id, article_id = extract_ids_from_url(url)
        self.assertEqual(cafe_id, "suddenattackskincafe")
        self.assertEqual(article_id, 5143198)

        url_simple = "https://cafe.naver.com/jmeat/1017417"
        cafe_id2, article_id2 = extract_ids_from_url(url_simple)
        self.assertEqual(cafe_id2, "jmeat")
        self.assertEqual(article_id2, 1017417)

    def test_extract_ids_invalid_or_empty(self):
        """빈 값, None, 무효한 URL 처리 검증."""
        self.assertEqual(extract_ids_from_url(""), (None, None))
        self.assertEqual(extract_ids_from_url(None), (None, None))
        self.assertEqual(extract_ids_from_url("https://www.google.com"), (None, None))
        self.assertEqual(extract_ids_from_url("https://cafe.naver.com/"), (None, None))

    # ----------------------------------------------------
    # 2. extract_art_token 테스트
    # ----------------------------------------------------
    def test_extract_art_token(self):
        """URL 쿼리 파라미터에서 art 토큰 추출 검증."""
        url = "https://cafe.naver.com/test/123?art=TOKEN_VALUE_ABC&tc=naver"
        self.assertEqual(extract_art_token(url), "TOKEN_VALUE_ABC")

        url_no_art = "https://cafe.naver.com/test/123"
        self.assertIsNone(extract_art_token(url_no_art))

    # ----------------------------------------------------
    # 3. is_sale_article 테스트
    # ----------------------------------------------------
    def test_is_sale_article_true(self):
        """saleInfo가 존재하는 거래글 판별 검증."""
        data_with_sale = {
            "result": {
                "article": {"subject": "상품 판매합니다"},
                "saleInfo": {
                    "price": 50000,
                    "productCondition": "NEW",
                    "saleStatus": "ON_SALE"
                }
            }
        }
        self.assertTrue(is_sale_article(data_with_sale))

    def test_is_sale_article_false(self):
        """saleInfo가 None이거나 없는 일반글 판별 검증."""
        data_no_sale = {
            "result": {
                "article": {"subject": "티맵 길안내 질문입니다"},
                "saleInfo": None
            }
        }
        self.assertFalse(is_sale_article(data_no_sale))

        data_without_key = {
            "result": {
                "article": {"subject": "일반 커뮤니티 글"}
            }
        }
        self.assertFalse(is_sale_article(data_without_key))

    def test_is_sale_article_edge_cases(self):
        """빈 딕셔너리, None, 잘못된 형식 판별 검증."""
        self.assertFalse(is_sale_article({}))
        self.assertFalse(is_sale_article(None))
        self.assertFalse(is_sale_article({"result": None}))

    # ----------------------------------------------------
    # 4. fetch_article_detail 테스트 (Mock)
    # ----------------------------------------------------
    @patch('requests.get')
    def test_fetch_article_detail_success(self, mock_get):
        """HTTP 200 응답 시 정상 딕셔너리 반환 검증."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "article": {"subject": "테스트 제목"},
                "saleInfo": None
            }
        }
        mock_get.return_value = mock_response

        res = fetch_article_detail(12345, 67890, art="TEST_TOKEN")
        self.assertIsNotNone(res)
        self.assertEqual(res["result"]["article"]["subject"], "테스트 제목")
        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        self.assertIn("apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/12345/articles/67890", called_url)

    @patch('requests.get')
    def test_fetch_article_detail_error_response(self, mock_get):
        """HTTP 401/404/500 에러 시 None 반환 검증."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        res = fetch_article_detail(12345, 67890)
        self.assertIsNone(res)

    @patch('requests.get')
    def test_fetch_article_detail_exception(self, mock_get):
        """네트워크 예외 발생 시 안전하게 None 반환 검증."""
        import requests
        mock_get.side_effect = requests.RequestException("Network Error")

        res = fetch_article_detail(12345, 67890)
        self.assertIsNone(res)

    @patch('article_api.fetch_article_detail')
    def test_fetch_article_from_url(self, mock_fetch):
        """URL 문자열로부터 id와 art 토큰을 추출하여 fetch_article_detail 위임 검증."""
        mock_fetch.return_value = {"result": {"article": {"subject": "통합 조회"}}}
        url = "https://cafe.naver.com/ca-fe/cafes/12345/articles/67890?art=TOKEN123"

        res = fetch_article_from_url(url)
        self.assertIsNotNone(res)
        mock_fetch.assert_called_once_with(12345, 67890, art="TOKEN123", session=None)

        # 무효 URL 시 None 반환
        self.assertIsNone(fetch_article_from_url("invalid_url"))

    # ----------------------------------------------------
    # 5. resolve_cafe_id 테스트
    # ----------------------------------------------------
    def test_resolve_cafe_id_numeric(self):
        """이미 숫자 형태인 cafe_id는 API 호출 없이 즉시 정수 반환 검증."""
        self.assertEqual(resolve_cafe_id(12345), 12345)
        self.assertEqual(resolve_cafe_id("12345"), 12345)

    @patch('requests.get')
    def test_resolve_cafe_id_clubname_api(self, mock_get):
        """문자열 cluburl을 CafeGateInfo API로 조회하여 cafeId 반환 검증."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "status": "200",
                "result": {
                    "cafeInfoView": {
                        "cafeId": 99887766
                    }
                }
            }
        }
        mock_get.return_value = mock_response

        # 캐시 영향을 피하기 위해 임의의 고유 이름 사용
        cafe_id = resolve_cafe_id("mock_club_unique_123")
        self.assertEqual(cafe_id, 99887766)


if __name__ == '__main__':
    unittest.main()
