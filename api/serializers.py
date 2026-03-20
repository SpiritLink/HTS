from rest_framework import serializers
from hts.models import Stock, StockPrice

class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ['symbol', 'name', 'market']

class StockPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockPrice
        fields = ['symbol', 'market', 'timestamp', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']
