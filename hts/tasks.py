import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import DataFetchRequest, Stock, StockPrice, StockTradingCalendar

logger = logging.getLogger(__name__)


def get_today():
    """
    오늘 날짜를 반환합니다.
    """
    from django.utils import timezone
    return timezone.now().date()


def is_valid_date_for_calendar(date):
    """
    캘린더에 등록 가능한 날짜인지 확인합니다.
    오늘과 미래는 등록할 수 없습니다.
    """
    today = get_today()
    return date < today


def get_yahoo_ticker_symbol(symbol, market=None):
    """
    DB의 종목 코드를 Yahoo Finance 형식으로 변환합니다.
    
    - 한국 코스피: 005930 → 005930.KS
    - 한국 코스닥: 035720 → 035720.KQ
    - 미국: AAPL → AAPL (그대로)
    """
    if not market:
        try:
            stock = Stock.objects.get(symbol=symbol)
            market = stock.market
        except Stock.DoesNotExist:
            if symbol.isdigit() and len(symbol) == 6:
                market = 'KR'
            else:
                market = 'US'
    
    if '.' in symbol:
        return symbol
    
    if market in ['KR', 'KOSPI', 'KRX']:
        return f"{symbol}.KS"
    elif market in ['KQ', 'KOSDAQ']:
        return f"{symbol}.KQ"
    elif market in ['JP', 'T']:
        return f"{symbol}.T"
    elif market in ['HK', 'HKEX']:
        return f"{symbol}.HK"
    return symbol


def get_market_holidays(market, year):
    """
    시장별 기본 공휴일을 반환합니다.
    TODO: 실제 공휴일 API 연동 가능
    """
    # 현재는 빈 리스트 반환 (추후 확장)
    return []


@shared_task(bind=True, max_retries=3)
def fetch_stock_data(self, request_id):
    """
    특정 DataFetchRequest를 처리하여 Yahoo Finance에서 주가 데이터를 가져옵니다.
    주말/공휴일은 캘린더에 별도 표기하고, 거래일에만 데이터를 저장합니다.
    
    지원 interval: 1d (일별), 1h (1시간), 30m, 15m, 5m
    """
    try:
        with transaction.atomic():
            fetch_request = DataFetchRequest.objects.select_for_update().get(id=request_id)
            
            if fetch_request.status not in ['PENDING', 'PROCESSING']:
                logger.info(f"Request {request_id} is already completed or failed.")
                return
            
            fetch_request.status = 'PROCESSING'
            fetch_request.save()
            
            symbol = fetch_request.symbol
            start_date = fetch_request.start_date
            end_date = fetch_request.end_date
            interval = fetch_request.interval  # '1d', '1h', '30m', etc.
            
            yahoo_symbol = get_yahoo_ticker_symbol(symbol)
            
            logger.info(f"[FETCH] {symbol} ({yahoo_symbol}) | {start_date} ~ {end_date} | interval={interval}")
            
            ticker = yf.Ticker(yahoo_symbol)
            
            end_datetime = datetime.combine(end_date, datetime.max.time())
            start_datetime = datetime.combine(start_date, datetime.min.time())
            
            try:
                # interval에 따라 데이터 조회 방식 변경
                if interval == '1d':
                    hist = ticker.history(start=start_datetime, end=end_datetime, interval='1d')
                elif interval == '1h':
                    # 1시간 데이터는 최대 730일까지만 제공
                    hist = ticker.history(start=start_datetime, end=end_datetime, interval='1h')
                elif interval in ['30m', '15m', '5m']:
                    hist = ticker.history(start=start_datetime, end=end_datetime, interval=interval)
                else:
                    hist = ticker.history(start=start_datetime, end=end_datetime, interval='1d')
            except Exception as e:
                logger.warning(f"Yahoo Finance error for {yahoo_symbol}: {e}")
                hist = pd.DataFrame()
            
            # 시장 정보 확인
            try:
                ticker_info = ticker.info if hasattr(ticker, 'info') else {}
                market_from_yahoo = ticker_info.get('market', 'US')
                long_name = ticker_info.get('longName', symbol)
            except:
                market_from_yahoo = 'US'
                long_name = symbol
            
            # Stock 모델 조회 또는 생성
            stock, created = Stock.objects.get_or_create(
                symbol=symbol,
                defaults={
                    'name': long_name,
                    'market': market_from_yahoo
                }
            )
            
            # 요청 기간의 모든 날짜에 대해 캘린더 생성 (오늘과 미래는 제외)
            current_date = start_date
            trading_days_in_data = set()
            today = get_today()
            
            while current_date <= end_date:
                # 오늘과 미래는 캘린더에 등록하지 않음
                if current_date >= today:
                    current_date += timedelta(days=1)
                    continue
                
                weekday = current_date.weekday()
                
                if weekday >= 5:  # 토(5), 일(6)
                    # 주말로 마킹
                    StockTradingCalendar.mark_day_type(
                        symbol=symbol,
                        market=market_from_yahoo,
                        date=current_date,
                        day_type='WEEKEND',
                        has_price_data=False
                    )
                else:
                    # 평일 - 일단 NO_DATA로 설정 (데이터 확인 후 업데이트)
                    StockTradingCalendar.mark_day_type(
                        symbol=symbol,
                        market=market_from_yahoo,
                        date=current_date,
                        day_type='NO_DATA',
                        has_price_data=False
                    )
                
                current_date += timedelta(days=1)
            
            # Yahoo Finance에서 가져온 데이터가 있으면 저장
            if not hist.empty:
                price_objects = []
                
                for index, row in hist.iterrows():
                    if hasattr(index, 'to_pydatetime'):
                        timestamp = timezone.make_aware(index.to_pydatetime()) if not index.tzinfo else index.to_pydatetime()
                    else:
                        timestamp = timezone.make_aware(datetime.combine(index, datetime.min.time()))
                    
                    price_date = timestamp.date()
                    trading_days_in_data.add(price_date)
                    
                    price_objects.append(StockPrice(
                        stock=stock,
                        symbol=symbol,
                        market=stock.market,
                        interval=interval,  # 데이터 간격 저장
                        timestamp=timestamp,
                        open_price=round(float(row['Open']), 2) if pd.notna(row['Open']) else None,
                        high_price=round(float(row['High']), 2) if pd.notna(row['High']) else None,
                        low_price=round(float(row['Low']), 2) if pd.notna(row['Low']) else None,
                        close_price=round(float(row['Close']), 2),
                        volume=int(row['Volume']) if pd.notna(row['Volume']) else None
                    ))
                
                # 벌크 생성
                created_records = StockPrice.objects.bulk_create(
                    price_objects,
                    ignore_conflicts=True
                )
                
                # 캘린더 업데이트 - 데이터가 있는 날짜는 TRADING으로 표시 (오늘/미래 제외)
                # 시간 단위 데이터도 일별로 캘린더 업데이트
                for price_date in trading_days_in_data:
                    if is_valid_date_for_calendar(price_date):
                        StockTradingCalendar.mark_day_type(
                            symbol=symbol,
                            market=market_from_yahoo,
                            date=price_date,
                            day_type='TRADING',
                            has_price_data=True
                        )
                
                interval_label = "hours" if interval != '1d' else "days"
                logger.info(f"[SUCCESS] {symbol}: Saved {len(price_objects)} records ({interval}), {len(trading_days_in_data)} trading days")
            else:
                logger.warning(f"[NO_DATA] {symbol}: No trading data from Yahoo Finance for {start_date} ~ {end_date}")
            
            fetch_request.status = 'COMPLETED'
            fetch_request.save()
            
    except Exception as exc:
        logger.exception(f"[ERROR] Request {request_id}: {exc}")
        try:
            fetch_request = DataFetchRequest.objects.get(id=request_id)
            fetch_request.status = 'FAILED'
            fetch_request.save()
        except DataFetchRequest.DoesNotExist:
            pass
        raise self.retry(exc=exc, countdown=300)


