"""Streamlit functional check; constructing/refreshing the UI never calls a model."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_annual_ui_load_preview_and_model_does_not_autocall(monkeypatch,tmp_path):
    import httpx
    def forbidden(*args,**kwargs):raise AssertionError('no model/data network on page refresh')
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    app=AppTest.from_file(str(Path('app.py').resolve()),default_timeout=30).run()
    app.radio(key='workflow').set_value('全年规划与Agent').run()
    assert not app.exception
    assert app.button[0].disabled
    app.checkbox(key='annual_ack').check().run()
    next(b for b in app.button if b.label=='加载许可全年离线案例').click().run()
    assert not app.exception
    assert len(app.session_state['annual_task'].data.timestamps)==8760
    assert any('成本—排放' in b.label for b in app.button)
