# 两项决策扩展 · 实际合成演示验收

24小时、固定随机种子42。全部负荷为合成数据，设备、价格、排放因子和约束为演示假设；非真实工程，不调用模型。两个案例基准独立，不是将修复结果自动采用后再分析。

## 反事实三路径

基准run_id=93ecbb892f3f40ec94ab01a8e8c83136；v1；复核=infeasible。搜索调用102次、耗时0.667秒；基准另外调用3次。

固定常规电负荷10kW、热负荷20kW_th；预算60000元、排放230kgCO2e、购电12kW。每次只修改一个允许上限，其余负荷、供热、时段、设备、候选和服务保持。

- budget_yuan：60000 → 401191.40625 元；调整341191.40625；边界精度1000.0，达到=True；状态optimal，gap=0.0；独立校验=True；run_id=7732f271842747c3bb347feac0b957cd。 投资/购能费/运行排放等指标：{"investment_yuan": 400999.99999999994, "operating_cost_yuan": 67.79668307060774, "emissions_kg": 60.506869110090804, "grid_kwh": 110.0124892910742, "gas_kwh_lhv": 0.0, "curtailed_pv_kwh": 13.643055750247058, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

- emission_limit_kg：230 → 239.7412109375 kgCO2e；调整9.7412109375；边界精度0.05，达到=True；状态optimal，gap=0.0；独立校验=True；run_id=5f73cbba7a2845d38fb3a7a3093ca951。 投资/购能费/运行排放等指标：{"investment_yuan": 15750.0, "operating_cost_yuan": 341.16666666666663, "emissions_kg": 239.73333333333335, "grid_kwh": 240.0, "gas_kwh_lhv": 533.3333333333333, "curtailed_pv_kwh": 0.0, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

- grid_limit_kw：12 → 16.2529296875 kW；调整4.2529296875；边界精度0.01，达到=True；状态optimal，gap=0.0；独立校验=True；run_id=4317dec289c94b89b1d8818a3078dd12。 投资/购能费/运行排放等指标：{"investment_yuan": 51400.0, "operating_cost_yuan": 277.0625, "emissions_kg": 214.5, "grid_kwh": 390.0, "gas_kwh_lhv": 0.0, "curtailed_pv_kwh": 0.0, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

不同路径属于替代决策，不是必须一起修改；不证明唯一不可行原因。结果未自动采用。基准不可行，不能伪造基准费用或排放差值。

## 多情景最小最大后悔

基准run_id=fc1f95100d874cab890d956d5758a3ad；v1；状态certified；12次矩阵调用、0.152秒；基准另外调用3次；12/12单元独立校验通过。

固定A/B/C容量，只让逐时运行适应四个情景：基准、购电价×1.2、燃气价×1.2、光伏出力×0.8。负荷、供热、时段、预算及约束保持。仅比较该24小时购能费，投资另列；无NPV、不年化、不与全部投资混称生命周期费用。

成本矩阵（元）：{"A": {"base": 1845.381528336603, "electric_up": 2094.383810073651, "gas_up": 1965.4555522668757, "pv_down": 1845.381528336603}, "B": {"base": 1319.9093341493235, "electric_up": 1463.8171770489157, "gas_up": 1439.983358079596, "pv_down": 1414.5931822233913}, "C": {"base": 1060.7301966794612, "electric_up": 1253.690411908401, "gas_up": 1061.7606852789559, "pv_down": 1168.4272832077643}}

后悔矩阵（元）：{"A": {"base": 784.6513316571418, "electric_up": 840.6933981652501, "gas_up": 903.6948669879198, "pv_down": 676.9542451288387}, "B": {"base": 259.1791374698623, "electric_up": 210.12676514051464, "gas_up": 378.2226728006401, "pv_down": 246.16589901562702}, "C": {"base": 0.0, "electric_up": 0.0, "gas_up": 0.0, "pv_down": 0.0}}

最坏后悔（元）：{"A": 903.6948669879198, "B": 378.2226728006401, "C": 0.0}

当前有限矩阵推荐：["C"]。不是连续容量空间的全局稳健最优，也不是未来预测。

## 证据与复现

普通测试、加载数据和页面刷新不调用模型或求解器。完整JSON含来源、版本、输入指纹、求解状态、gap及独立校验。资源限制是现有求解适配器的协作式预算，不是进程级硬终止；未知结果不会展示成已确认不可行。
