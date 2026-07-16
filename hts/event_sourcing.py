import pytz
from datetime import time, date, timedelta, datetime
from django.db import transaction
from django.utils import timezone
from .models import User, Stock, StockPrice, StockTradingCalendar, StockTradeEvent, UserBalanceSnapshot

class CalculationDataInsufficientError(Exception):
    """주가 정보가 없거나 정산을 진행하기에 데이터가 불충분할 때 발생하는 예외"""
    pass


def is_market_open(market, dt):
    """
    특정 시장의 거래 시간 및 영업일 여부를 확인합니다.
    """
    market_upper = market.upper()
    
    # 1. 시장별 타임존 및 정규 거래 시간 설정
    if market_upper in ['KR', 'KOSPI', 'KOSDAQ']:
        tz = pytz.timezone('Asia/Seoul')
        market_hours = [(time(9, 0), time(15, 30))]
    elif market_upper == 'US':
        tz = pytz.timezone('America/New_York')
        market_hours = [(time(9, 30), time(16, 0))]
    elif market_upper == 'JP':
        tz = pytz.timezone('Asia/Tokyo')
        market_hours = [
            (time(9, 0), time(11, 30)),
            (time(12, 30), time(15, 0))
        ]
    else:
        # 기본값: 한국 정규 시간
        tz = pytz.timezone('Asia/Seoul')
        market_hours = [(time(9, 0), time(15, 30))]

    # 2. 거래 시각을 현지 시간대로 변환
    dt_local = dt.astimezone(tz)
    
    # 3. 주말 여부 검증 (토요일=5, 일요일=6)
    if dt_local.weekday() >= 5:
        return False, "주말에는 주식 거래를 진행할 수 없습니다."

    # 4. 개장 시간 검증
    local_time = dt_local.time()
    in_range = False
    for start, end in market_hours:
        if start <= local_time <= end:
            in_range = True
            break

    if not in_range:
        return False, f"장 거래 시간 외에는 주문할 수 없습니다. (현지 시간: {local_time.strftime('%H:%M:%S')})"

    # 5. 거래일 캘린더 검증
    date_local = dt_local.date()
    cal = StockTradingCalendar.objects.filter(date=date_local).first()
    if cal and cal.day_type != 'TRADING':
        return False, f"해당 일자는 거래일이 아닙니다. (구분: {cal.get_day_type_display()})"

    return True, ""


def get_price_at_timestamp(stock, dt):
    """
    이벤트 생성 시점(dt) 기준 해당 종목의 가장 최근 주가 정보를 조회합니다.
    """
    return StockPrice.objects.filter(
        symbol=stock.symbol,
        market=stock.market,
        timestamp__lte=dt
    ).order_by('-timestamp').first()


def calculate_user_portfolio_up_to(user, event_id):
    """
    특정 이벤트 ID 이전까지 적용된 포트폴리오 상태를 계산합니다.
    """
    portfolio = {}
    events = StockTradeEvent.objects.filter(
        user=user,
        status='PROCESSED',
        id__lt=event_id
    ).order_by('id')
    
    for event in events:
        if event.event_type == 'BUY':
            portfolio[event.stock_symbol] = portfolio.get(event.stock_symbol, 0) + event.quantity
        elif event.event_type == 'SELL':
            portfolio[event.stock_symbol] = portfolio.get(event.stock_symbol, 0) - event.quantity
            if portfolio[event.stock_symbol] <= 0:
                portfolio.pop(event.stock_symbol, None)
                
    return portfolio


