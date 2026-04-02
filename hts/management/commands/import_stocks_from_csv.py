"""
CSV 파일에서 주식 종목을 import하는 명령어
"""
import csv
from django.core.management.base import BaseCommand
from hts.models import Stock


class Command(BaseCommand):
    help = 'CSV 파일에서 주식 종목을 import합니다.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='CSV 파일 경로')
        parser.add_argument(
            '--market',
            type=str,
            default='KR',
            help='시장 코드 (KR, KQ, US 등)'
        )
        parser.add_argument(
            '--symbol-col',
            type=str,
            default='종목코드',
            help='종목코드 컬럼명'
        )
        parser.add_argument(
            '--name-col',
            type=str,
            default='종목명',
            help='종목명 컬럼명'
        )
        parser.add_argument(
            '--encoding',
            type=str,
            default='euc-kr',
            help='CSV 파일 인코딩 (euc-kr, utf-8 등)'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        market = options['market']
        symbol_col = options['symbol_col']
        name_col = options['name_col']
        encoding = options['encoding']

        self.stdout.write(f'CSV 파일 읽는 중: {csv_file}')
        
        try:
            with open(csv_file, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                
                count = 0
                for row in reader:
                    try:
                        code = row[symbol_col].strip()
                        name = row[name_col].strip()
                        
                        # 숫자 코드인 경우 6자리로 패딩
                        if code.isdigit():
                            code = f"{int(code):06d}"
                        
                        Stock.objects.get_or_create(
                            symbol=code,
                            defaults={
                                'name': name,
                                'market': market
                            }
                        )
                        count += 1
                        
                        if count % 100 == 0:
                            self.stdout.write(f'  {count}개 처리 중...')
                            
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'  행 스킵: {e}'))
                        continue
            
            self.stdout.write(self.style.SUCCESS(f'\n총 {count}개 종목 import 완료!'))
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'파일을 찾을 수 없습니다: {csv_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'오류 발생: {e}'))
