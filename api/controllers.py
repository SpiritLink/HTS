from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from django.utils import timezone
from hts.models import Stock, StockPrice, DataFetchRequest, StockTradingCalendar
from hts.services.cache_service import get_cached_prices, cache_prices
from .serializers import StockSerializer, StockPriceSerializer
from datetime import datetime, timedelta


def get_today():
    """
    오늘 날짜를 반환합니다.
    """
    return timezone.now().date()


def validate_date_range(start_date, end_date):
    """
    조회 기간의 유효성을 검사합니다.
    
    Returns:
        tuple: (is_valid: bool, error_message: str, adjusted_start: date, adjusted_end: date)
    """
    today = get_today()
    
    # 시작일이 종료일보다 늦은 경우
    if start_date > end_date:
        return False, "시작일은 종료일보다 이전이어야 합니다.", None, None
    
    # 종료일이 오늘 이후인 경우
    if end_date >= today:
        return False, f"조회 기간의 종료일은 어제({today - timedelta(days=1)})까지만 가능합니다. 오늘({today}) 및 미래 데이터는 조회할 수 없습니다.", None, None
    
    # 시작일이 오늘 이후인 경우
    if start_date >= today:
        return False, f"조회 기간의 시작일은 어제({today - timedelta(days=1)})까지만 가능합니다.", None, None
    
    return True, None, start_date, end_date


def adjust_to_yesterday(end_date):
    """
    종료일이 오늘 이후라면 어제로 조정합니다.
    """
    today = get_today()
    if end_date >= today:
        return today - timedelta(days=1)
    return end_date


def get_default_date_range(days=30):
    """
    기본 조회 기간을 반환합니다 (어제 기준).
    """
    today = get_today()
    end_date = today - timedelta(days=1)  # 어제
    start_date = end_date - timedelta(days=days-1)  # days일 전
    return start_date, end_date


def get_missing_trading_days(symbol, start_date, end_date):
    """
    요청된 기간 중 거래일이면서도 데이터가 없는 날짜들을 반환합니다.
    주말/공휴일은 제외하고 실제로 데이터가 필요한 날짜만 반환합니다.
    """
    # 캘린더에서 해당 기간의 거래일 정보 조회
    calendar_entries = StockTradingCalendar.objects.filter(
        symbol=symbol,
        date__range=(start_date, end_date)
    )
    
    # 데이터가 없는 거래일 (NO_DATA) 또는 캘린더에 없는 평일
    missing_dates = []
    current = start_date
    
    while current <= end_date:
        weekday = current.weekday()
        
        # 주말은 스킵
        if weekday >= 5:
            current += timedelta(days=1)
            continue
        
        try:
            entry = calendar_entries.get(date=current)
            # 거래일이어야 하는데 데이터가 없는 경우
            if entry.day_type == 'NO_DATA':
                missing_dates.append(current)
        except StockTradingCalendar.DoesNotExist:
            # 캘린더에 없는 평일 - 데이터가 필요함
            missing_dates.append(current)
        
        current += timedelta(days=1)
    
    return missing_dates


