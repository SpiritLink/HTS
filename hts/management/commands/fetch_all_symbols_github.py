"""
GitHub에 공개된 주식 종목 리스트를 가져오는 명령어
"""
import requests
import csv
import io
from django.core.management.base import BaseCommand
from hts.models import Stock


class Command(BaseCommand):
    help = 'GitHub의 공개 데이터에서 전체 주식 종목을 가져옵니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default='all',
            help='데이터 소스 (nasdaq, nyse, amex, krx, all)'
        )

    def handle(self, *args, **options):
        source = options['source']
        
        if source in ['nasdaq', 'all']:
            self.fetch_from_nasdaq_trader()
        if source in ['krx', 'all']:
            self.fetch_krx_all_stocks()
        
        self.stdout.write(self.style.SUCCESS('완료!'))

    def fetch_from_nasdaq_trader(self):
        """NASDAQ Trader에서 전체 종목 가져오기"""
        self.stdout.write('NASDAQ Trader에서 종목 가져오는 중...')
        try:
            # NASDAQ 전체 종목
            url = 'https://www.nasdaq.com/market-activity/stocks/screener?exchange=NASDAQ&render=download'
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                csv_data = io.StringIO(response.text)
                reader = csv.DictReader(csv_data)
                
                count = 0
                for row in reader:
                    symbol = row.get('Symbol', '').strip()
                    name = row.get('Name', '').strip()
                    
                    if symbol and name:
                        Stock.objects.get_or_create(
                            symbol=symbol,
                            defaults={
                                'name': name,
                                'market': 'US'
                            }
                        )
                        count += 1
                
                self.stdout.write(self.style.SUCCESS(f'  ✓ NASDAQ: {count}개 종목'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ 오류: {e}'))

    def fetch_krx_all_stocks(self):
        """한국거래소 전체 종목 가져오기"""
        self.stdout.write('한국거래소 종목 가져오는 중...')
        try:
            # 토큰 받기
            auth_url = 'http://data.krx.co.kr/comm/bldAttendant/getJsonToken.cmd'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # 전체 종목 조회
            url = 'http://data.krx.co.kr/comm/bldAttendant/getJsonToken.cmd'
            
            # 대체: 네이버 금융에서 전체 종목 가져오기
            self.fetch_krx_from_naver()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ 오류: {e}'))

    def fetch_krx_from_naver(self):
        """네이버 금융에서 전체 종목 가져오기"""
        # 코스피 전체
        kospi_count = self.fetch_all_korean_stocks('0', 'KR')
        # 코스닥 전체  
        kosdaq_count = self.fetch_all_korean_stocks('10', 'KQ')
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ KOSPI: {kospi_count}개'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ KOSDAQ: {kosdaq_count}개'))

    def fetch_all_korean_stocks(self, market_code, market):
        """네이버 금융 API에서 모든 종목 가져오기"""
        count = 0
        
        for page in range(1, 100):  # 최대 5000개
            url = f'https://m.stock.naver.com/api/stocks/marketValue/{market_code}?page={page}&pageSize=50'
            
            try:
                response = requests.get(url, timeout=10)
                data = response.json()
                
                if 'stocks' not in data or len(data['stocks']) == 0:
                    break
                
                for stock in data['stocks']:
                    code = stock.get('stockCode', '')
                    name = stock.get('stockName', '')
                    
                    if code and name:
                        symbol = f"{code:0>6}.KS" if market == 'KR' else f"{code:0>6}.KQ"
                        
                        Stock.objects.get_or_create(
                            symbol=symbol,
                            defaults={
                                'name': name,
                                'market': market
                            }
                        )
                        count += 1
                        
            except Exception as e:
                break
        
        return count
