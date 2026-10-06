from alembic import context

from nsapp.db import engine
from nsapp.schema import metadata
from nsapp.settings import ensure_dirs

ensure_dirs()
with engine.connect() as connection:
    connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    connection.commit()
    context.configure(connection=connection, target_metadata=metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