def check_and_request_missing_data(symbol, start_date, end_date, existing_prices):
    """
    누락된 거래일 데이터가 있는지 확인하고, 필요시 큐에 등록합니다.
    주말/공휴일은 제외하고 실제 거래일만 체크합니다.
    """
    # DB에 있는 날짜들 추출 (QuerySet을 다시 폄질하지 않고 한 번만 조회)
    existing_dates = set(existing_prices.values_list('timestamp__date', flat=True))
    
    # 캘린더 기준으로 누락된 거래일 계산
    calendar_entries = StockTradingCalendar.objects.filter(
        symbol=symbol,
        date__range=(start_date, end_date)
    )
    
    # 캘린더에서 거래일로 표시된 날짜 종류 (has_price_data=True 기준)
    trading_days_from_calendar = set(
        calendar_entries.filter(day_type='TRADING', has_price_data=True).values_list('date', flat=True)
    )
    
    # 캘린더에서 NO_DATA로 표시된 날짜
    no_data_from_calendar = set(
        calendar_entries.filter(day_type='NO_DATA').values_list('date', flat=True)
    )
    
    missing_trading_days = []
    no_data_days = []
    
    current = start_date
    while current <= end_date:
        weekday = current.weekday()
        
        # 주말은 스킵
        if weekday >= 5:
            current += timedelta(days=1)
            continue
        
        # 1. 캘린더에서 거래일+데이터있음 표시 + 실제 데이터도 있음 → OK
        if current in trading_days_from_calendar:
            if current in existing_dates:
                # 모두 일치 - 정상
                pass
            else:
                # 캘린더에는 데이터 있음으로 표시되어 있지만 실제로 없음
                # → 데이터 부존성 문제, 재요청 필요
                missing_trading_days.append(current)
        # 2. 캘린더에서 NO_DATA 표시된 날짜
        elif current in no_data_from_calendar:
            no_data_days.append(current)
        # 3. 캘린더에 없는 날짜 (처음 조회)
        elif current not in existing_dates:
            missing_trading_days.append(current)
        
        current += timedelta(days=1)
    
    if not missing_trading_days and not no_data_days:
        return {
            'has_missing': False,
            'message': 'All trading days have data',
            'missing_ranges': [],
            'queued_ranges': [],
            'pending_ranges': []
        }
    
    # 누락된 날짜들을 범위로 그룹화
    all_missing = sorted(set(missing_trading_days + no_data_days))
    missing_ranges = []
    
    if all_missing:
        range_start = all_missing[0]
        range_end = all_missing[0]
        
        for i in range(1, len(all_missing)):
            if all_missing[i] == range_end + timedelta(days=1) or all_missing[i] == range_end + timedelta(days=3):  # 주말 걱정
                range_end = all_missing[i]
            else:
                missing_ranges.append((range_start, range_end))
                range_start = all_missing[i]
                range_end = all_missing[i]
        
        missing_ranges.append((range_start, range_end))
    
    # 큐에 등록
    queued_ranges = []
    pending_ranges = []
    
    for miss_start, miss_end in missing_ranges:
        existing_request = DataFetchRequest.objects.filter(
            symbol=symbol,
            start_date=miss_start,
            end_date=miss_end,
            status__in=['PENDING', 'PROCESSING']
        ).first()
        
        if existing_request:
            pending_ranges.append((miss_start, miss_end))
        else:
            if not DataFetchRequest.objects.filter(
                symbol=symbol,
                start_date=miss_start,
                end_date=miss_end
            ).exists():
                DataFetchRequest.objects.create(
                    symbol=symbol,
                    start_date=miss_start,
                    end_date=miss_end
                )
                queued_ranges.append((miss_start, miss_end))
    
    # 메시지 생성
    messages = []
    if pending_ranges:
        ranges_str = ', '.join([f"{s}~{e}" for s, e in pending_ranges])
        messages.append(f"Fetching in progress: {ranges_str}")
    if queued_ranges:
        ranges_str = ', '.join([f"{s}~{e}" for s, e in queued_ranges])
        messages.append(f"New request queued: {ranges_str}")
    
    return {
        'has_missing': True,
        'message': '; '.join(messages) if messages else 'Missing trading day data detected',
        'missing_ranges': missing_ranges,
        'queued_ranges': queued_ranges,
        'pending_ranges': pending_ranges,
        'weekend_days': [],  # 주말은 제외
        'holiday_days': []   # 공휴일은 제외
    }


