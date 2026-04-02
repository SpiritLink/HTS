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

class Stock(models.Model):
    """
    개별 주식 종목의 기본 정보를 저장하는 모델.
    주식 이름으로 검색할 수 있도록 별도 분리합니다.
    """
    symbol = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    market = models.CharField(max_length=10, db_index=True, default='KR')
    
    def __str__(self):
        return f"[{self.market}] {self.name} ({self.symbol})"

class StockPrice(models.Model):
    """
    주가 정보를 저장하는 모델. 일 단위(Daily) 데이터를 기본으로 하지만,
    시간(시간, 분 등) 단위로 확장 가능하도록 DateTimeField를 사용합니다.
    """
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='prices', null=True, blank=True)

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

class DataFetchRequest(models.Model):
    """
    Yahoo Finance 등 외부 API를 통해 데이터를 가져오기 위한 요청 큐 모델.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    symbol = models.CharField(max_length=20, db_index=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 동일 종목에 대해 동일 기간의 요청이 중복되지 않도록 설정
        unique_together = ('symbol', 'start_date', 'end_date')
        ordering = ['-created_at']

    def __str__(self):
        return f"Request for {self.symbol} from {self.start_date} to {self.end_date} ({self.status})"


class StockTradingCalendar(models.Model):
    """
    각 종목별 거래일 캘린더를 관리하는 모델.
    특정 날짜가 거래일인지, 주말/공휴일인지 구분하여 저장합니다.
    """
    DAY_TYPE_CHOICES = [
        ('TRADING', 'Trading Day'),      # 정상 거래일
        ('WEEKEND', 'Weekend'),           # 주말
        ('HOLIDAY', 'Holiday'),           # 공휴일
        ('NO_DATA', 'No Data Available'), # 거래일이나 데이터 없음 (상장폐지 등)
    ]
    
    symbol = models.CharField(max_length=20, db_index=True)
    market = models.CharField(max_length=10, db_index=True, default='KR')
    date = models.DateField(db_index=True)
    day_type = models.CharField(max_length=20, choices=DAY_TYPE_CHOICES, default='TRADING')
    
    # 해당 날짜의 StockPrice가 있는지 여부 (빠른 조회용)
    has_price_data = models.BooleanField(default=False)
    
    class Meta:
        # 동일 종목, 동일 날짜에 대한 중복 방지
        unique_together = ('symbol', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['symbol', 'day_type']),
            models.Index(fields=['market', 'date']),
        ]

    def __str__(self):
        return f"[{self.symbol}] {self.date} - {self.get_day_type_display()}"

    @classmethod
    def is_trading_day(cls, symbol, date):
        """
        특정 종목의 특정 날짜가 거래일인지 확인합니다.
        """
        try:
            calendar = cls.objects.get(symbol=symbol, date=date)
            return calendar.day_type == 'TRADING' and calendar.has_price_data
        except cls.DoesNotExist:
            # 캘린더 정보가 없으면 주말인지 확인
            if date.weekday() >= 5:  # 토(5), 일(6)
                return False
            return None  # 알 수 없음

    @classmethod
    def mark_day_type(cls, symbol, market, date, day_type, has_price_data=False):
        """
        특정 날짜의 유형을 마킹합니다.
        """
        cls.objects.update_or_create(
            symbol=symbol,
            date=date,
            defaults={
                'market': market,
                'day_type': day_type,
                'has_price_data': has_price_data
            }
        )
