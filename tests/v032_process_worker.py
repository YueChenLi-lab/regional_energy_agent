"""Subprocess fixture: real file locks, saved sessions and local solves, no HTTP."""
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from energy_agent.agent import EnergyAgent
from energy_agent.conversation import AgentSession
from energy_agent.schemas import RunResult


def main():
    action,folder,base_path=sys.argv[1:4];folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    class Model:
        def call_tool(self,name,cls,c,**kwargs):
            with (folder/'模拟调用.txt').open('a',encoding='utf-8') as f:f.write(name+'\n')
            if action=='hold':
                (folder/'ready').write_text('ready',encoding='utf-8')
                sys.stdin.readline()
            if name=='planning_intent':
                contract=c['authorized_contract']
                return cls.model_validate({'operation':'clarify' if contract['missing'] else 'modify','patch':None if contract['missing'] else contract['patch']})
            return cls.model_validate({'run_id':c['run_id'],'conclusion':c['conclusion'],
                'claims':[{'reference':k,'value':v} for k,v in list(c['current_facts'].items())[:5]]})
    session=AgentSession(EnergyAgent(folder/'实际 结果'),Model(),folder/'会话 保存')
    try:
        if action in ('hold','submit'):
            base=RunResult.model_validate_json(Path(base_path).read_text(encoding='utf-8'))
            reply=session.submit('预算少一点，供热不变',base,request_id='同一请求')
        elif action=='answer':reply=session.answer('同一请求','减少15%',turn_id='同一回答')
        elif action=='restore':reply=session.restore('同一请求')
        else:raise ValueError('unknown fixture action')
    except ValueError as exc:
        if '正在处理中' in str(exc):return 42
        raise
    summary={'status':reply.status,'run_id':reply.run.run_id if reply.run else None,
        'budget_yuan':reply.run.task.constraints.budget_yuan if reply.run else None,'heat_unchanged':reply.heat_unchanged,
        'files':reply.run.files if reply.run else {}}
    (folder/(action+'_reply.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0


if __name__=='__main__':sys.exit(main())
