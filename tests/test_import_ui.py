"""UI tests use explicitly labelled artificial CSV; never request real networks."""
from pathlib import Path

import httpx
import pandas as pd
from streamlit.testing.v1 import AppTest

from energy_agent.adapters import RAW_ROOT, RECORD_FILES, fetch_cached


def test_import_preview_requires_acknowledgement_and_budget_recomputes(tmp_path,monkeypatch):
    cache=tmp_path/'cache'
    times=pd.date_range('2017-01-01',periods=24,freq='h')
    raw=pd.DataFrame([{'Time':str(t),'Type':m,'Record':v} for t in times for m,v in [('Q',20),('W',10)]])
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw.to_csv(index=False).encode() if str(r.url).endswith('.csv') else b'ARTIFICIAL documentation fixture')))
    fetch_cached(RAW_ROOT+RECORD_FILES['test'],cache,offline=False,client=client)
    fetch_cached(RAW_ROOT+'dataset/README.md',cache,offline=False,client=client)
    monkeypatch.setenv('ENERGY_AGENT_DATA_CACHE',str(cache))
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path/'outputs'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=120).run()
    app.radio(key='workflow').set_value('外部数据导入（电侧）').run()
    app.selectbox(key='real_provider').set_value('github').run()
    assert not app.exception
    app.selectbox(key='real_kind').set_value('人工格式测试样本（非实测）')
    app.selectbox(key='real_meters').set_value('Q,W')
    app.checkbox(key='real_boundary_ack').check()
    app.selectbox(key='real_anchor').set_value('假设区间起点')
    app.checkbox(key='real_time_ack').check()
    app.number_input(key='real_hours').set_value(24)
    app.button(key='real_preview').click().run()
    assert not app.exception
    assert app.button(key='real_evaluate').disabled
    assert any('不建模供热' in w.value for w in app.warning)
    app.checkbox(key='real_assumptions_ack').check().run()
    assert not app.button(key='real_evaluate').disabled
    app.button(key='real_evaluate').click().run()
    assert not app.exception
    first=app.session_state['real_run']
    assert first.comparison.recommended_id=='GB'
    assert first.task.data.heat_load_kw_th==[0]*24
    assert first.task.sources[0].category=='synthetic'
    assert Path(first.task.case_context.import_files['normalized_csv']).is_file()
    assert len(app.get('download_button'))>=7
    app.number_input(key='real_budget').set_value(0.0)
    app.button(key='real_evaluate').click().run()
    assert not app.exception
    second=app.session_state['real_run']
    assert second.input_version==first.input_version+1
    assert second.comparison.recommended_id=='G'
    assert second.run_id!=first.run_id
    assert second.scenarios[1].dispatch.status=='rejected'
