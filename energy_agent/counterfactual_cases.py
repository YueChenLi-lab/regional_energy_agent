"""Explicit synthetic research inputs for reproducible repair acceptance."""
from .data import make_demo_task
from .schemas import Candidate


def make_repair_case(hours=24):
    task = make_demo_task(seed=42, hours=hours)
    task.project_name = f'合成反事实修复验收 · {hours}小时 · 非真实工程'
    task.data.electric_load_kw = [10.] * hours
    task.data.heat_load_kw_th = [20.] * hours
    task.candidates = [
        Candidate(candidate_id='A', name='电网＋锅炉', source_id='demo-candidates', pv_kw=0, battery_power_kw=0, battery_energy_kwh=0, hp_kw_th=0, boiler_kw_th=20),
        Candidate(candidate_id='C', name='电网＋热泵', source_id='demo-candidates', pv_kw=0, battery_power_kw=0, battery_energy_kwh=0, hp_kw_th=20, boiler_kw_th=0),
        Candidate(candidate_id='D', name='光伏＋储能＋热泵', source_id='demo-candidates', pv_kw=50, battery_power_kw=20, battery_energy_kwh=150, hp_kw_th=20, boiler_kw_th=0),
    ]
    task.constraints.budget_yuan = 60000
    task.constraints.emission_limit_kg = hours * 230/24
    task.constraints.grid_limit_kw = 12
    task.sources[0].processing.append('反事实验收合成负荷：常规电功率恒10kW，热功率恒20kW_th；原168小时随机日型未拼接或年化；光伏沿用固定种子逐时合成')
    next(s for s in task.sources if s.source_id=='demo-candidates').processing.append('研究假设：三个固定候选A(锅炉20)、C(热泵20)、D(光伏50/储能20kW150kWh/热泵20)；容量不随约束放宽而改变')
    next(s for s in task.sources if s.source_id=='demo-conditions').processing.append('研究假设：预算60000元，购电12kW，排放上限按hours*230/24 kgCO2e；只统计实际输入期')
    return task
