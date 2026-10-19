import unittest
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from filters import is_trade_post, is_within_hours, is_within_2_hours


class TestFilters(unittest.TestCase):
    """거래글 필터링 및 작성시간 파싱 로직 단위 테스트 스위트."""

    # ----------------------------------------------------
    # 1. is_trade_post 테스트
    # ----------------------------------------------------
    def test_trade_post_by_cafename(self):
        """거래 관련 카페명 필터링 검증."""
        self.assertTrue(is_trade_post("중고나라", "티맵 HUD 거치대 질문", "어떤가요?"))
        self.assertTrue(is_trade_post("당근마켓 공식 카페", "티맵 사용 후기", "좋네요"))
        self.assertTrue(is_trade_post("벼룩시장 동호회", "길안내 문의", "내용"))
        self.assertTrue(is_trade_post("전국직거래장터", "잡담", "내용"))

    def test_trade_post_by_keywords(self):
        """본문/제목 거래 키워드 필터링 검증."""
        self.assertTrue(is_trade_post("일반카페", "티맵 네비 HUD 팝니다", "상태 S급"))
        self.assertTrue(is_trade_post("일반카페", "거치대 삽니다", "직거래 희망"))
        self.assertTrue(is_trade_post("일반카페", "스마트폰 거치대", "미개봉 택포 2만원에 판매"))
        self.assertTrue(is_trade_post("일반카페", "급매 티맵 연동 기기", "네고 가능 착불"))
        self.assertTrue(is_trade_post("일반카페", "물품 정리", "예약중입니다"))
        self.assertTrue(is_trade_post("일반카페", "물품 정리", "판매완료"))

    def test_trade_post_by_price_pattern(self):
        """정규식 가격 패턴 포함 게시글 필터링 검증."""
        self.assertTrue(is_trade_post("일반카페", "HUD 공구 15,000원", "신청하세요"))
        self.assertTrue(is_trade_post("일반카페", "거치대 양도", "가격은 3만원입니다"))
        self.assertTrue(is_trade_post("일반카페", "기기 처분", "본문 120,000원에 넘겨요"))

    def test_non_trade_post(self):
        """순수 커뮤니티/정보성 정상 게시글은 False 반환 검증."""
        self.assertFalse(is_trade_post("클리앙", "티맵 vs 카카오내비 비교", "고속도로 안내 품질"))
        self.assertFalse(is_trade_post("아반떼 동호회", "티맵 이번 업데이트 어떤가요?", "UI가 많이 바뀌었네요"))
        self.assertFalse(is_trade_post("IT정보마당", "안드로이드 오토 티맵 연결 끊김 해결법", "케이블 교체해보세요"))

    def test_trade_post_edge_cases(self):
        """빈 값, None, 경계 케이스 검증."""
        self.assertFalse(is_trade_post("", "", ""))
        self.assertFalse(is_trade_post(None, None, None))
        self.assertFalse(is_trade_post("일반카페", "10km 운전 후기", "연비 15km/l 나왔습니다"))

    # ----------------------------------------------------
    # 2. is_within_hours & is_within_2_hours 테스트
    # ----------------------------------------------------
    def test_within_hours_true_cases(self):
        """기준 시간(기본 2시간) 이내 작성된 경우 True 검증."""
        self.assertTrue(is_within_hours("방금"))
        self.assertTrue(is_within_hours("방금 전"))
        self.assertTrue(is_within_hours("10초 전"))
        self.assertTrue(is_within_hours("1분 전"))
        self.assertTrue(is_within_hours("15분 전"))
        self.assertTrue(is_within_hours("59분 전"))
        self.assertTrue(is_within_hours("1시간 전"))
        self.assertTrue(is_within_hours("2시간 전"))
        # 공백 포함 케이스
        self.assertTrue(is_within_hours("  2 시간 전  "))
        self.assertTrue(is_within_hours(" 30 분 전 "))

    def test_within_hours_false_cases(self):
        """기준 시간(기본 2시간) 초과 및 과거 날짜는 False 검증."""
        self.assertFalse(is_within_hours("3시간 전"))
        self.assertFalse(is_within_hours("5시간 전"))
        self.assertFalse(is_within_hours("23시간 전"))
        self.assertFalse(is_within_hours("1일 전"))
        self.assertFalse(is_within_hours("2일 전"))
        self.assertFalse(is_within_hours("어제"))
        self.assertFalse(is_within_hours("2026.10.15."))
        self.assertFalse(is_within_hours("2026.10.18. 14:30"))

    def test_within_hours_edge_cases(self):
        """빈 문자열 및 None 처리 검증."""
        self.assertFalse(is_within_hours(""))
        self.assertFalse(is_within_hours("   "))
        self.assertFalse(is_within_hours(None))

    def test_custom_max_hours(self):
        """max_hours 인자 커스터마이징 검증."""
        self.assertTrue(is_within_hours("3시간 전", max_hours=3))
        self.assertTrue(is_within_hours("5시간 전", max_hours=6))
        self.assertFalse(is_within_hours("4시간 전", max_hours=3))

    def test_is_within_2_hours_wrapper(self):
        """2시간 전용 하위 호환 래퍼 검증."""
        self.assertTrue(is_within_2_hours("1시간 전"))
        self.assertTrue(is_within_2_hours("2시간 전"))
        self.assertFalse(is_within_2_hours("3시간 전"))


if __name__ == '__main__':
    unittest.main()
