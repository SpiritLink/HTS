from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Django가 기본적으로 아이디, 비밀번호(암호화 포함), 이메일 등을 관리해 줍니다.
    # 여기에 주식 거래에 필요한 '투자금' 필드만 추가합니다.
    balance = models.FloatField(default=10000000.0)

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    stock_symbol = models.CharField(max_length=20, db_index=True)
    order_type = models.CharField(max_length=10) # "BUY" 또는 "SELL"
    quantity = models.IntegerField()
    price = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

class StockPrice(models.Model):
    """
    주가 정보를 저장하는 모델. 일 단위(Daily) 데이터를 기본으로 하지만,
    시간(시간, 분 등) 단위로 확장 가능하도록 DateTimeField를 사용합니다.
    """
    # 주식 코드 (예: 'AAPL' - 미국, '005930' - 한국)
    symbol = models.CharField(max_length=20, db_index=True)
    
    # 국가 코드 또는 시장 정보 (예: 'US', 'KR', 'JP')
    market = models.CharField(max_length=10, db_index=True, default='KR')
    
    # 주가 데이터의 기준 일시
    timestamp = models.DateTimeField(db_index=True)
    
    # 시가, 고가, 저가, 종가 (OHLC)
    open_price = models.FloatField(null=True, blank=True)
    high_price = models.FloatField(null=True, blank=True)
    low_price = models.FloatField(null=True, blank=True)
    close_price = models.FloatField()
    
    # 거래량
    volume = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        # 동일 주식, 동일 시간에 대한 중복 데이터 방지
        unique_together = ('symbol', 'market', 'timestamp')
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.market}] {self.symbol} - {self.timestamp}: {self.close_price}"
