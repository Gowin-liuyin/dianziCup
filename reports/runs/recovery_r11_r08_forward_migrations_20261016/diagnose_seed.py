"""Read the safe PostgreSQL diagnostic for the synthetic retained-data seed."""

from prepare_pg import seed_0016
from run_checks import approved_test_url
from sqlalchemy import create_engine

engine = create_engine(
    approved_test_url().set(
        database="test_dianzi_r11_r08_forward_migrations_20261016_retained_recheck1"
    ),
    hide_parameters=True,
)
with engine.connect() as connection:
    from sqlalchemy import text

    print(
        connection.execute(
            text("SELECT current_database(), current_schema(), current_setting('search_path')")
        ).one()
    )
    print(
        connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='document_revisions' "
                "ORDER BY ordinal_position"
            )
        ).all()
    )
    connection.rollback()
    transaction = connection.begin()
    try:
        seed_0016(connection)
    except Exception as failure:
        print(type(failure).__name__)
        print(getattr(getattr(failure.orig, "diag", None), "message_primary", None))
    finally:
        transaction.rollback()
engine.dispose()
