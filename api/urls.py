from django.urls import path
from . import controllers

app_name = 'api'

urlpatterns = [
    path('stocks/', controllers.StockAPIView.as_view(), name='stock-list'),
    path('prices/range/', controllers.StockPriceRangeAPIView.as_view(), name='stock-price-range'),
    path('prices/single/', controllers.StockPriceSingleAPIView.as_view(), name='stock-price-single'),
    path('prices/symbol/range/', controllers.StockSymbolPriceRangeAPIView.as_view(), name='stock-symbol-price-range'),
]