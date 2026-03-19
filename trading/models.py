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