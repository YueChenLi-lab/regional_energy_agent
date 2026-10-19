"""Shared, conservative quantity and operation semantics for authorized edits.

A complete unit token is validated before arithmetic. No model is involved.
Negated/ambiguous operations are rejected before clause splitting or evaluation.
"""
from dataclasses import dataclass
from decimal import Decimal
import re


class EditMeaningError(ValueError):
    pass


# Longest complete lexical unit wins; ASCII suffixes are consumed in full, so
# kWh, kW_th, kgCO2e and yuan/kWh cannot be accepted as a shorter unit prefix.
_NUMBER = re.compile(r'(?<![A-Za-z0-9_.])([+-]?\d+(?:\.\d+)?)(?:\s*)((?:个百分点|[%％]|万元|万|元|年|吨|千克|[A-Za-z_])(?:[A-Za-z0-9_/]|(?<=/)年)*|)')
_TARGET = re.compile(r'改为|设为|设置为|调整为|变为|调至|(?:增加|提高|上调|降低|减少|削减|下调|缩减|延长|缩短|降|减|增)(?:到|至)')
_UP = re.compile(r'增加|提高|上调|增长|上升|延长')
_DOWN = re.compile(r'减少|降低|削减|下调|缩减|下降|缩短')
_NEGATION = re.compile(r'不(?!变)|不要|勿|别|禁止|无需|无须|无意|没有|尚未')
_CHOICE = re.compile(r'或者|或|至少|不低于|不超过|范围|以上|以下|以内|至多|不多于|最多|最少|超过|低于|高于|大于|小于|少于|多于|\d\s*(?:~|～|—|-)\s*\d')
_APPROXIMATE = re.compile(r'大约|大概|约莫|差不多|左右|上下|近似|大致|视情况|看情况|酌情|适当|约(?=\s*\d|增加|提高|减少|降低|为|到|至)')


def has_negation(text):
    return bool(_NEGATION.search(text))


def is_explicit_preservation(text):
    """Only an unambiguous keep/cancel prohibition is a preservation, not an edit."""
    return bool(re.search(r'不变|保持|保留|维持|(?:不要|不|无需|禁止|不能)取消',text)) and not (_UP.search(text) or _DOWN.search(text) or _TARGET.search(text))


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit: str


@dataclass(frozen=True)
class ParsedEdit:
    operation: str
    value: float
    canonical_unit: str
    input_unit: str
    multiplier: float | None = None


def _quantity(match):
    value=Decimal(match[1])
    if value < 0:raise EditMeaningError('负数不能转换为正数执行，请明确有效值')
    return Quantity(value,match[2].replace('％','%'))


def _convert(quantity, dimension, species):
    unit=quantity.unit
    simple={
        'money':{'元':1,'万元':10000,'万':10000},
        'annual_money':{'元':1,'万元':10000,'万':10000,'元/年':1,'万元/年':10000},
        'years':{'年':1}, 'power':{'kw':1}, 'thermal_power':{'kw_th':1},
        'energy':{'kwh':1}, 'thermal_energy':{'kwh_th':1},
        'electric_om':{'元/kwh':1}, 'thermal_om':{'元/kwh_th':1},
        'rate':{'%':Decimal('.01'),'':1},
    }
    if dimension=='emissions':
        # t/T are both metric tonnes. Explicit species must match the task;
        # bare mass inherits the confirmed task species, never CO2 -> CO2e.
        key=unit.casefold()
        for suffix in ('co2e','co2'):
            if key.endswith(suffix):
                if suffix!=species.casefold():raise EditMeaningError('排放物质与当前任务不一致，不能混用CO2与CO2e')
                key=key[:-len(suffix)];break
        mapping={'kg':1,'千克':1,'t':1000,'吨':1000}
    else:
        key=unit if dimension in ('money','annual_money','years','rate') else unit.casefold()
        mapping=simple.get(dimension,{})
    if key not in mapping:raise EditMeaningError(f'单位“{unit or "缺失"}”不属于该字段要求的{dimension}，不能按单位前缀截取')
    return quantity.value*Decimal(str(mapping[key]))


