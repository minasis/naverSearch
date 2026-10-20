import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock
import pandas as pd

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, DOWNLOAD_FOLDER


class TestWebApp(unittest.TestCase):
    """Flask 웹 애플리케이션 라우트 및 API 단위 테스트 스위트."""

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_get_index(self):
        """메인 페이지 GET / 요청 시 200 응답 및 검색 UI 렌더링 검증."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("네이버 카페", html)
        self.assertIn("티맵", html)
        self.assertIn("tableTotalCount", html)
        self.assertIn("paginationContainer", html)
        self.assertIn("postModal", html)
        self.assertIn("modalContent", html)
        self.assertIn("modalGallery", html)

    def test_search_missing_query(self):
        """검색어 누락 시 400 Bad Request 반환 검증."""
        payload = {
            "query": "",
            "start_date": "2026-10-15",
            "end_date": "2026-10-18"
        }
        res = self.client.post('/api/search', json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("검색어", data.get("error", ""))

    def test_search_exceed_max_days(self):
        """5일 초과 기간 선택 시 400 Bad Request 및 에러 메시지 반환 검증."""
        payload = {
            "query": "티맵",
            "start_date": "2026-10-10",
            "end_date": "2026-10-18"  # 9일
        }
        res = self.client.post('/api/search', json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("최대 5일", data.get("error", ""))

    def test_search_invalid_date_order(self):
        """시작일이 종료일보다 늦은 경우 400 Bad Request 반환 검증."""
        payload = {
            "query": "티맵",
            "start_date": "2026-10-20",
            "end_date": "2026-10-15"
        }
        res = self.client.post('/api/search', json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("시작일은 종료일보다 이전", data.get("error", ""))

    @patch('app.search_and_collect')
    def test_search_success_workflow(self, mock_search):
        """정상 기간 검색 요청 시 엑셀 생성, 요약 반환 검증."""
        mock_df = pd.DataFrame([
            {
                "번호": 1,
                "작성시간": "2026-10-18 14:00:00",
                "카페명": "테스트카페",
                "게시판": "자유",
                "제목": "티맵 테스트 글",
                "작성자": "유저1",
                "댓글수": 1,
                "조회수": 20,
                "본문": "테스트 본문",
                "이미지수": 2,
                "이미지목록": ["https://img1.jpg", "https://img2.jpg"],
                "게시글링크": "https://cafe.naver.com/t/1",
                "수집방식": "REA"
            }
        ])
        mock_df.attrs = {
            "query": "티맵",
            "start_date": "2026-10-15",
            "end_date": "2026-10-18",
            "total_candidates": 5,
            "trade_excluded": 4,
            "valid_count": 1,
        }
        mock_search.return_value = mock_df

        payload = {
            "query": "티맵",
            "start_date": "2026-10-15",
            "end_date": "2026-10-18"
        }
        res = self.client.post('/api/search', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        summary = data.get("summary", {})
        self.assertEqual(summary.get("total_candidates"), 5)
        self.assertEqual(summary.get("trade_excluded"), 4)
        self.assertEqual(summary.get("valid_count"), 1)
        self.assertTrue(summary.get("filename", "").endswith(".xlsx"))
        self.assertIn("download_url", summary)

        preview = data.get("preview", [])
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0]["제목"], "티맵 테스트 글")

    @patch('app.search_and_collect')
    def test_search_all_rows_returned_without_truncation(self, mock_search):
        """20건 이상의 결과도 10건으로 축소되지 않고 전수 반환되는지 검증."""
        rows = [
            {
                "번호": i,
                "작성시간": "2026-10-18 14:00:00",
                "카페명": f"테스트카페_{i}",
                "게시판": "자유",
                "제목": f"티맵 테스트 글 {i}",
                "작성자": f"유저{i}",
                "댓글수": i,
                "조회수": i * 10,
                "본문": f"본문 {i}",
                "게시글링크": f"https://cafe.naver.com/t/{i}",
                "수집방식": "REA"
            }
            for i in range(1, 26)  # 25건
        ]
        mock_df = pd.DataFrame(rows)
        mock_df.attrs = {
            "query": "티맵",
            "start_date": "2026-10-15",
            "end_date": "2026-10-18",
            "total_candidates": 30,
            "trade_excluded": 5,
            "valid_count": 25,
        }
        mock_search.return_value = mock_df

        payload = {
            "query": "티맵",
            "start_date": "2026-10-15",
            "end_date": "2026-10-18"
        }
        res = self.client.post('/api/search', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        preview = data.get("preview", [])
        self.assertEqual(len(preview), 25)
        self.assertEqual(len(data.get("items", [])), 25)
        self.assertEqual(preview[24]["제목"], "티맵 테스트 글 25")

    def test_download_file_not_found(self):
        """존재하지 않는 엑셀 파일 다운로드 시도 시 404 반환 검증."""
        res = self.client.get('/api/download/non_existent_file.xlsx')
        self.assertEqual(res.status_code, 404)

    def test_download_directory_traversal_blocked(self):
        """디렉터리 탐색 공격 시도 차단 검증."""
        res = self.client.get('/api/download/..%2F..%2Fsecret.txt')
        self.assertIn(res.status_code, [400, 404])

    def test_download_existing_file(self):
        """실제 생성된 엑셀 파일 다운로드 성공 검증."""
        test_file = os.path.join(DOWNLOAD_FOLDER, "test_download_file.xlsx")
        pd.DataFrame([{"테스트": 1}]).to_excel(test_file, index=False)

        try:
            res = self.client.get('/api/download/test_download_file.xlsx')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("Content-Type"),
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            res.close()
        finally:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception:
                    pass


if __name__ == '__main__':
    unittest.main()
