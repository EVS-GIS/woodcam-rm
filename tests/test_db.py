import psycopg2

import pytest
from woodcamrm.db import get_db


# def test_get_close_db(app):
#     with app.app_context():
#         db = get_db()
#         assert db is get_db()

#     with pytest.raises(psycopg2.ProgrammingError) as e:
#         cur = db.cursor()
#         db.execute('SELECT 1;')
#         cur.close()
#         db.commit()

#     assert 'closed' in str(e.value)
    
    
def test_init_db_command(runner, monkeypatch):
    class Recorder(object):
        called = False

    def fake_init_db():
        Recorder.called = True

    monkeypatch.setattr('woodcamrm.db.init_db', fake_init_db)
    result = runner.invoke(args=['init-db'])
    assert 'Initialized' in result.output
    assert Recorder.called