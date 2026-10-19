"""UI facts must remain faithful to real schemas; no solvers/models in presenters."""
import copy
from pathlib import Path

import pytest

from energy_agent.agent import EnergyAgent, revise_task
from energy_agent.console.decision_archives import ARCHIVES, load_archive
from energy_agent.console.decision_components import boundary_html, heat_table, _path_card_html
from energy_agent.console.decision_presenters import (
    num, build_regret_vm, build_counterfactual_vm, before_after_rows,
    build_task_summary, build_conversation_vm, derive_stages, router_available)
from energy_agent.conversation import ConversationReply, PendingDialog
from energy_agent.data import make_demo_task
from energy_agent.modifications import compile_contract
from energy_agent.schemas import TaskPatch


@pytest.mark.parametrize('value',[None,True,float('nan'),float('inf'),-float('inf'),'bad'])
def test_missing_and_invalid_numeric_values_never_look_like_results(value):
    assert num(value)=='—'
    assert num(0)=='0.00'


@pytest.mark.parametrize('name',list(ARCHIVES))
def test_actual_archives_typed_readonly_and_dynamic_size(name):
    result,downloads=load_archive(name)
    before=result.model_dump_json()
    if hasattr(result,'analysis'):
        vm=build_regret_vm(result)
        assert vm.status=='certified'
        assert len(vm.cells)==len(result.candidates)*len(result.scenarios)
        assert len(vm.cells) in (6,12)
        assert all(c.kind=='optimal' for c in vm.cells.values())
        html=heat_table(vm,'cost',None)
        assert html.count('scope="col"')==len(result.scenarios)+1
        assert html.count('tabindex="0"')==len(vm.cells)+1
    else:
        vm=build_counterfactual_vm(result)
        assert len(vm.paths)==3 and all(p.verified and p.can_adopt for p in vm.paths)
        assert all(p.boundary.reached for p in vm.paths)
    assert result.model_dump_json()==before
    assert all(Path(p).is_file() for p in downloads.values())


@pytest.mark.parametrize('status',['uncertain','error','budget_exhausted'])
def test_unknown_boundaries_have_neutral_axis_no_implied_feasible_region(status):
    result,_=load_archive('反事实 · 24小时三路径')
    result.paths[0].status=status
    path=build_counterfactual_vm(result).paths[0]
    assert not path.verified and not path.can_adopt
    assert path.boundary.segments==() and not path.boundary.reached
    assert 'seg ok' not in boundary_html(path.boundary)


def test_unverified_endpoint_and_failed_validation_cannot_certify_boundary():
    result,_=load_archive('反事实 · 24小时三路径')
    result.paths[0].trace=[]
    path=build_counterfactual_vm(result).paths[0]
    assert not path.boundary.segments and not path.boundary.reached
    result.paths[0].final_validation.valid=False
    path=build_counterfactual_vm(result).paths[0]
    assert not path.verified and not path.can_adopt


def test_feasible_limit_path_has_warning_not_optimal_colour():
    result,_=load_archive('反事实 · 24小时三路径')
    result.paths[0].solver_status='feasible_limit'
    path=build_counterfactual_vm(result).paths[0]
    assert path.verified and '最优性未证明' in path.caveat
    html=_path_card_html(path)
    assert 'dw-t-warn">可行解 · 未证明最优' in html


@pytest.mark.parametrize('state',['not_run','infeasible','uncertain','rejected','error'])
def test_null_cells_remain_text_not_zero_and_old_certification_removed(state):
    result,_=load_archive('后悔决策 · 合成24小时3×4')
    raw=result.model_dump(mode='json')
    cell=raw['cells'][0];cid,sid=cell['candidate_id'],cell['scenario_id']
    cell.update(feasibility=state,cost_yuan=None,cost_is_optimal=False)
    raw['analysis']['cost_matrix'][cid][sid]=None
    raw['analysis']['regret_matrix'][cid][sid]=None
    vm=build_regret_vm(raw)
    assert vm.cells[cid,sid].cost is None and vm.cells[cid,sid].regret is None
    assert vm.cells[cid,sid].cost_text!='0'
    assert 'dw-x' in heat_table(vm,'cost',(cid,sid))
    if state!='infeasible':
        assert vm.status=='partial' and not vm.recommended_ids


