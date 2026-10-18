"""Explicit end-of-year cash flows; physical operating emissions are undiscounted."""
import numpy as np

from .planning import investment_yuan
from .schemas import CAPACITY_FIELDS, CashFlow, EconomicResult

COST_FIELDS = ("pv_cost_per_kw", "battery_power_cost_per_kw", "battery_cost_per_kwh",
               "hp_cost_per_kw_th", "boiler_cost_per_kw_th")


def annuity_factor(economics):
    return sum((1 + economics.discount_rate) ** -year for year in range(1, economics.horizon_years + 1))


def unit_investments(devices):
    return np.array([getattr(devices, key) * (1 + devices.installation_fraction) for key in COST_FIELDS])


def asset_flows(initial, asset, horizon):
    """Replace at L,2L,... strictly before H; remaining life credit at H.

    Replacement fraction applies to subsequent installed assets; original asset
    salvage uses original cost. No replacement is bought at the final instant.
    """
    replacements = {y: initial * asset.replacement_fraction for y in range(asset.lifetime_years, horizon, asset.lifetime_years)}
    last = max(replacements, default=0)
    installed_cost = replacements[last] if last else initial
    remaining = max(0, asset.lifetime_years - (horizon - last)) / asset.lifetime_years
    residual = installed_cost * remaining if asset.residual_method == "straight_line" else 0.0
    return replacements, residual


def capacity_npv_coefficients(devices, economics):
    result = []
    for name, initial in zip(CAPACITY_FIELDS, unit_investments(devices)):
        asset = economics.assets[name]
        replacements, residual = asset_flows(initial, asset, economics.horizon_years)
        value = initial + initial * asset.fixed_om_fraction * annuity_factor(economics)
        value += sum(cost / (1 + economics.discount_rate) ** year for year, cost in replacements.items())
        value -= residual / (1 + economics.discount_rate) ** economics.horizon_years
        result.append(value)
    return np.array(result)


def evaluate_economics(task, candidate, dispatch, metrics):
    e = task.economics
    if e is None:
        return None
    # Caller validates a complete year before invoking representative-year economics.
    capacities = np.array([getattr(candidate, k) for k in CAPACITY_FIELDS])
    initial_by_asset = capacities * unit_investments(task.devices)
    fixed = sum(cost * e.assets[name].fixed_om_fraction for name, cost in zip(CAPACITY_FIELDS, initial_by_asset))
    dt = task.data.step_hours
    variable = dt * sum(p.discharge_kw * e.battery_variable_om_per_kwh
        + p.hp_heat_kw_th * e.hp_variable_om_per_kwh_th
        + p.boiler_heat_kw_th * e.boiler_variable_om_per_kwh_th for p in dispatch.points)
    replacements = {}; residual = 0
    for name, cost in zip(CAPACITY_FIELDS, initial_by_asset):
        schedule, credit = asset_flows(cost, e.assets[name], e.horizon_years)
        for year, amount in schedule.items():
            replacements[year] = replacements.get(year, 0) + amount
        residual += credit
    initial = investment_yuan(candidate, task.devices)
    flows = [CashFlow(year=0, investment_yuan=initial, net_yuan=initial, discounted_yuan=initial)]
    for year in range(1, e.horizon_years + 1):
        credit = residual if year == e.horizon_years else 0
        replacement = replacements.get(year, 0)
        net = metrics.operating_cost_yuan + fixed + variable + replacement - credit
        flows.append(CashFlow(year=year, energy_yuan=metrics.operating_cost_yuan, fixed_om_yuan=fixed,
            variable_om_yuan=variable, replacement_yuan=replacement, residual_credit_yuan=credit,
            net_yuan=net, discounted_yuan=net / (1 + e.discount_rate) ** year))
    return EconomicResult(npv_cost_yuan=sum(f.discounted_yuan for f in flows), annual_energy_cost_yuan=metrics.operating_cost_yuan,
        annual_fixed_om_yuan=fixed, annual_variable_om_yuan=variable, annual_emissions_kg=metrics.emissions_kg,
        horizon_operating_emissions_kg=metrics.emissions_kg * e.horizon_years, cashflows=flows,
        assumption=e.representative_year_assumption + "；年末付费，更换发生在寿命结束年末，期末线性剩余寿命残值；电网接入费不更换且无残值；运行排放不折现；未计设备隐含排放")
