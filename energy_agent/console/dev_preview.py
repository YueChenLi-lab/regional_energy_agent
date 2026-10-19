"""DEV PREVIEW ONLY. Every number here is FICTIONAL. Never imported by competition_app / console.app."""
import os

import streamlit as st

from ..regret_math import analyze_regret
from .components import theme
from .decision_components import chat_stream, decision_theme, pipeline, regret_board, repair_board
from .decision_presenters import build_conversation_vm, derive_stages

_SCEN = [dict(scenario_id='base', name='基准', is_baseline=True, assumption='基准'),
         dict(scenario_id='electric_up', name='购电价格上涨', electricity_price_multiplier=1.2, assumption='虚构假设'),
         dict(scenario_id='gas_up', name='燃气价格上涨', gas_price_multiplier=1.2, assumption='虚构假设'),
         dict(scenario_id='pv_down', name='光伏出力下降', pv_multiplier=.8, assumption='虚构假设')]
_COST = {'A': [9000, 10400, 9900, 9300], 'B': [8200, 9100, 9400, 8900],
         'C': [7400, 8700, 7400, 8100], 'D': [7000, 8900, 7200, 8600]}
_INV = {'A': 15750., 'B': 120000., 'C': 51400., 'D': 401000.}
_CAP = {'A': (0, 0, 0, 0, 20), 'B': (50, 0, 0, 0, 20), 'C': (0, 0, 0, 20, 0), 'D': (50, 20, 150, 20, 0)}


def sample_regret(variant: str) -> dict:
    cells = []
    for cid, row in _COST.items():
        for s, cost in zip(_SCEN, row):
            sid, feas, status, opt = s['scenario_id'], 'feasible', 'optimal', True
            if variant == 'partial' and (cid, sid) == ('D', 'pv_down'):
                feas, status, cost, opt = 'uncertain', 'no_solution_limit', None, False
            if variant == 'partial' and (cid, sid) == ('A', 'electric_up'):
                feas, status, cost, opt = 'infeasible', 'infeasible', None, False
            if variant in ('approximate', 'partial') and (cid, sid) == ('B', 'pv_down'):
                status, opt = 'feasible_limit', False
            cells.append(dict(candidate_id=cid, scenario_id=sid, feasibility=feas, solver_status=status,
                              cost_yuan=cost, cost_is_optimal=opt))
    ana = analyze_regret(cells, list(_COST), [s['scenario_id'] for s in _SCEN], 'base')
    full = [dict(c, investment_yuan=_INV[c['candidate_id']], emissions_kg=None if c['cost_yuan'] is None else 100.0,
                 mip_gap=0.0 if c['cost_is_optimal'] else None, solve_seconds=0.01, run_id='preview',
                 capacities_fixed=True if c['cost_yuan'] is not None else None, reasons=[],
                 validation={'valid': c['cost_yuan'] is not None, 'metrics': {'period_hours': 24}}) for c in cells]
    cands = [dict(candidate=dict(candidate_id=k, name='示例配置 ' + k, pv_kw=v[0], battery_power_kw=v[1],
                                 battery_energy_kwh=v[2], hp_kw_th=v[3], boiler_kw_th=v[4]),
                  capacity_sha256='0' * 64, origin='task') for k, v in _CAP.items()]
    return dict(request_id='dev-preview-' + variant, base_run_id='PREVIEW0', input_version=1, cost_basis='period_energy',
                case_label='DEV PREVIEW · 虚构示例，非计算结果', candidates=cands, scenarios=_SCEN, cells=full,
                analysis=ana, solver_calls=0, elapsed_seconds=0.0, files={},
                explanation='【虚构示例】本段文字仅用于检查排版。\n\n不代表任何真实求解结果。')


def _trial(phase, value, feas, calls=3):
    return dict(phase=phase, value=value, feasibility=feas, solver_statuses={'D': 'optimal'}, solver_calls=calls, run_id='preview00')


