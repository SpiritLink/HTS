from django.urls import path
from . import controllers

app_name = 'api'

urlpatterns = [
    # 모든 주식 목록을 가져오는 API
    path('stocks/', controllers.StockAPIView.as_view(), name='stock-list'),
    # 특정 기간 동안의 주식 가격 범위를 가져오는 API
    path('prices/range/', controllers.StockPriceRangeAPIView.as_view(), name='stock-price-range'),
    # 단일 주식의 현재 가격을 가져오는 API
    path('prices/single/', controllers.StockPriceSingleAPIView.as_view(), name='stock-price-single'),
    # 특정 심볼에 대한 기간별 주식 가격 범위를 가져오는 API
    path('prices/symbol/range/', controllers.StockSymbolPriceRangeAPIView.as_view(), name='stock-symbol-price-range'),
    # 여러 주식의 가격 정보를 동시에 등록하는 API
    path('prices/bulk-create/', controllers.BulkStockPriceCreateAPIView.as_view(), name='stock-price-bulk-create'),
]