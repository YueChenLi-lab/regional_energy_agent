# 反事实修复离线验收

6/24/168小时为固定种子的合成研究案例；如包含8760小时案例，则为上海Q实测与仿真供热、NASA估算资源及人为参数的混合研究情景。

基准不可行时没有可比较的基准运行费用或排放结果；表中费用与排放仅来自各自已求解修复方案。不同路径是替代决策，不是联合修改要求。

## three_paths_24h · 24小时

基准：infeasible；run_id：a205baf811c94edda23a41c6b7efc097；求解适配器调用102；耗时0.641秒。

- budget_yuan：60000.0 → 401191.40625 元；调整341191.40625；状态verified_repair；边界精度达到True；求解optimal，gap=0.0；指标{'investment_yuan': 400999.99999999994, 'operating_cost_yuan': 67.79668307060774, 'emissions_kg': 60.506869110090804, 'grid_kwh': 110.0124892910742, 'gas_kwh_lhv': 0.0, 'curtailed_pv_kwh': 13.643055750247058, 'electric_load_kwh': 240.0, 'heat_load_kwh_th': 480.0, 'supply_satisfied': True, 'period_hours': 24.0, 'emission_unit': 'kgCO2e'}；NPV=None；run_id=41f6eebb103040ceb42adf5d4036fb8f。

- emission_limit_kg：230.0 → 239.7412109375 kgCO2e；调整9.7412109375；状态verified_repair；边界精度达到True；求解optimal，gap=0.0；指标{'investment_yuan': 15750.0, 'operating_cost_yuan': 341.16666666666663, 'emissions_kg': 239.73333333333335, 'grid_kwh': 240.0, 'gas_kwh_lhv': 533.3333333333333, 'curtailed_pv_kwh': 0.0, 'electric_load_kwh': 240.0, 'heat_load_kwh_th': 480.0, 'supply_satisfied': True, 'period_hours': 24.0, 'emission_unit': 'kgCO2e'}；NPV=None；run_id=ef514b4bc4304e198492b869030b45f4。

- grid_limit_kw：12.0 → 16.2529296875 kW；调整4.2529296875；状态verified_repair；边界精度达到True；求解optimal，gap=0.0；指标{'investment_yuan': 51400.0, 'operating_cost_yuan': 277.0625, 'emissions_kg': 214.5, 'grid_kwh': 390.0, 'gas_kwh_lhv': 0.0, 'curtailed_pv_kwh': 0.0, 'electric_load_kwh': 240.0, 'heat_load_kwh_th': 480.0, 'supply_satisfied': True, 'period_hours': 24.0, 'emission_unit': 'kgCO2e'}；NPV=None；run_id=b8df5a9878bc46db9ff2f2ef2ab507fc。

## budget_6h · 6小时

基准：infeasible；run_id：63ed208b3f074f05bacc5757391aaa04；求解适配器调用14；耗时0.149秒。

- budget_yuan：0.0 → 15753.173828125 元；调整15753.173828125；状态verified_repair；边界精度达到True；求解optimal，gap=0.0；指标{'investment_yuan': 15750.0, 'operating_cost_yuan': 65.46666666666667, 'emissions_kg': 59.93333333333333, 'grid_kwh': 60.0, 'gas_kwh_lhv': 133.33333333333334, 'curtailed_pv_kwh': 0.0, 'electric_load_kwh': 60.0, 'heat_load_kwh_th': 120.0, 'supply_satisfied': True, 'period_hours': 6.0, 'emission_unit': 'kgCO2e'}；NPV=None；run_id=658f5a07d1e84abd88d7dfd4d1e89ca0。

## emissions_168h · 168小时

基准：infeasible；run_id：a705177e4f7b4b4d935b3a99dc0773b9；求解适配器调用18；耗时0.423秒。

- emission_limit_kg：0.0 → 1678.16162109375 kgCO2e；调整1678.16162109375；状态verified_repair；边界精度达到True；求解optimal，gap=0.0；指标{'investment_yuan': 15750.0, 'operating_cost_yuan': 2388.1666666666665, 'emissions_kg': 1678.1333333333337, 'grid_kwh': 1680.0, 'gas_kwh_lhv': 3733.333333333334, 'curtailed_pv_kwh': 0.0, 'electric_load_kwh': 1680.0, 'heat_load_kwh_th': 3360.0, 'supply_satisfied': True, 'period_hours': 168.0, 'emission_unit': 'kgCO2e'}；NPV=None；run_id=98259dcf8af34cec9e3b1fe275ef9d0f。

## multiple_conflicts_6h · 6小时

基准：infeasible；run_id：e8c99d42446a4cc698b0a20f43e00e30；求解适配器调用7；耗时0.048秒。

- budget_yuan：0.0 → None 元；调整None；状态not_found；边界精度达到False；求解None，gap=None；指标None；NPV=None；run_id=None。

- grid_limit_kw：0.0 → None kW；调整None；状态not_found；边界精度达到False；求解None，gap=None；指标None；NPV=None；run_id=None。

## annual_heat_8760h · 8760小时

基准：infeasible；run_id：48626cad2189408a87b27916c486acfd；求解适配器调用6；耗时65.767秒。

- budget_yuan：0.0 → 187500.0 元；调整187500.0；状态verified_repair；边界精度达到True；求解optimal，gap=0.0；指标{'investment_yuan': 187500.0, 'operating_cost_yuan': 3125408.8089905316, 'emissions_kg': 2276323.563647615, 'grid_kwh': 3960399.7733350564, 'gas_kwh_lhv': 485661.82333333325, 'curtailed_pv_kwh': 0.0, 'electric_load_kwh': 3961671.29, 'heat_load_kwh_th': 437095.64099999995, 'supply_satisfied': True, 'period_hours': 8760.0, 'emission_unit': 'kgCO2e'}；NPV=39188087.89337306；run_id=5f49d1d9be3040ec9ce17450818f265b。