def sample_repair() -> dict:
    ok = dict(valid=True, checks=[dict(passed=True)] * 3)
    cap = dict(candidate_id='D', name='示例配置', pv_kw=50, battery_power_kw=20, battery_energy_kwh=150, hp_kw_th=20, boiler_kw_th=0)
    met = dict(investment_yuan=300000., operating_cost_yuan=120., emissions_kg=60., emission_unit='kgCO2e', period_hours=24.)
    p1 = dict(path_id='p1', field='budget_yuan', unit='元', original_value=60000., status='verified_repair',
              search_range=dict(lower=60000., upper=600000., precision=1000.), suggested_value=300500., adjustment=240500.,
              known_infeasible_lower=299800., known_feasible_upper=300500., boundary_precision_reached=True, boundary_kind='bracket',
              candidate=cap, metrics=met, solver_status='optimal', mip_gap=0.0, solve_seconds=0.02, final_validation=ok,
              note='【虚构】在声明范围内找到可行边界。', run_id='preview01',
              trace=[_trial('expand', 195000., 'infeasible'), _trial('expand', 330000., 'feasible'), _trial('bisect', 299800., 'infeasible')])
    p2 = dict(p1, path_id='p2', field='emission_limit_kg', unit='kgCO2e', original_value=230.,
              search_range=dict(lower=230., upper=300., precision=.05), suggested_value=240., adjustment=10.,
              known_infeasible_lower=None, known_feasible_upper=240., boundary_precision_reached=False, boundary_kind='not_established',
              solver_status='feasible_limit', mip_gap=.01, note='【虚构】只有可行点，没有已确认不可行下界：不画边界。',
              trace=[_trial('expand', 247., 'feasible')])
    p3 = dict(path_id='p3', field='grid_limit_kw', unit='kW', original_value=12., status='uncertain',
              search_range=dict(lower=12., upper=25., precision=.01), suggested_value=None, boundary_kind='not_established',
              note='【虚构】出现不确定状态，停止推断；不是不可行证明。', trace=[_trial('expand', 15., 'uncertain')])
    return dict(status='partial', baseline_verification=dict(feasibility='infeasible', reasons=['【虚构】示例原因']),
                solver_calls=0, elapsed_seconds=0.0, limits=dict(single_solve_seconds=3., max_solver_calls=48, total_seconds=30.),
                locked_conditions=['electric_load', 'heat_load', 'period', 'service'], paths=[p1, p2, p3], note='DEV PREVIEW',
                monotonicity='', request_id='dev-preview', base_run_id='PREVIEW0', input_version=1)


def sample_reply() -> dict:
    return dict(status='clarification', text='【虚构】尚未修改或求解。请问减少多少？', request_id='dev', run=None, contract=None,
                explanation_verified=False,
                pending=dict(original_request='预算少一点，供热不变。', answers=[], base_run_id='PREVIEW0', input_version=1,
                             status='awaiting_answer', confirmed_conditions={},
                             missing_fields=[dict(field='budget', question='预算减少多少？')]))


def main() -> None:
    st.set_page_config(page_title='DEV PREVIEW', layout='wide')
    theme(); decision_theme()
    if os.getenv('ENERGY_AGENT_DEV_PREVIEW') != '1':
        st.error('开发预览已禁用。设置 ENERGY_AGENT_DEV_PREVIEW=1 后再运行；该页面不是正式比赛页面。')
        return
    st.html('<div class="dw-devbanner">DEV PREVIEW · 全部数值均为虚构样例，不是求解结果，禁止用于比赛展示</div>')
    variant = st.radio('最小后悔样例', ['certified', 'approximate', 'partial'], horizontal=True)
    regret_board(sample_regret(variant))
    st.subheader('反事实修复样例')
    repair_board(sample_repair())
    st.subheader('对话样例')
    reply = sample_reply()
    pipeline(derive_stages(reply))
    chat_stream(build_conversation_vm(reply, None))
