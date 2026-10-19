"""Runs unchanged on Linux and Windows CI; genuine fresh Python processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from energy_agent.agent import EnergyAgent
from energy_agent.data import make_demo_task


def test_cross_process_lock_unicode_exports_restart_and_duplicate_answer(tmp_path):
    folder=tmp_path/'中文 空格 会话';folder.mkdir()
    base=EnergyAgent(tmp_path/'基准 文件').run(make_demo_task(hours=6))
    worker=Path(__file__).with_name('v032_process_worker.py')
    env=os.environ.copy();env['PYTHONUTF8']='1'
    def command(action):return [sys.executable,str(worker),action,str(folder),base.files['json']]
    def invoke(action):
        return subprocess.run(command(action),env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
    first=subprocess.Popen(command('hold'),env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
    try:
        deadline=time.monotonic()+30
        while not (folder/'ready').exists():
            if first.poll() is not None:raise AssertionError(first.communicate())
            if time.monotonic()>deadline:raise AssertionError('holder process did not acquire request lock')
            time.sleep(.05)
        duplicate=invoke('submit')
        assert duplicate.returncode==42,duplicate.stderr
        assert (folder/'模拟调用.txt').read_text(encoding='utf-8').splitlines()==['planning_intent']
    finally:
        if first.poll() is None:
            stdout,stderr=first.communicate('\n',timeout=30)
            assert first.returncode==0,stderr
    # The process holding the clarification has exited. A new interpreter
    # restores its durable context, then another performs a genuine solve.
    restored=invoke('restore');assert restored.returncode==0,restored.stderr
    assert json.loads((folder/'restore_reply.json').read_text(encoding='utf-8'))['status']=='clarification'
    answer=invoke('answer');assert answer.returncode==0,answer.stderr
    reply=json.loads((folder/'answer_reply.json').read_text(encoding='utf-8'))
    assert reply['status']=='completed' and reply['heat_unchanged']
    assert reply['budget_yuan']==base.task.constraints.budget_yuan*.85
    run_id=reply['run_id'];count=(folder/'模拟调用.txt').read_text(encoding='utf-8').splitlines()
    for action in ('answer','restore'):
        result=invoke(action);assert result.returncode==0,result.stderr
        cached=json.loads((folder/(action+'_reply.json')).read_text(encoding='utf-8'))
        assert cached['run_id']==run_id
    assert (folder/'模拟调用.txt').read_text(encoding='utf-8').splitlines()==count
    assert len(count)==3
    assert '区域' in Path(reply['files']['markdown']).read_text(encoding='utf-8')
    assert 'candidate_id' in Path(reply['files']['csv']).read_text(encoding='utf-8-sig')
    data=json.loads(Path(reply['files']['json']).read_text(encoding='utf-8'))
    assert data['input_version']==2 and data['previous_run_id']==base.run_id
