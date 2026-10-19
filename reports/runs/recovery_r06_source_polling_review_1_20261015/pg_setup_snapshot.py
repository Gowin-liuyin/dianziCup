"""Create only the named review database and compare its public schema."""

import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
DATABASE = 'test_dianzi_r06_catalog_polling_20261015'


def main():
    target = make_url(os.environ['TEST_DATABASE_URL'])
    assert target.database == DATABASE
    administration = create_engine(target.set(database='postgres'), isolation_level='AUTOCOMMIT', connect_args={'connect_timeout':5})
    with administration.connect() as connection:
        exists = connection.scalar(text('select 1 from pg_database where datname=:name'), {'name':DATABASE})
        if not exists:
            connection.exec_driver_sql('CREATE DATABASE ' + DATABASE)
    administration.dispose()
    engine = create_engine(target, connect_args={'connect_timeout':5})
    with engine.connect() as connection:
        rows = connection.execute(text("select c.relname,c.relkind,pg_get_userbyid(c.relowner) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' order by c.relname")).all()
        counts = {}
        for name, kind, owner in rows:
            if kind in ('r','p'):
                counts[name] = connection.exec_driver_sql('SELECT count(*) FROM public.' + engine.dialect.identifier_preparer.quote(name)).scalar_one()
        snapshot = {'database':DATABASE, 'relations':[list(row) for row in rows], 'table_counts':counts}
    engine.dispose()
    output = RUN/('public_'+sys.argv[1]+'.json')
    output.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
    if sys.argv[1] == 'after':
        before = json.loads((RUN/'public_before.json').read_text())
        assert before == snapshot, 'review database public schema changed'
    print(json.dumps({'database':DATABASE, 'public_relations':len(rows), 'public_unchanged':sys.argv[1]=='after'}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(type(error).__name__)
        raise SystemExit(1) from None
