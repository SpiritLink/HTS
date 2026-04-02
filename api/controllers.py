from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from hts.models import Stock, StockPrice, DataFetchRequest, StockTradingCalendar
from .serializers import StockSerializer, StockPriceSerializer
from datetime import datetime, timedelta


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
    # DB에 있는 날짜들 추출
    existing_dates = set(existing_prices.values_list('timestamp__date', flat=True))
    
    # 캘린더 기준으로 누락된 거래일 계산
    calendar_entries = StockTradingCalendar.objects.filter(
        symbol=symbol,
        date__range=(start_date, end_date)
    )
    
    missing_trading_days = []
    no_data_days = []  # NO_DATA로 마킹된 날짜 (Yahoo에 요청할 날짜)
    
    current = start_date
    while current <= end_date:
        weekday = current.weekday()
        
        # 주말은 스킵
        if weekday >= 5:
            current += timedelta(days=1)
            continue
        
        # DB에 데이터가 있는지 확인
        if current not in existing_dates:
            try:
                entry = calendar_entries.get(date=current)
                if entry.day_type == 'NO_DATA':
                    # 이미 조회했지만 데이터가 없었던 날
                    no_data_days.append(current)
                elif entry.day_type in ['WEEKEND', 'HOLIDAY']:
                    # 공휴일 - 스킵
                    pass
                else:
                    # 알 수 없는 상태 - 조회 필요
                    missing_trading_days.append(current)
            except StockTradingCalendar.DoesNotExist:
                # 캘린더에 없음 - 처음 조회하는 거래일
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


class StockAPIView(APIView):
    def get(self, request):
        """
        1. 주식 정보를 조회할 수 있는 GET API
        """
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

    def post(self, request):
        """
        2. 주식 정보를 추가할 수 있는 POST API
        """
        is_many = isinstance(request.data, list)
        serializer = StockSerializer(data=request.data, many=is_many)
        
        if serializer.is_valid():
            if is_many:
                symbols = [item.get('symbol') for item in serializer.validated_data if item.get('symbol')]
                existing_stocks = Stock.objects.filter(symbol__in=symbols).values_list('symbol', flat=True)
                if existing_stocks:
                    return Response({
                        "status": "error", 
                        "message": f"Some stocks already exist: {', '.join(existing_stocks)}"
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                symbol = serializer.validated_data.get('symbol')
                if Stock.objects.filter(symbol=symbol).exists():
                    return Response({
                        "status": "error", 
                        "message": "Stock already exists"
                    }, status=status.HTTP_400_BAD_REQUEST)
                
            serializer.save()
            return Response({
                "status": "success",
                "message": "Stocks added successfully" if is_many else "Stock added successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
            
        return Response({
            "status": "error",
            "message": "Invalid data",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class StockPriceRangeAPIView(APIView):
    def get(self, request):
        """
        3. 주식 이름/심볼로 가격 검색 API
        - 주말/공휴일은 제외하고 실제 거래일 데이터만 확인
        """
        search = request.query_params.get('search')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        end_date = datetime.now().date() if not end_date_str else datetime.strptime(end_date_str, '%Y-%m-%d').date()
        start_date = end_date - timedelta(days=30) if not start_date_str else datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
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
        """
        symbol = request.query_params.get('symbol')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        end_date = datetime.now().date() if not end_date_str else datetime.strptime(end_date_str, '%Y-%m-%d').date()
        start_date = end_date - timedelta(days=30) if not start_date_str else datetime.strptime(start_date_str, '%Y-%m-%d').date()

        if not symbol:
            return Response({
                "status": "error",
                "message": "symbol is a required parameter"
            }, status=status.HTTP_400_BAD_REQUEST)

        # DB에서 데이터 조회
        prices = StockPrice.objects.filter(
            symbol=symbol,
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
        
        response_data = {
            "status": "success",
            "message": f"Stock prices for {symbol} retrieved successfully",
            "period": f"{start_date} to {end_date}",
            "count": prices.count(),
            "data": serializer.data
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


class BulkStockPriceCreateAPIView(APIView):
    def post(self, request):
        """
        6. 여러 주식 가격 정보 일괄 등록 API
        """
        if not isinstance(request.data, list):
            return Response({
                "status": "error",
                "message": "Expected a list of objects but got a single object or invalid format."
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = StockPriceSerializer(data=request.data, many=True)
        
        if serializer.is_valid():
            try:
                serializer.save()
                return Response({
                    "status": "success",
                    "message": f"Successfully created {len(serializer.data)} stock price records.",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                 return Response({
                    "status": "error",
                    "message": "An error occurred while saving the data.",
                    "details": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
                 
        return Response({
            "status": "error",
            "message": "Invalid data format or missing required fields.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
