import pytest
    
def test_init_db_command(runner, monkeypatch):
    class Recorder(object):
        called = False

    def fake_init_db():
        Recorder.called = True

    monkeypatch.setattr('woodcamrm.db.init_db', fake_init_db)
    result = runner.invoke(args=['init-db -y'])
    assert 'Initialized the database.' in result.output
    assert Recorder.called