def process_user_events(user):
    """
    사용자의 PENDING 상태 이벤트를 선입선출(FIFO)로 안전하게 처리합니다.
    """
    # 정산 오류 마킹(FAILED 스냅샷)이 있다면 처리하지 않음
    if UserBalanceSnapshot.objects.filter(user=user, status='FAILED').exists():
        return

    with transaction.atomic():
        user_locked = User.objects.select_for_update().get(id=user.id)
        
        if UserBalanceSnapshot.objects.filter(user=user_locked, status='FAILED').exists():
            return

        pending_events = StockTradeEvent.objects.filter(
            user=user_locked,
            status='PENDING'
        ).order_by('id').select_for_update()

        for event in pending_events:
            # 이전 이벤트 중 실패(FAILED)한 건이 있다면 처리 중단
            failed_exists = StockTradeEvent.objects.filter(
                user=user_locked,
                status='FAILED',
                id__lt=event.id
            ).exists()
            if failed_exists:
                break

            try:
                stock = Stock.objects.get(symbol=event.stock_symbol)
                
                # 1. 거래 시간 및 요일 검증
                is_open, error_reason = is_market_open(stock.market, event.created_at)
                if not is_open:
                    raise ValueError(error_reason)

                # 2. 해당 시간 주가 조회
                price_record = get_price_at_timestamp(stock, event.created_at)
                if not price_record:
                    raise CalculationDataInsufficientError(
                        f"종목 {event.stock_symbol}의 {event.created_at} 기준 주가 정보가 존재하지 않습니다."
                    )

                price = price_record.close_price
                total_cost = price * event.quantity

                # 3. 잔고/보유량 검증 및 업데이트
                portfolio = calculate_user_portfolio_up_to(user_locked, event.id)

                if event.event_type == 'BUY':
                    if user_locked.balance < total_cost:
                        raise ValueError(f"잔액이 부족합니다. (필요: {total_cost:,.0f}원, 잔액: {user_locked.balance:,.0f}원)")
                    user_locked.balance -= total_cost
                    user_locked.save()
                elif event.event_type == 'SELL':
                    current_qty = portfolio.get(event.stock_symbol, 0)
                    if current_qty < event.quantity:
                        raise ValueError(f"보유 주식이 부족합니다. (보유: {current_qty}주, 요청: {event.quantity}주)")
                    user_locked.balance += total_cost
                    user_locked.save()

                event.status = 'PROCESSED'
                event.processed_at = timezone.now()
                event.save()

            except CalculationDataInsufficientError as e:
                # 시스템 가격 결손 오류 발생 시, 해당 날짜의 스냅샷을 FAILED로 마킹하여 계정 블록
                event_date = event.created_at.astimezone(pytz.timezone('Asia/Seoul')).date()
                UserBalanceSnapshot.objects.update_or_create(
                    user=user_locked,
                    snapshot_date=event_date,
                    defaults={
                        'balance': user_locked.balance,
                        'portfolio': calculate_user_portfolio_up_to(user_locked, event.id),
                        'status': 'FAILED',
                        'error_details': str(e)
                    }
                )
                break
            except Exception as e:
                # 사용자 주문 실패 (잔액 부족, 시간 외 거래 등)
                event.status = 'FAILED'
                event.error_message = str(e)
                event.processed_at = timezone.now()
                event.save()
                # 실패한 이벤트 이후의 이벤트도 처리하지 않음
                break