def parse_edit(text,current,dimension,*,species='CO2e'):
    """Return a target, delta, or baseline ratio; refuse guessing the operation.

    Percentages for scalar rates may be absolute targets. For physical amounts
    and load scales, a target percentage must explicitly reference the baseline.
    """
    if re.search(r'(?:[-−－]|负)\s*\d',text):raise EditMeaningError('负数不能转换为正数执行，请明确有效值')
    if has_negation(text):raise EditMeaningError('修改包含否定，需先明确是否修改及最终目标；未执行被否定的操作')
    if _CHOICE.search(text) or _APPROXIMATE.search(text):raise EditMeaningError('近似量、多个选项、范围或不等式需要澄清为唯一目标')
    matches=list(_NUMBER.finditer(text))
    if not matches:raise EditMeaningError('缺少明确数值与完整单位')
    quantities=[_quantity(m) for m in matches]
    target=bool(_TARGET.search(text));up=bool(_UP.search(text));down=bool(_DOWN.search(text))
    if len(quantities)==2:
        if '从' not in text or not target:raise EditMeaningError('多个数值不能猜测采用哪一个')
        start=_convert(quantities[0],dimension,species)
        if abs(start-Decimal(str(current)))>Decimal('.000001'):raise EditMeaningError('声明的起始值与已确认基准不一致')
        quantities=quantities[1:]
    if len(quantities)!=1:raise EditMeaningError('必须明确一个修改目标')
    q=quantities[0];base=Decimal(str(current))
    def verify_target(value):
        if target and (up and down or up and value<base or down and value>base):
            raise EditMeaningError('目标值与增加/减少方向矛盾，请明确最终目标或增减方向')
    canonical={'money':'元','annual_money':'元/年','years':'年','power':'kW','thermal_power':'kW_th','energy':'kWh',
               'thermal_energy':'kWh_th','electric_om':'元/kWh','thermal_om':'元/kWh_th','rate':'1','scale':'相对基准倍数','emissions':'kg'+species}[dimension]
    if q.unit=='个百分点':
        if dimension!='rate' or target or up==down:raise EditMeaningError('百分点只支持明确的费率增减')
        value=base+q.value/100*(1 if up else -1)
        return ParsedEdit('delta',float(value),canonical,q.unit)
    ratio=bool(re.search(r'原来|原有|基准',text))
    if q.unit=='%' and (dimension!='rate' or ratio or (not target and up!=down)):
        if target and not ratio:raise EditMeaningError('百分比目标需要明确“原来的/基准的”比例，或给出绝对值及单位')
        if ratio and not target and up==down:raise EditMeaningError('基准比例需要明确“调整到/改为/提高到”等目标操作')
        if target:factor=q.value/100
        elif up!=down:factor=1+q.value/100*(1 if up else -1)
        else:raise EditMeaningError('百分比没有明确的目标或增减方向')
        if factor<0:raise EditMeaningError('修改后的值不能为负')
        verify_target(base*factor)
        return ParsedEdit('baseline_ratio' if target else 'relative_percent',float(base*factor),canonical,q.unit,float(factor))
    if dimension=='scale':raise EditMeaningError('负荷修改只支持明确的相对百分比或基准比例')
    value=_convert(q,dimension,species)
    if target:operation='target'
    elif up!=down:
        operation='delta';value=base+value*(1 if up else -1)
    elif up and down:raise EditMeaningError('增减方向相互矛盾')
    else:operation='target'  # e.g. “规划期25年”, with a complete compatible unit
    if value<0:raise EditMeaningError('修改后的值不能为负')
    verify_target(value)
    return ParsedEdit(operation,float(value),canonical,q.unit)
