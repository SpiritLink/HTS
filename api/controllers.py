from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.dateparse import parse_datetime
from hts.models import Stock, StockPrice
from .serializers import StockSerializer, StockPriceSerializer

class StockAPIView(APIView):
    def get(self, request):
        """
        1. 주식 정보를 조회할 수 있는 GET API
        모든 주식 종목 정보를 반환합니다.
        """
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
        단일 종목 또는 여러 종목(리스트)을 한 번에 등록합니다.
        """
        is_many = isinstance(request.data, list)
        serializer = StockSerializer(data=request.data, many=is_many)
        
        if serializer.is_valid():
            # 중복 체크
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
        3. 시작 시각 / 종료 시각을 파라미터로 전달받고, 해당 기간동안 존재하는 db 값을 반환하는 GET API
        """
        start_time_str = request.query_params.get('start_time')
        end_time_str = request.query_params.get('end_time')
        
        if not start_time_str or not end_time_str:
            return Response({
                "status": "error", 
                "message": "start_time and end_time are required parameters"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        start_time = parse_datetime(start_time_str)
        end_time = parse_datetime(end_time_str)
        
        if not start_time or not end_time:
             return Response({
                 "status": "error", 
                 "message": "Invalid datetime format. Use ISO 8601 (e.g., 2023-10-27T10:00:00Z)"
             }, status=status.HTTP_400_BAD_REQUEST)
             
        prices = StockPrice.objects.filter(timestamp__range=(start_time, end_time))
        serializer = StockPriceSerializer(prices, many=True)
        
        return Response({
            "status": "success",
            "message": "Stock prices retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

class StockPriceSingleAPIView(APIView):
    def get(self, request):
        """
        4. 시각 / 종목 ID를 파라미터로 받은뒤 단일 가격 정보를 반환하는 API
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
        5. 시작 시각 / 종료 시각 / 종목 ID를 파라미터로 받은뒤 기간 내에 해당하는 가격 정보를 반환하는 API
        """
        symbol = request.query_params.get('symbol')
        start_time_str = request.query_params.get('start_time')
        end_time_str = request.query_params.get('end_time')
        
        if not symbol or not start_time_str or not end_time_str:
             return Response({
                 "status": "error", 
                 "message": "symbol, start_time, and end_time are required parameters"
             }, status=status.HTTP_400_BAD_REQUEST)
             
        start_time = parse_datetime(start_time_str)
        end_time = parse_datetime(end_time_str)
        
        if not start_time or not end_time:
             return Response({
                 "status": "error", 
                 "message": "Invalid datetime format. Use ISO 8601"
             }, status=status.HTTP_400_BAD_REQUEST)
             
        prices = StockPrice.objects.filter(symbol=symbol, timestamp__range=(start_time, end_time))
        serializer = StockPriceSerializer(prices, many=True)
        
        return Response({
            "status": "success",
            "message": f"Stock prices for {symbol} retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)