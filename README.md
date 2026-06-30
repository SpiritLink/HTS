# HTS (Home Trading System)

## 프로젝트 소개

Python Django 프레임워크를 기반으로 구축된 홈 트레이딩 시스템(HTS)입니다. 이 프로젝트는 주식 데이터 수집, 분석 및 API 제공을 목표로 합니다. Celery를 사용하여 주기적인 작업을 처리하고, Django Rest Framework를 통해 외부 애플리케이션에 데이터를 제공합니다.

## 주요 기능

*   **주식 데이터 수집:** `yfinance`, `finance-datareader` 등의 라이브러리를 사용하여 주식 데이터를 수집합니다.
*   **데이터 관리:** 수집된 데이터는 PostgreSQL 데이터베이스에 저장하고 관리합니다.
*   **비동기 작업 처리:** Celery와 Redis를 사용하여 데이터 수집과 같은 시간이 많이 소요되는 작업을 비동기적으로 처리합니다.
*   **REST API 제공:** Django Rest Framework를 사용하여 분석된 데이터를 외부로 제공하는 API를 구축합니다.

## 기술 스택

*   **언어:** Python
*   **프레임워크:** Django, Django Rest Framework
*   **데이터베이스:** PostgreSQL
*   **비동기 작업:** Celery, Redis
*   **데이터 분석:** pandas
*   **데이터 수집:** yfinance, finance-datareader, lxml

## 프로젝트 구조

```
HTS/
├── api/              # REST API 관련 Django 앱
├── hts/              # 핵심 비즈니스 로직 관련 Django 앱
├── config/           # Django 프로젝트 설정
├── manage.py         # Django 관리 스크립트
├── requirements.txt  # Python 의존성 목록
└── README.md         # 프로젝트 소개 파일
```

## 설치 및 실행 방법

### 1. 소스 코드 클론

```bash
git clone <저장소_URL>
cd HTS
```

### 2. 가상 환경 생성 및 활성화

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 데이터베이스 설정

`config/settings.py` 파일에서 데이터베이스 설정을 환경에 맞게 수정해야 합니다.

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 5. 데이터베이스 마이그레이션

```bash
python manage.py migrate
```

### 6. 개발 서버 실행

```bash
python manage.py runserver
```

### 7. Celery 실행 (별도의 터미널에서 실행)

**Celery Worker 실행:**

```bash
celery -A config worker -l info
```

**Celery Beat 실행 (주기적 작업 스케줄러):**

```bash
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```