class StockListAPIView(APIView):
    """
    주식 종목 전체 조회 API
    """
    def get(self, request):
        search = request.query_params.get('search')
        
        if search:
            stocks = Stock.objects.filter(
                Q(name__icontains=search) | Q(symbol__icontains=search)
            )
        else:
            stocks = Stock.objects.all()
        
        serializer = StockSerializer(stocks, many=True)
        return Response({
            "status": "success",
            "message": "Stock list retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class StockPriceRangeAPIView(APIView):
    def get(self, request):
        """
        3. 주식 이름/심볼로 가격 검색 API
        - 주말/공휴일은 제외하고 실제 거래일 데이터만 확인
        - 오늘 및 미래 날짜는 조회 불가
        """
        search = request.query_params.get('search')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        # 날짜 파싱
        try:
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = get_today() - timedelta(days=1)  # 어제
            
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                start_date = end_date - timedelta(days=29)
        except ValueError:
            return Response({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD format."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 조회 기간 유효성 검사
        is_valid, error_message, start_date, end_date = validate_date_range(start_date, end_date)
        if not is_valid:
            return Response({
                "status": "error",
                "message": error_message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        symbol_filter = Q()
        symbols_to_check = []
        
        if search:
            matching_stocks = Stock.objects.filter(
                Q(name__icontains=search) | Q(symbol__icontains=search)
            )
            if not matching_stocks.exists():
                return Response({
                    "status": "error",
                    "message": f"No stocks found matching '{search}'"
                }, status=status.HTTP_404_NOT_FOUND)
            
            symbols_to_check = list(matching_stocks.values_list('symbol', flat=True))
            symbol_filter = Q(symbol__in=symbols_to_check)
        
        prices = StockPrice.objects.filter(
            symbol_filter,
            timestamp__date__range=(start_date, end_date)
        ).order_by('symbol', 'timestamp')
        
        # 데이터가 없을 경우
        if not prices.exists():
            if not symbols_to_check:
                return Response({
                    "status": "error",
                    "message": "Please provide a search parameter when no data exists."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            pending_requests = []
            new_requests = []
            
            for symbol in symbols_to_check:
                existing = DataFetchRequest.objects.filter(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    status__in=['PENDING', 'PROCESSING']
                ).first()
                
                if existing:
                    pending_requests.append(symbol)
                else:
                    if not DataFetchRequest.objects.filter(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date
                    ).exists():
                        DataFetchRequest.objects.create(
                            symbol=symbol,
                            start_date=start_date,
                            end_date=end_date
                        )
                        new_requests.append(symbol)
            
            if pending_requests:
                return Response({
                    "status": "pending",
                    "message": f"Data is being fetched for: {', '.join(pending_requests)}"
                }, status=status.HTTP_202_ACCEPTED)
            else:
                return Response({
                    "status": "accepted",
                    "message": f"Data request queued for: {', '.join(new_requests)}"
                }, status=status.HTTP_202_ACCEPTED)
        
        # 일부만 있는 경우 (주말/공휴일 제외하고 거래일만 체크)
        missing_data_info = {}
        
        if symbols_to_check:
            for symbol in symbols_to_check:
                symbol_prices = prices.filter(symbol=symbol)
                result = check_and_request_missing_data(symbol, start_date, end_date, symbol_prices)
                if result['has_missing']:
                    missing_data_info[symbol] = result
        
        serializer = StockPriceSerializer(prices, many=True)
        
        response_data = {
            "status": "success",
            "message": "Stock prices retrieved successfully",
            "data": serializer.data
        }
        
        if missing_data_info:
            response_data["status"] = "partial"
            response_data["missing_data"] = {
                "info": "Some trading day data is missing",
                "details": missing_data_info
            }
        
        return Response(response_data, status=status.HTTP_200_OK)


class StockPriceSingleAPIView(APIView):
    def get(self, request):
        """
        4. 단일 주식 가격 조회 API
        """
        symbol = request.query_params.get('symbol')
        timestamp_str = request.query_params.get('timestamp')
        
        if not symbol or not timestamp_str:
             return Response({
                 "status": "error", 
                 "message": "symbol and timestamp are required parameters"
             }, status=status.HTTP_400_BAD_REQUEST)
             
        timestamp = parse_datetime(timestamp_str)
        
        if not timestamp:
            return Response({
                "status": "error", 
                "message": "Invalid datetime format. Use ISO 8601"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            price = StockPrice.objects.get(symbol=symbol, timestamp=timestamp)
            serializer = StockPriceSerializer(price)
            
            return Response({
                "status": "success",
                "message": "Stock price retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
            
        except StockPrice.DoesNotExist:
             return Response({
                 "status": "error", 
                 "message": "Stock price not found for the given symbol and timestamp"
             }, status=status.HTTP_404_NOT_FOUND)
        
        
class StockSymbolPriceRangeAPIView(APIView):
    def get(self, request):
        """
        5. 특정 종목의 기간별 가격 조회 API
        - 주말/공휴일은 제외하고 실제 거래일만 확인
        - 거래일에 데이터가 없는 경우에만 Yahoo Finance 요청
        - 오늘 및 미래 날짜는 조회 불가
        - Redis 캐싱 적용
        """
        symbol = request.query_params.get('symbol')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        interval = request.query_params.get('interval', '1d')  # 기본값: 1일

        # 날짜 파싱
        try:
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                # 기본값: 어제
                end_date = get_today() - timedelta(days=1)
            
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                # 기본값: 30일 전
                start_date = end_date - timedelta(days=29)
        except ValueError:
            return Response({
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD format."
            }, status=status.HTTP_400_BAD_REQUEST)

        if not symbol:
            return Response({
                "status": "error",
                "message": "symbol is a required parameter"
            }, status=status.HTTP_400_BAD_REQUEST)

        # 조회 기간 유효성 검사
        is_valid, error_message, start_date, end_date = validate_date_range(start_date, end_date)
        if not is_valid:
            return Response({
                "status": "error",
                "message": error_message
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. Redis 캐시에서 먼저 조회
        cache_hit, cached_data = get_cached_prices(symbol, interval, start_date, end_date)
        if cache_hit:
            return Response({
                "status": "success",
                "message": f"Stock prices for {symbol} retrieved from cache",
                "period": f"{start_date} to {end_date}",
                "interval": interval,
                "count": len(cached_data),
                "source": "cache",
                "data": cached_data
            }, status=status.HTTP_200_OK)

        # 2. 캐시에 없으면 DB에서 조회
        prices = StockPrice.objects.filter(
            symbol=symbol,
            interval=interval,
            timestamp__date__range=(start_date, end_date)
        ).order_by('timestamp')

        # 데이터가 전혀 없을 경우
        if not prices.exists():
            existing_pending = DataFetchRequest.objects.filter(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                status__in=['PENDING', 'PROCESSING']
            ).first()
            
            if existing_pending:
                return Response({
                    "status": "pending",
                    "message": f"Data for {symbol} is being fetched. Please try again later.",
                    "requested_at": existing_pending.created_at
                }, status=status.HTTP_202_ACCEPTED)
            
            DataFetchRequest.objects.create(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            return Response({
                "status": "accepted",
                "message": f"Data request for {symbol} has been queued.",
                "period": f"{start_date} to {end_date}"
            }, status=status.HTTP_202_ACCEPTED)

        # 일부만 있는 경우 (주말/공휴일 제외)
        missing_check = check_and_request_missing_data(symbol, start_date, end_date, prices)

        serializer = StockPriceSerializer(prices, many=True)
        serialized_data = serializer.data
        
        # 3. DB에서 조회한 데이터를 Redis에 캐싱
        cache_prices(symbol, interval, start_date, end_date, serialized_data)
        
        response_data = {
            "status": "success",
            "message": f"Stock prices for {symbol} retrieved successfully",
            "period": f"{start_date} to {end_date}",
            "interval": interval,
            "count": prices.count(),
            "source": "database",
            "data": serialized_data
        }
        
        # 누락된 거래일 데이터가 있으면 응답에 추가
        if missing_check['has_missing']:
            response_data["status"] = "partial"
            response_data["missing_data"] = {
                "message": missing_check['message'],
                "missing_ranges": [f"{s}~{e}" for s, e in missing_check['missing_ranges']],
                "queued_ranges": [f"{s}~{e}" for s, e in missing_check['queued_ranges']],
                "pending_ranges": [f"{s}~{e}" for s, e in missing_check['pending_ranges']],
                "note": "Weekends and holidays are excluded from missing data check"
            }

        return Response(response_data, status=status.HTTP_200_OK)



