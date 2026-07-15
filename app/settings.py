import sys
from os import environ
from uuid import uuid4

from sqlalchemy.pool import NullPool


LOG_LEVEL = environ.get('LOG_LEVEL', 'INFO')

APP_NAME = environ.get('APP_NAME', 'internal-mobility-matching')
APP_ENV = environ.get('APP_ENV', 'local')
APP_HOST = environ.get('APP_HOST', '0.0.0.0')
APP_PORT = int(environ.get('APP_PORT', 4004))

if 'pytest' in sys.modules:
    APP_ENV = 'test'

# Database (warehouse Postgres shared with llm-engine; own schema)
if 'pytest' in sys.modules:
    DATABASE_URL = 'postgresql+asyncpg://postgres:password@localhost:5432/internal_mobility_matching_test_db'
    SYNC_DATABASE_URL = 'postgresql://postgres:password@localhost:5432/internal_mobility_matching_test_db'
    CELERY_DATABASE_BACKEND_URL = 'db+postgresql://postgres:password@localhost:5432/internal_mobility_matching_test_db'
else:
    DATABASE_URL = 'postgresql+asyncpg://postgres:password@host.docker.internal:35432/warehouse'
    SYNC_DATABASE_URL = 'postgresql://postgres:password@host.docker.internal:35432/warehouse'
    CELERY_DATABASE_BACKEND_URL = 'db+postgresql://postgres:password@host.docker.internal:35432/warehouse'

DATABASE_URL = environ.get('DATABASE_URL', DATABASE_URL)
SYNC_DATABASE_URL = environ.get('SYNC_DATABASE_URL', SYNC_DATABASE_URL)
CELERY_DATABASE_BACKEND_URL = environ.get('CELERY_DATABASE_BACKEND_URL', CELERY_DATABASE_BACKEND_URL)
DATABASE_SCHEMA = environ.get('DATABASE_SCHEMA', 'better_sense')

USE_PGBOUNCER = str(environ.get('PGBOUNCER_ENABLED', False)).lower()[0] in ['t', '1']


def get_async_engine_options():
    args = dict(echo=False, future=True, pool_pre_ping=True)
    if 'pytest' in sys.modules:
        args['poolclass'] = NullPool
    if USE_PGBOUNCER:
        args.setdefault("connect_args", {})
        args["connect_args"]["statement_cache_size"] = 0
        args["connect_args"]["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid4()}__"
    return args


# Celery / broker
REDIS_BROKER_ENABLED = str(environ.get('REDIS_BROKER_ENABLED', True)).lower()[0] in ['t', '1']
REDIS_BROKER_URL = environ.get('REDIS_BROKER_URL', 'redis://localhost:6379/0')
CELERY_TASK_DEFAULT_QUEUE = environ.get('CELERY_TASK_DEFAULT_QUEUE', 'local-internal-mobility-matching-celery')
CELERY_RESULT_TABLES = {
    'task': 'internal_mobility_matching_taskmeta',
    'group': 'internal_mobility_matching_groupmeta',
}

# LLM Proxy
OPENAI_API_KEY = environ.get('OPENAI_API_KEY')
LLM_PROXY_URL = environ.get('LLM_PROXY_URL', 'https://rainforest.betterworks.com/services/llm-proxy/v1')
LLM_PROXY_TOKEN = environ.get('LLM_PROXY_TOKEN')
LLM_PROXY_ENABLED = str(environ.get('LLM_PROXY_ENABLED', True)).lower()[0] in ['t', '1']
PRIVATE_LLM_MODEL = environ.get('PRIVATE_LLM_MODEL', 'meta/llama3.1')

# Embedding service (same instance llm-engine uses; embeds the JD query vector)
BW_EMBEDDING_URL = environ.get('BW_EMBEDDING_URL', 'http://localhost:6005')
EMBEDDING_MODEL = environ.get('EMBEDDING_MODEL', 'embeddinggemma-300m')
EMBEDDING_TIMEOUT_SECONDS = int(environ.get('EMBEDDING_TIMEOUT_SECONDS', 120))
