import unittest
import sys
import os
from bs4 import BeautifulSoup

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from parser import parse_cafe_item, parse_cafe_search_results


SAMPLE_HTML = """
<div class="main_pack">
  <ul class="lst_total">
    <li class="bx">
      <div class="view_wrap">
        <div class="user_box">
          <a class="name" href="https://cafe.naver.com/naviclub">네비게이션 사용자 모임</a>
          <span class="sub">10분 전</span>
        </div>
        <div class="title_area">
          <a class="title_link" href="https://cafe.naver.com/naviclub/12345">티맵 길안내 오류 관련 질문입니다.</a>
        </div>
        <div class="dsc_area">
          오늘 아침 출근길에 티맵 경로 재탐색이 자주 발생했는데 다른 분들도 그러신가요?
        </div>
      </div>
    </li>
    <li class="bx">
      <div class="view_wrap">
        <div class="user_box">
          <a class="name" href="https://cafe.naver.com/carclub">그랜저 공식 카페</a>
          <span class="sub">1시간 전</span>
        </div>
        <div class="title_area">
          <a class="title_link" href="https://cafe.naver.com/carclub/67890">안드로이드 오토 티맵 HUD 연동 성공</a>
        </div>
        <div class="dsc_area">
          순정 HUD에 티맵 턴바이턴 안내 아주 잘 뜹니다. 대만족이네요.
        </div>
      </div>
    </li>
    <li class="bx">
      <!-- 타이틀 링크가 없는 예외적/비정상 bx 요소 -->
      <div class="banner_box">
        <p>프로모션 광고 배너</p>
      </div>
    </li>
  </ul>
</div>
"""


class TestParser(unittest.TestCase):
    """네이버 카페 검색 결과 HTML 파싱 단위 테스트 스위트."""

    def test_parse_cafe_search_results_valid(self):
        """샘플 HTML로부터 유효 게시글 정상 추출 검증."""
        items = parse_cafe_search_results(SAMPLE_HTML)
        self.assertEqual(len(items), 2)

        first = items[0]
        self.assertEqual(first["title"], "티맵 길안내 오류 관련 질문입니다.")
        self.assertEqual(first["link"], "https://cafe.naver.com/naviclub/12345")
        self.assertEqual(first["cafename"], "네비게이션 사용자 모임")
        self.assertEqual(first["post_time"], "10분 전")
        self.assertIn("티맵 경로 재탐색", first["desc"])

        second = items[1]
        self.assertEqual(second["title"], "안드로이드 오토 티맵 HUD 연동 성공")
        self.assertEqual(second["link"], "https://cafe.naver.com/carclub/67890")
        self.assertEqual(second["cafename"], "그랜저 공식 카페")
        self.assertEqual(second["post_time"], "1시간 전")
        self.assertIn("순정 HUD", second["desc"])

    def test_parse_cafe_item_single(self):
        """단일 bs4 li.bx 요소 직접 파싱 검증."""
        soup = BeautifulSoup(SAMPLE_HTML, 'html.parser')
        bx_list = soup.select('li.bx')

        # 첫 번째 bx (유효한 글)
        item1 = parse_cafe_item(bx_list[0])
        self.assertIsNotNone(item1)
        self.assertEqual(item1["title"], "티맵 길안내 오류 관련 질문입니다.")

        # 세 번째 bx (title_link 없는 배너)
        item3 = parse_cafe_item(bx_list[2])
        self.assertIsNone(item3)

    def test_parse_empty_or_invalid_html(self):
        """빈 HTML, None, 검색결과 없음 처리 검증."""
        self.assertEqual(parse_cafe_search_results(""), [])
        self.assertEqual(parse_cafe_search_results(None), [])
        self.assertEqual(parse_cafe_search_results("<div>검색 결과가 없습니다.</div>"), [])


if __name__ == '__main__':
    unittest.main()