@shared_task
def process_pending_fetch_requests():
    """
    PENDING 상태인 모든 DataFetchRequest를 처리합니다.
    """
    pending_requests = DataFetchRequest.objects.filter(status='PENDING')
    
    if not pending_requests.exists():
        return
    
    logger.info(f"[QUEUE] Found {pending_requests.count()} pending requests")
    
    for request in pending_requests:
        fetch_stock_data.delay(request.id)
        logger.info(f"[QUEUE] Task queued: {request.symbol} ({request.start_date} ~ {request.end_date})")


@shared_task
def sync_calendar_with_prices():
    """
    StockTradingCalendar와 StockPrice 데이터를 동기화합니다.
    실제 데이터가 있는데 캘린더에 반영되지 않은 경우를修正합니다.
    """
    from django.db.models import Count
    
    # 실제 데이터가 있는 날짜들 조회
    price_dates = StockPrice.objects.values('symbol', 'market').annotate(
        dates=Count('timestamp__date')
    ).order_by('symbol')
    
    updated_count = 0
    
    for entry in price_dates:
        symbol = entry['symbol']
        
        # 해당 종목의 모든 주가 데이터 날짜 조회
        timestamps = StockPrice.objects.filter(symbol=symbol).values_list('timestamp', flat=True)
        
        for ts in timestamps:
            price_date = ts.date() if hasattr(ts, 'date') else ts
            
            # 캘린더 업데이트
            calendar, created = StockTradingCalendar.objects.get_or_create(
                symbol=symbol,
                date=price_date,
                defaults={
                    'market': entry['market'],
                    'day_type': 'TRADING',
                    'has_price_data': True
                }
            )
            
            if not created and not calendar.has_price_data:
                calendar.day_type = 'TRADING'
                calendar.has_price_data = True
                calendar.save()
                updated_count += 1
    
    logger.info(f"[SYNC] Updated {updated_count} calendar entries")
    return updated_count


@shared_task
def cleanup_old_completed_requests(days=7):
    """
    오래된 COMPLETED 상태의 요청들을 정리합니다.
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    old_requests = DataFetchRequest.objects.filter(
        status='COMPLETED',
        updated_at__lt=cutoff_date
    )
    
    deleted_count, _ = old_requests.delete()
    logger.info(f"[CLEANUP] Deleted {deleted_count} old requests")
    return deleted_count
