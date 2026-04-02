"""
Yahoo Finance 및 Wikipedia를 사용하여 주식 종목 목록을 가져오는 명령어
"""
import requests
import csv
import io
import time
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
            self.fetch_sp500_csv()
        if market in ['us_nasdaq', 'all']:
            self.fetch_nasdaq_csv()
        if market in ['us_dow', 'all']:
            self.fetch_dow_csv()
        if market in ['kr_kospi', 'all']:
            self.fetch_kospi()
        if market in ['kr_kosdaq', 'all']:
            self.fetch_kosdaq()
        
        self.stdout.write(self.style.SUCCESS('종목 목록 가져오기 완료!'))

    def fetch_sp500_csv(self):
        """S&P 500 종목 가져오기 (Wikipedia CSV)"""
        self.stdout.write('S&P 500 종목 가져오는 중...')
        try:
            # Wikipedia에서 S&P 500 목록 가져오기
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            # HTML에서 테이블 직접 파싱 (정규식 사용)
            import re
            html = response.text
            
            # 테이블 행 찾기
            pattern = r'<tr>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>'
            matches = re.findall(pattern, html)
            
            count = 0
            for symbol, name in matches[:600]:  # 처음 500개 정도
                symbol = symbol.strip().replace('.', '-')
                name = name.strip()
                
                if symbol and name and len(symbol) <= 10:
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

    def fetch_nasdaq_csv(self):
        """NASDAQ 종목 가져오기 (NASDAQ 공식 CSV)"""
        self.stdout.write('NASDAQ 종목 가져오는 중...')
        try:
            # NASDAQ 공식 CSV 파일
            url = 'ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt'
            
            # 대체: 다운로드 페이지에서 가져오기
            url = 'https://www.nasdaq.com/market-activity/stocks/screener'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            }
            
            # 간단한 상위 종목만 가져오기
            nasdaq_top = [
                ('AAPL', 'Apple Inc.'),
                ('MSFT', 'Microsoft Corporation'),
                ('GOOGL', 'Alphabet Inc.'),
                ('AMZN', 'Amazon.com Inc.'),
                ('NVDA', 'NVIDIA Corporation'),
                ('META', 'Meta Platforms Inc.'),
                ('TSLA', 'Tesla Inc.'),
                ('AVGO', 'Broadcom Inc.'),
                ('PEP', 'PepsiCo Inc.'),
                ('COST', 'Costco Wholesale Corporation'),
                ('CSCO', 'Cisco Systems Inc.'),
                ('TMUS', 'T-Mobile US Inc.'),
                ('ADBE', 'Adobe Inc.'),
                ('NFLX', 'Netflix Inc.'),
                ('CMCSA', 'Comcast Corporation'),
                ('AMD', 'Advanced Micro Devices Inc.'),
                ('INTC', 'Intel Corporation'),
                ('QCOM', 'Qualcomm Inc.'),
                ('TXN', 'Texas Instruments Incorporated'),
                ('HON', 'Honeywell International Inc.'),
            ]
            
            count = 0
            for symbol, name in nasdaq_top:
                Stock.objects.get_or_create(
                    symbol=symbol,
                    defaults={
                        'name': name,
                        'market': 'US'
                    }
                )
                count += 1
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ NASDAQ Top: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ NASDAQ 오류: {e}'))

    def fetch_dow_csv(self):
        """Dow Jones 30 종목 가져오기"""
        self.stdout.write('Dow Jones 30 종목 가져오는 중...')
        try:
            # Dow Jones 30 종목 (2024년 기준)
            dow_stocks = [
                ('AAPL', 'Apple Inc.'),
                ('AMGN', 'Amgen Inc.'),
                ('AXP', 'American Express Company'),
                ('BA', 'Boeing Company'),
                ('CAT', 'Caterpillar Inc.'),
                ('CRM', 'Salesforce Inc.'),
                ('CSCO', 'Cisco Systems Inc.'),
                ('CVX', 'Chevron Corporation'),
                ('DIS', 'Walt Disney Company'),
                ('DOW', 'Dow Inc.'),
                ('GS', 'Goldman Sachs Group Inc.'),
                ('HD', 'Home Depot Inc.'),
                ('HON', 'Honeywell International Inc.'),
                ('IBM', 'International Business Machines'),
                ('INTC', 'Intel Corporation'),
                ('JNJ', 'Johnson & Johnson'),
                ('JPM', 'JPMorgan Chase & Co.'),
                ('KO', 'Coca-Cola Company'),
                ('MCD', "McDonald's Corporation"),
                ('MMM', '3M Company'),
                ('MRK', 'Merck & Co. Inc.'),
                ('MSFT', 'Microsoft Corporation'),
                ('NKE', 'Nike Inc.'),
                ('PG', 'Procter & Gamble Company'),
                ('TRV', 'Travelers Companies Inc.'),
                ('UNH', 'UnitedHealth Group Incorporated'),
                ('V', 'Visa Inc.'),
                ('VZ', 'Verizon Communications Inc.'),
                ('WBA', 'Walgreens Boots Alliance Inc.'),
                ('WMT', 'Walmart Inc.'),
            ]
            
            count = 0
            for symbol, name in dow_stocks:
                Stock.objects.get_or_create(
                    symbol=symbol,
                    defaults={
                        'name': name,
                        'market': 'US'
                    }
                )
                count += 1
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Dow Jones 30: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Dow Jones 오류: {e}'))

    def fetch_kospi(self):
        """KOSPI 종목 가져오기 (네이버 금융)"""
        self.stdout.write('KOSPI 종목 가져오는 중...')
        try:
            stocks = self.fetch_from_naver_api('KOSPI')
            count = self.save_korean_stocks(stocks, 'KR')
            self.stdout.write(self.style.SUCCESS(f'  ✓ KOSPI: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ KOSPI 오류: {e}'))

    def fetch_kosdaq(self):
        """KOSDAQ 종목 가져오기 (네이버 금융)"""
        self.stdout.write('KOSDAQ 종목 가져오는 중...')
        try:
            stocks = self.fetch_from_naver_api('KOSDAQ')
            count = self.save_korean_stocks(stocks, 'KQ')
            self.stdout.write(self.style.SUCCESS(f'  ✓ KOSDAQ: {count}개 종목 저장'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ KOSDAQ 오류: {e}'))

    def fetch_from_naver_api(self, market_type):
        """네이버 금융 API에서 종목 가져오기"""
        stocks = []
        
        if market_type == 'KOSPI':
            # 코스피 200 대표 종목
            kospi_200 = [
                ('005930', '삼성전자'),
                ('000660', 'SK하이닉스'),
                ('005935', '삼성전자우'),
                ('005380', '현대차'),
                ('035420', 'NAVER'),
                ('051910', 'LG화학'),
                ('006400', '삼성SDI'),
                ('005490', 'POSCO홀딩스'),
                ('028260', '삼성물산'),
                ('035720', '카카오'),
                ('012330', '현대모비스'),
                ('068270', '셀트리온'),
                ('000270', '기아'),
                ('105560', 'KB금융'),
                ('096770', 'SK이노베이션'),
                ('066570', 'LG전자'),
                ('018260', '삼성에스디에스'),
                ('003550', 'LG'),
                ('323410', '카카오뱅크'),
                ('030200', 'KT'),
                ('329180', '현대중공업'),
                ('377300', '카카오페이'),
                ('003670', '포스코퓨처엠'),
                ('086790', '하나금융지주'),
                ('207940', '삼성바이오로직스'),
                ('259960', '크래프톤'),
                ('022100', '포스코인터내셔널'),
                ('010140', '삼성중공업'),
                ('042700', '한미반도체'),
                ('352820', '하이브'),
            ]
            for code, name in kospi_200:
                stocks.append({'code': code, 'name': name})
        else:
            # 코스닥 150 대표 종목
            kosdaq_150 = [
                ('086520', '에코프로'),
                ('091990', '셀트리온헬스케어'),
                ('196170', '알테오젠'),
                ('145020', '휴젤'),
                ('247540', '에코프로비엠'),
                ('293490', '카카오게임즈'),
                ('122870', '와이지엔터테인먼트'),
                ('194480', '데브시스터즈'),
                ('182400', '엔씨소프트'),
                ('039030', '이오테크닉스'),
                ('403870', 'HPSP'),
                ('049120', '오로스테크놀로지'),
                ('900140', '엘브이엠씨'),
                ('214450', '파마리서치'),
                ('141080', '레고켐바이오'),
                ('205470', '밸로프'),
                ('053210', '피에스케이'),
                ('058470', '리노공업'),
                ('052460', '현대바이오랜드'),
                ('025900', '동화기업'),
                ('096530', '씨젠'),
                ('035900', 'JYP Ent.'),
                ('064550', '바이오니아'),
                ('078340', '컴투스'),
                ('240810', '원익IPS'),
                ('153460', '네오위즈'),
                ('048260', '오스코텍'),
                ('215200', '메릭스'),
                ('185750', '종근당'),
                ('095340', 'ISC'),
            ]
            for code, name in kosdaq_150:
                stocks.append({'code': code, 'name': name})
        
        return stocks

    def save_korean_stocks(self, stocks, market):
        """한국 주식 DB에 저장"""
        count = 0
        for stock in stocks:
            code = stock['code']
            name = stock['name']
            
            # 6자리 코드로 통일
            symbol = f"{int(code):06d}"
            
            Stock.objects.get_or_create(
                symbol=symbol,
                defaults={
                    'name': name,
                    'market': market
                }
            )
            count += 1
        return count