def test_invalid_cost_or_validation_does_not_render_confident_old_numeric_claims():
    result,_=load_archive('后悔决策 · 混合8760小时2×3')
    raw=result.model_dump(mode='json')
    raw['cells'][0]['validation']['valid']=False
    vm=build_regret_vm(raw)
    assert vm.status=='partial' and not vm.recommended_ids
    assert vm.cells['BASE','base'].cost is None
    assert '未通过' in vm.paragraphs[0]
    raw=result.model_dump(mode='json')
    raw['analysis']['cost_matrix']['BASE']['base']=float('nan')
    vm=build_regret_vm(raw)
    assert vm.status=='partial' and 'nan' not in heat_table(vm,'cost',None).lower()


def test_html_labels_are_escaped_and_zero_is_a_real_value():
    result,_=load_archive('后悔决策 · 合成24小时3×4')
    result.scenarios[0].name='<script>alert(1)</script>'
    vm=build_regret_vm(result)
    markup=heat_table(vm,'regret',None)
    assert '<script>' not in markup and '&lt;script&gt;' in markup
    assert vm.cells['C','base'].regret_text=='0'


def test_nonoptimal_or_missing_regret_never_looks_like_certified_zero():
    result,_=load_archive('后悔决策 · 合成24小时3×4')
    raw=result.model_dump(mode='json')
    raw['cells'][0].update(solver_status='feasible_limit',cost_is_optimal=False,mip_gap=.1)
    vm=build_regret_vm(raw)
    assert vm.status=='approximate' and vm.cells['A','base'].cost_text.startswith('≤')
    raw['analysis']['regret_matrix']['A']['base']=None
    vm=build_regret_vm(raw)
    assert vm.cells['A','base'].regret_text=='—'


def test_annual_discount_change_is_labelled_sensitivity_not_investment_savings():
    """Only vary an assumption to test presentation; no new planning result claimed."""
    import gzip
    from energy_agent.schemas import RunResult
    path=Path(__file__).resolve().parents[1]/'docs/v041_evidence/mixed_heat_8760h_PV_base_run.json.gz'
    old=RunResult.model_validate_json(gzip.decompress(path.read_bytes()))
    changed=old.model_copy(deep=True)
    changed.task.economics.discount_rate=.08
    rows=before_after_rows(changed,old)
    assert rows and all('敏感性差值' in row[3] for row in rows if row[1]!='—' and row[2]!='—')


def test_comparability_uses_actual_inputs_even_when_both_short_period(tmp_path):
    original=EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    same=EnergyAgent(tmp_path/'same').run(revise_task(original.task,TaskPatch(budget_yuan=900000)),previous=original)
    assert not any('敏感性' in row[3] for row in before_after_rows(same,original))
    modified=EnergyAgent(tmp_path/'load').run(revise_task(original.task,TaskPatch(electric_demand_scale=1.05)),previous=original)
    rows=before_after_rows(modified,original)
    assert rows and all('敏感性差值' in row[3] for row in rows if row[1]!='—' and row[2]!='—')
    reply=ConversationReply(status='completed',text='实际工具结果',run=modified,request_id='test')
    summary=build_task_summary(reply,modified,original)
    assert '口径C' in summary.basis_text


def test_real_contract_fields_clarification_and_cancel_are_not_fake_progress(tmp_path):
    base=EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    contract=compile_contract('预算少一点，供热不变。',base)
    pending=PendingDialog(request_id='q',original_request='预算少一点，供热不变。',base_run_id=base.run_id,
        input_version=base.input_version,base_file='unused.json',confirmed_conditions={},missing_fields=contract.missing)
    reply=ConversationReply(status='clarification',text='请补充预算幅度',request_id='q',pending=pending,contract=contract)
    assert [s.state for s in derive_stages(reply)]==['clarify','pending','pending','pending','pending']
    assert any(m.kind=='AGENT_CLARIFICATION' for m in build_conversation_vm(reply).messages)
    serialized=reply.model_dump(mode='json')
    assert not any(m.kind=='AGENT_CONFIRMATION' for m in build_conversation_vm(serialized).messages)
    pending.status='cancelled'
    reply.status='cancelled'
    assert all(s.state!='running' for s in derive_stages(reply))
    assert not router_available()
