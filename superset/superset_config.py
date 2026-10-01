import os
from sqlalchemy.engine import URL

SECRET_KEY = os.environ['SUPERSET_SECRET_KEY']
SQLALCHEMY_DATABASE_URI = URL.create(
    'postgresql+psycopg2', username='news', password=os.environ['POSTGRES_PASSWORD'],
    host='postgres', database='superset_meta',
).render_as_string(hide_password=False)
SQLALCHEMY_TRACK_MODIFICATIONS = False
WTF_CSRF_ENABLED = True
TALISMAN_ENABLED = False
ENABLE_PROXY_FIX = False
APP_NAME = 'Phân tích tin tức Việt Nam'
CACHE_CONFIG = {'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 60}
DATA_CACHE_CONFIG = {'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 60}
FEATURE_FLAGS = {'DASHBOARD_NATIVE_FILTERS': True}
