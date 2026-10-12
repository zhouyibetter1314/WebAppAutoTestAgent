from alembic import context
from sqlalchemy import create_engine

from webapp_auto_test_agent.storage import Base

config = context.config
url = config.get_main_option("sqlalchemy.url") or ""
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
