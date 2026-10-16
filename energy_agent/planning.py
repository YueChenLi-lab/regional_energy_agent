"""Finite, explicitly configured candidates; no global capacity optimum claim."""
from .schemas import Candidate, CandidateList, DeviceParameters, ProjectTask


def investment_yuan(candidate: Candidate, devices: DeviceParameters) -> float:
    equipment = (
        candidate.pv_kw * devices.pv_cost_per_kw
        + candidate.battery_energy_kwh * devices.battery_cost_per_kwh
        + candidate.battery_power_kw * devices.battery_power_cost_per_kw
        + candidate.hp_kw_th * devices.hp_cost_per_kw_th
        + candidate.boiler_kw_th * devices.boiler_cost_per_kw_th
    )
    return equipment * (1 + devices.installation_fraction) + devices.grid_connection_cost_yuan


def build_candidates(task: ProjectTask) -> CandidateList:
    # Every rejected candidate remains visible in the subsequent result table.
    return CandidateList(candidates=[c.model_copy(deep=True) for c in task.candidates])
