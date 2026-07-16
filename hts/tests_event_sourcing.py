from datetime import datetime, date, timedelta
import pytz
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from hts.models import Stock, StockPrice, StockTradingCalendar, StockTradeEvent, UserBalanceSnapshot
from hts.event_sourcing import (
    is_market_open,
    process_user_events,
    check_and_create_snapshots,
    reconstruct_user_state,
    CalculationDataInsufficientError
)

User = get_user_model()

class EventSourcingTestCase(TestCase):
    def setUp(self):
        # 1. 테스트 사용자 생성
        self.user = User.objects.create_user(username='testuser', password='password123')
        # 기본 잔고 설정
        self.user.balance = 10000000.0
        self.user.save()

        # 2. 테스트 종목 생성 (한국주식 삼성전자, 미국주식 애플)
        self.samsung = Stock.objects.create(symbol='005930', name='삼성전자', market='KR')
        self.apple = Stock.objects.create(symbol='AAPL', name='애플', market='US')

        # 3. 주가 데이터 세팅
        self.kst_tz = pytz.timezone('Asia/Seoul')
        self.est_tz = pytz.timezone('America/New_York')

        # 기준일 설정 (수요일 정오 기준 - 영업일)
        self.kr_trade_time = datetime(2026, 7, 15, 12, 0, 0, tzinfo=self.kst_tz)
        self.us_trade_time = datetime(2026, 7, 15, 12, 0, 0, tzinfo=self.est_tz)

        # 주가 저장
        self.samsung_price = StockPrice.objects.create(
            stock=self.samsung,
            symbol='005930',
            market='KR',
            timestamp=self.kr_trade_time,
            close_price=70000.0
        )
        self.apple_price = StockPrice.objects.create(
            stock=self.apple,
            symbol='AAPL',
            market='US',
            timestamp=self.us_trade_time,
            close_price=150.0
        )

        # 4. 거래일 달력 설정
        StockTradingCalendar.mark_day_type(
            symbol='005930', market='KR', date=date(2026, 7, 15), day_type='TRADING', has_price_data=True
        )
        StockTradingCalendar.mark_day_type(
            symbol='AAPL', market='US', date=date(2026, 7, 15), day_type='TRADING', has_price_data=True
        )

    def tearDown(self):
        # 테스트 격리를 보장하기 위한 강제 정리
        StockTradeEvent.objects.all().delete()
        UserBalanceSnapshot.objects.all().delete()
        StockPrice.objects.all().delete()
        StockTradingCalendar.objects.all().delete()
        Stock.objects.all().delete()
        User.objects.all().delete()

    def test_market_hours_validation(self):
        """거래 가능 시간 및 요일 검증 테스트"""
        # 한국 장중 (수요일 12시)
        is_open, _ = is_market_open('KR', self.kr_trade_time)
        self.assertTrue(is_open)

        # 한국 장외 (수요일 18시 5분)
        kr_closed_time = datetime(2026, 7, 15, 18, 5, 0, tzinfo=self.kst_tz)
        is_open, _ = is_market_open('KR', kr_closed_time)
        self.assertFalse(is_open)

        # 한국 주말 (토요일 12시)
        kr_weekend_time = datetime(2026, 7, 18, 12, 0, 0, tzinfo=self.kst_tz)
        is_open, _ = is_market_open('KR', kr_weekend_time)
        self.assertFalse(is_open)

        # 미국 장중 (수요일 12시 EST)
        is_open, _ = is_market_open('US', self.us_trade_time)
        self.assertTrue(is_open)

    def test_trade_event_processing_and_replay(self):
        """매수/매도 이벤트 소싱 처리 및 리플레이(상태 재현) 테스트"""
        # 매수 이벤트 등록 (삼성전자 10주, 주가 70,000원 = 총 700,000원)
        event1 = StockTradeEvent.objects.create(
            user=self.user,
            stock_symbol='005930',
            event_type='BUY',
            quantity=10,
            status='PENDING',
            created_at=self.kr_trade_time
        )
        
        process_user_events(self.user)
        self.user.refresh_from_db()
        event1.refresh_from_db()

        # 거래 체결 검증
        self.assertEqual(event1.status, 'PROCESSED')
        self.assertEqual(self.user.balance, 9300000.0)

        # 매도 이벤트 등록 (삼성전자 5주, 주가 70,000원 = 총 350,000원 회수)
        event2 = StockTradeEvent.objects.create(
            user=self.user,
            stock_symbol='005930',
            event_type='SELL',
            quantity=5,
            status='PENDING',
            created_at=self.kr_trade_time + timedelta(minutes=5)
        )
        
        # 이전 이벤트와 충돌나지 않도록 가격 정보 추가
        StockPrice.objects.create(
            stock=self.samsung,
            symbol='005930',
            market='KR',
            timestamp=self.kr_trade_time + timedelta(minutes=5),
            close_price=70000.0
        )

        process_user_events(self.user)
        self.user.refresh_from_db()
        event2.refresh_from_db()

        self.assertEqual(event2.status, 'PROCESSED')
        self.assertEqual(self.user.balance, 9650000.0)

        # 3. 리플레이 기능 검증
        reconstructed_balance, reconstructed_portfolio = reconstruct_user_state(self.user)
        self.assertEqual(reconstructed_balance, 9650000.0)
        self.assertEqual(reconstructed_portfolio, {'005930': 5})

    def test_fifo_sequential_processing_and_error_propagation(self):
        """선입선출(FIFO) 검증 및 이전 이벤트 실패 시 후속 이벤트 중단 테스트"""
        # 첫 번째 주문: 잔액을 초과하는 대규모 주문 (실패할 예정)
        event_fail = StockTradeEvent.objects.create(
            user=self.user,
            stock_symbol='005930',
            event_type='BUY',
            quantity=200, # 70,000원 * 200 = 14,000,000원 (잔액 10,000,000원 초과)
            status='PENDING',
            created_at=self.kr_trade_time
        )
        
        # 두 번째 주문: 정상적인 주문 (대기 상태여야 함)
        event_ok = StockTradeEvent.objects.create(
            user=self.user,
            stock_symbol='005930',
            event_type='BUY',
            quantity=1,
            status='PENDING',
            created_at=self.kr_trade_time + timedelta(minutes=1)
        )

        process_user_events(self.user)
        event_fail.refresh_from_db()
        event_ok.refresh_from_db()

        # 첫 번째 주문이 실패했으므로 두 번째 주문은 PENDING 상태로 멈춰있어야 함
        self.assertEqual(event_fail.status, 'FAILED')
        self.assertEqual(event_ok.status, 'PENDING')

    def test_snapshot_creation_and_blocking_on_missing_price(self):
        """스냅샷 생성 시 주가 누락 시 FAILED 마킹 및 신규 주문 차단 검증"""
        # 1. 주가 정보가 없는 날짜에 주문 이벤트를 인위적으로 발생시킴
        missing_price_time = datetime(2026, 7, 14, 12, 0, 0, tzinfo=self.kst_tz) # 전날
        StockTradingCalendar.mark_day_type(
            symbol='005930', market='KR', date=date(2026, 7, 14), day_type='TRADING', has_price_data=False
        )

        StockTradeEvent.objects.create(
            user=self.user,
            stock_symbol='005930',
            event_type='BUY',
            quantity=1,
            status='PENDING',
            created_at=missing_price_time
        )

        # 2. 스냅샷 생성 시도 -> 주가 데이터 부재로 스냅샷 FAILED 기록되어야 함
        check_and_create_snapshots(self.user)
        
        failed_snapshot = UserBalanceSnapshot.objects.filter(user=self.user, status='FAILED').first()
        self.assertIsNotNone(failed_snapshot)
        
        # 동적 어제 날짜 구하기
        yesterday = timezone.now().astimezone(self.kst_tz).date() - timedelta(days=1)
        self.assertEqual(failed_snapshot.snapshot_date, yesterday)

        # 3. 스냅샷 FAILED 존재 시 신규 주문 비동기 API 요청 차단 여부 검증
        self.client.force_login(self.user)
        response = self.client.post('/hts/trade/', data={
            'symbol': '005930',
            'order_type': 'BUY',
            'quantity': 1
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('데이터 정산이 필요합니다', response.json()['message'])

    def test_price_correction_replay(self):
        """주가 보정 시 리플레이로 잔고 보정 재현 테스트"""
        event = StockTradeEvent.objects.create(
            user=self.user,
            stock_symbol='005930',
            event_type='BUY',
            quantity=10,
            status='PENDING',
            created_at=self.kr_trade_time
        )
        
        process_user_events(self.user)
        event.refresh_from_db()
        self.assertEqual(event.status, 'PROCESSED')

        # 가격을 보정함 (70,000원에서 60,000원으로 변경)
        self.samsung_price.close_price = 60000.0
        self.samsung_price.save()

        # 리플레이 결과 재검색
        reconstructed_balance, _ = reconstruct_user_state(self.user)
        # 10,000,000 - (60,000 * 10) = 9,400,000원 (보정되어 반영됨)
        self.assertEqual(reconstructed_balance, 9400000.0)
