"""
Yahoo Finance 및 Wikipedia를 사용하여 주식 종목 목록을 가져오는 명령어
"""
import requests
import pandas as pd
from django.core.management.base import BaseCommand
from hts.models import Stock


class Command(BaseCommand):
    help = 'Wikipedia에서 S&P 500, NASDAQ 등의 주식 종목 목록을 가져와 DB에 저장합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--market',
            type=str,
            default='all',
            help='가져올 시장 (us_sp500, us_nasdaq, us_dow, kr_kospi, kr_kosdaq, all)'
        )

    def handle(self, *args, **options):
        market = options['market']
        
        if market in ['us_sp500', 'all']:
            self.fetch_sp500()
        if market in ['us_nasdaq', 'all']:
            self.fetch_nasdaq100()
        if market in ['us_dow', 'all']:
            self.fetch_dow_jones()
        if market in ['kr_kospi', 'all']:
            self.fetch_kospi200()
        if market in ['kr_kosdaq', 'all']:
            self.fetch_kosdaq150()
        
        self.stdout.write(self.style.SUCCESS('종목 목록 가져오기 완료!'))

    def fetch_sp500(self):
        """S&P 500 종목 가져오기"""
        self.stdout.write('S&P 500 종목 가져오는 중...')
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            tables = pd.read_html(url)
            df = tables[0]
            
            count = 0
            for _, row in df.iterrows():
                symbol = row['Symbol'].replace('.', '-')
                name = row['Security']
                
                Stock.objects.get_or_create(
                    symbol=symbol,
                    defaults={
                        'name': name,
                        'market': 'US'
                    }
                )
                count += 1
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ S&P 500: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ S&P 500 오류: {e}'))

    def fetch_nasdaq100(self):
        """NASDAQ 100 종목 가져오기"""
        self.stdout.write('NASDAQ 100 종목 가져오는 중...')
        try:
            url = 'https://en.wikipedia.org/wiki/NASDAQ-100'
            tables = pd.read_html(url)
            
            df = None
            for table in tables:
                if 'Ticker' in table.columns or 'Symbol' in table.columns:
                    df = table
                    break
            
            if df is None:
                self.stdout.write(self.style.WARNING('  ! NASDAQ 100 테이블을 찾을 수 없음'))
                return
            
            count = 0
            symbol_col = 'Ticker' if 'Ticker' in df.columns else 'Symbol'
            
            for _, row in df.iterrows():
                symbol = str(row[symbol_col]).replace('.', '-')
                name = str(row.get('Company', row.get('Name', symbol)))
                
                if symbol and symbol != 'nan':
                    Stock.objects.get_or_create(
                        symbol=symbol,
                        defaults={
                            'name': name,
                            'market': 'US'
                        }
                    )
                    count += 1
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ NASDAQ 100: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ NASDAQ 100 오류: {e}'))

    def fetch_dow_jones(self):
        """Dow Jones 30 종목 가져오기"""
        self.stdout.write('Dow Jones 30 종목 가져오는 중...')
        try:
            url = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
            tables = pd.read_html(url)
            
            df = None
            for table in tables:
                if 'Symbol' in table.columns:
                    df = table
                    break
            
            if df is None:
                self.stdout.write(self.style.WARNING('  ! Dow Jones 테이블을 찾을 수 없음'))
                return
            
            count = 0
            for _, row in df.iterrows():
                symbol = str(row['Symbol']).replace('.', '-')
                name = str(row.get('Company', symbol))
                
                if symbol and symbol != 'nan':
                    Stock.objects.get_or_create(
                        symbol=symbol,
                        defaults={
                            'name': name,
                            'market': 'US'
                        }
                    )
                    count += 1
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Dow Jones: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Dow Jones 오류: {e}'))

    def fetch_kospi200(self):
        """KOSPI 200 종목 가져오기 (네이버 금융)"""
        self.stdout.write('KOSPI 200 종목 가져오는 중...')
        try:
            codes = self.fetch_korean_stocks_from_naver('KOSPI')
            count = self.save_korean_stocks(codes, 'KR')
            self.stdout.write(self.style.SUCCESS(f'  ✓ KOSPI: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ KOSPI 오류: {e}'))

    def fetch_kosdaq150(self):
        """KOSDAQ 150 종목 가져오기 (네이버 금융)"""
        self.stdout.write('KOSDAQ 150 종목 가져오는 중...')
        try:
            codes = self.fetch_korean_stocks_from_naver('KOSDAQ')
            count = self.save_korean_stocks(codes, 'KQ')
            self.stdout.write(self.style.SUCCESS(f'  ✓ KOSDAQ: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ KOSDAQ 오류: {e}'))

    def fetch_korean_stocks_from_naver(self, market_type):
        """네이버 금융에서 한국 주식 종목 코드 가져오기"""
        stocks = []
        market_code = '0' if market_type == 'KOSPI' else '10'
        
        for page in range(1, 50):
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
                        if market_type == 'KOSPI':
                            symbol = f"{code:0>6}.KS"
                        else:
                            symbol = f"{code:0>6}.KQ"
                        
                        stocks.append({
                            'symbol': symbol,
                            'name': name,
                            'code': code
                        })
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  페이지 {page} 오류: {e}'))
                break
        
        return stocks

    def save_korean_stocks(self, stocks, market):
        """한국 주식 DB에 저장"""
        count = 0
        for stock in stocks:
            Stock.objects.get_or_create(
                symbol=stock['symbol'],
                defaults={
                    'name': stock['name'],
                    'market': market
                }
            )
            count += 1
        return count
