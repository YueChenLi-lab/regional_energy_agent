"""Read-only, escaped components backed by existing business schemas."""
from html import escape
from importlib.resources import files
from typing import Sequence

import pandas as pd
import streamlit as st


def safe(value) -> str:
    return escape(str(value), quote=True)


def theme() -> None:
    st.html('<style>' + files(__package__).joinpath('theme.css').read_text(encoding='utf-8') + '</style>')


def section(title: str, subtitle: str = '') -> None:
    st.html(f'<div class="rea-section"><h2>{safe(title)}</h2><span>{safe(subtitle)}</span></div>')


def empty(message: str) -> None:
    st.html(f'<div class="rea-empty">{safe(message)}</div>')


def number(value: float | str | None, decimals: int = 2) -> str:
    if isinstance(value, str):
        return safe(value)
    return '待评估' if value is None else f'{value:,.{decimals}f}'


def metrics(items: Sequence[tuple[str, float | str | None, str]]) -> None:
    """None is missing, never a manufactured zero; units are explicit."""
    cards = ''.join(f'<div class="rea-card"><div class="rea-label">{safe(label)}</div>'
                    f'<div class="rea-value">{number(value)}</div><div class="rea-unit">{safe(unit)}</div></div>'
                    for label, value, unit in items)
    st.html('<div class="rea-grid">' + cards + '</div>')


def feature_cards(items: Sequence[tuple[str, str, str]]) -> None:
    cards = ''.join(f'<article class="rea-card"><div class="rea-eyebrow">{safe(tag)}</div>'
                    f'<h3>{safe(title)}</h3><p>{safe(description)}</p></article>'
                    for tag, title, description in items)
    st.html('<div class="rea-grid three">' + cards + '</div>')


def execution(run) -> None:
    """Show recorded transitions only. No simulated progress or optimistic steps."""
    steps = ''.join(f'<span class="rea-step done">{safe(s.value)}</span>' for s in run.states)
    st.html('<div class="rea-steps">' + steps + '</div>')
    st.caption(f'当前状态：{run.state.value} · 输入版本 {run.input_version} · run_id：{run.run_id}')


def series_chart(frame: pd.DataFrame, unit: str, key: str) -> None:
    """Native Vega-Lite, explicit dark axes; retain real timestamps and samples."""
    data = frame.copy()
    # Temporal rendering otherwise follows the browser timezone. Use an
    # explicit UTC axis, keeping the original source timezone in the task.
    data.index = pd.to_datetime(data.index, utc=True)
    data.index.name = 'timestamp'
    long = data.reset_index().melt(id_vars='timestamp', var_name='series', value_name='value')
    long['time_label'] = long['timestamp'].map(lambda t: t.isoformat())
    st.vega_lite_chart(long, {
        'background': '#0d1c2e', 'height': 280,
        'mark': {'type': 'line', 'strokeWidth': 1.6, 'clip': True},
        'encoding': {
            'x': {'field': 'timestamp', 'type': 'temporal', 'scale': {'type': 'utc'}, 'title': '时间 UTC（原始时区见输入证据）'},
            'y': {'field': 'value', 'type': 'quantitative', 'title': unit},
            'color': {'field': 'series', 'type': 'nominal', 'title': None,
                      'scale': {'range': ['#59dfeb', '#71dfb7', '#f3c67d', '#a9a5ff', '#fa9f9f', '#c8e3ff']}},
            'tooltip': [{'field': 'time_label', 'type': 'nominal', 'title': '时间 UTC'}, {'field': 'series'},
                        {'field': 'value', 'type': 'quantitative', 'format': ',.3f'}],
        },
        'params': [{'name': 'view_window', 'select': {'type': 'interval', 'encodings': ['x']}, 'bind': 'scales'}],
        'config': {'view': {'stroke': None},
                   'axis': {'labelColor': '#a6bbcf', 'titleColor': '#edf4fc', 'gridColor': '#24384c'},
                   'legend': {'labelColor': '#edf4fc', 'orient': 'bottom'}},
    }, theme=None, key=key, width='stretch')