def check_and_create_snapshots(user):
    """
    사용자가 접속했을 때, 전날까지의 미정산 이벤트가 존재하면 스냅샷을 생성합니다.
    """
    if UserBalanceSnapshot.objects.filter(user=user, status='FAILED').exists():
        return

    kst = pytz.timezone('Asia/Seoul')
    now_kst = timezone.now().astimezone(kst)
    yesterday = now_kst.date() - timedelta(days=1)

    # 어제 날짜에 대한 완성된 스냅샷이 이미 있으면 정산 필요 없음
    if UserBalanceSnapshot.objects.filter(user=user, snapshot_date=yesterday, status='COMPLETED').exists():
        return

    with transaction.atomic():
        user_locked = User.objects.select_for_update().get(id=user.id)

        if UserBalanceSnapshot.objects.filter(user=user_locked, status='FAILED').exists():
            return

        latest_snapshot = UserBalanceSnapshot.objects.filter(
            user=user_locked,
            status='COMPLETED'
        ).order_by('-snapshot_date').first()

        if latest_snapshot:
            start_date = latest_snapshot.snapshot_date + timedelta(days=1)
            current_balance = latest_snapshot.balance
            current_portfolio = latest_snapshot.portfolio.copy()
        else:
            start_date = date(2000, 1, 1)
            current_balance = 10000000.0
            current_portfolio = {}

        # 전날까지의 PENDING 이벤트들 가져옴
        pending_events = StockTradeEvent.objects.filter(
            user=user_locked,
            status='PENDING',
            created_at__date__lte=yesterday
        ).order_by('id').select_for_update()

        try:
            for event in pending_events:
                # 이전 이벤트 중 실패(FAILED)한 건이 있다면 정산 진행 불가
                failed_exists = StockTradeEvent.objects.filter(
                    user=user_locked,
                    status='FAILED',
                    id__lt=event.id
                ).exists()
                if failed_exists:
                    raise CalculationDataInsufficientError(
                        f"이전 이벤트 {event.id}가 실패(FAILED) 상태여서 정산을 진행할 수 없습니다."
                    )

                stock = Stock.objects.get(symbol=event.stock_symbol)
                
                # 1. 거래 시간대 검증
                is_open, error_reason = is_market_open(stock.market, event.created_at)
                if not is_open:
                    event.status = 'FAILED'
                    event.error_message = error_reason
                    event.processed_at = timezone.now()
                    event.save()
                    continue

                # 2. 주가 정보 조회
                price_record = get_price_at_timestamp(stock, event.created_at)
                if not price_record:
                    raise CalculationDataInsufficientError(
                        f"종목 {event.stock_symbol}의 {event.created_at} 기준 주가 정보가 존재하지 않습니다."
                    )

                price = price_record.close_price
                total_cost = price * event.quantity

                # 3. 거래 처리
                if event.event_type == 'BUY':
                    if current_balance < total_cost:
                        event.status = 'FAILED'
                        event.error_message = f"잔액이 부족합니다. (필요: {total_cost:,.0f}원, 잔액: {current_balance:,.0f}원)"
                        event.processed_at = timezone.now()
                        event.save()
                        continue
                    current_balance -= total_cost
                    current_portfolio[event.stock_symbol] = current_portfolio.get(event.stock_symbol, 0) + event.quantity
                    
                    event.status = 'PROCESSED'
                    event.processed_at = timezone.now()
                    event.save()

                elif event.event_type == 'SELL':
                    if current_portfolio.get(event.stock_symbol, 0) < event.quantity:
                        event.status = 'FAILED'
                        event.error_message = f"보유 주식이 부족합니다. (보유: {current_portfolio.get(event.stock_symbol, 0)}주, 요청: {event.quantity}주)"
                        event.processed_at = timezone.now()
                        event.save()
                        continue
                    current_balance += total_cost
                    current_portfolio[event.stock_symbol] = current_portfolio.get(event.stock_symbol, 0) - event.quantity
                    if current_portfolio[event.stock_symbol] <= 0:
                        current_portfolio.pop(event.stock_symbol, None)

                    event.status = 'PROCESSED'
                    event.processed_at = timezone.now()
                    event.save()

            # 어제 날짜에 대한 완료(COMPLETED) 스냅샷 생성
            UserBalanceSnapshot.objects.create(
                user=user_locked,
                snapshot_date=yesterday,
                balance=current_balance,
                portfolio=current_portfolio,
                status='COMPLETED'
            )

            # 사용자 최종 잔고 반영
            user_locked.balance = current_balance
            user_locked.save()

        except CalculationDataInsufficientError as e:
            # 주가 데이터가 부족할 경우 FAILED 상태로 정산 오류 기록
            UserBalanceSnapshot.objects.create(
                user=user_locked,
                snapshot_date=yesterday,
                balance=current_balance,
                portfolio=current_portfolio,
                status='FAILED',
                error_details=str(e)
            )


def reconstruct_user_state(user):
    """
    최신 COMPLETED 스냅샷을 기반으로 그 이후의 PROCESSED 이벤트를 재생(Replay)하여 상태를 재구성합니다.
    """
    latest_snapshot = UserBalanceSnapshot.objects.filter(
        user=user,
        status='COMPLETED'
    ).order_by('-snapshot_date').first()

    if latest_snapshot:
        balance = latest_snapshot.balance
        portfolio = latest_snapshot.portfolio.copy()
        start_date = latest_snapshot.snapshot_date + timedelta(days=1)
    else:
        balance = 10000000.0
        portfolio = {}
        start_date = date(2000, 1, 1)

    events = StockTradeEvent.objects.filter(
        user=user,
        status='PROCESSED',
        created_at__date__gte=start_date
    ).order_by('id')

    for event in events:
        stock = Stock.objects.get(symbol=event.stock_symbol)
        price_record = get_price_at_timestamp(stock, event.created_at)
        if not price_record:
            continue
        price = price_record.close_price
        total_cost = price * event.quantity

        if event.event_type == 'BUY':
            balance -= total_cost
            portfolio[event.stock_symbol] = portfolio.get(event.stock_symbol, 0) + event.quantity
        elif event.event_type == 'SELL':
            balance += total_cost
            portfolio[event.stock_symbol] = portfolio.get(event.stock_symbol, 0) - event.quantity
            if portfolio[event.stock_symbol] <= 0:
                portfolio.pop(event.stock_symbol, None)

    return balance, portfolio
