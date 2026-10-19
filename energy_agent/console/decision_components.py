"""Read-only, escaped components. No solver, model or ToolRegistry calls here."""
from html import escape
from pathlib import Path
from importlib.resources import files
from typing import Callable

import streamlit as st

from .components import empty, safe, section
from .decision_presenters import (CandidateVM, g, num, path_title, Badge, BoundaryVM, ConversationVM, CounterfactualVM, IntentVM, KIND_LABEL,
                                  PathVM, RegretVM, STATE_TEXT, StageVM, TaskSummaryVM, build_counterfactual_vm,
                                  build_regret_vm, suggest_intent)

_h = safe


def decision_theme() -> None:
    st.html('<style>' + files(__package__).joinpath('decision_theme.css').read_text(encoding='utf-8') + '</style>')


def _badge(text, tone='muted') -> str:
    return f'<span class="dw-badge dw-t-{_h(tone)}">{_h(text)}</span>'


def _badges(items) -> str:
    return ''.join(_badge(b.text, b.tone) for b in items)


def _kv(rows) -> str:
    return '<dl class="dw-kv">' + ''.join(f'<div><dt>{_h(k)}</dt><dd>{_h(v)}</dd></div>' for k, v in rows) + '</dl>'


def _pos(left=None, width=None) -> str:
    parts = ([f'left:{left:.3f}%'] if left is not None else []) + ([f'width:{width:.3f}%'] if width is not None else [])
    return ' style="' + ';'.join(parts) + '"'


# ───────────── intent selector ─────────────
def intent_selector(options: tuple[IntentVM, ...], *, navigate: Callable[[str], None], router_ready: bool) -> None:
    by_key = {o.key: o for o in options}
    suggested, why = suggest_intent(st.session_state.get('dw_hint_text', ''))
    cards = ''.join(
        f'<article class="dw-intent{" dw-sug" if o.key == suggested else ""}{"" if o.available else " dw-off"}">'
        f'<h3>{_h(o.title)}</h3><p>{_h(o.tagline)}</p><p class="dw-eg">例：{_h(o.example)}</p></article>' for o in options)
    st.html('<div class="dw-intents">' + cards + '</div>')
    if not router_ready:
        st.caption('统一自然语言路由尚未接入：任务选择仅导航/提示，不自动调用工具或模型。')
    with st.expander('问题提示（仅关键词建议，不执行）'):
        st.text_input('描述你的问题（仅用于推荐任务类型；不调用模型，不执行）', key='dw_hint_text',
                      placeholder='例如：预算不够，怎么调整才能有可行方案？')
        if suggested:
            st.caption(f'建议任务类型：{by_key[suggested].title}（{why}）· 仅为提示，需要你自行选择并确认。')
    choice = st.segmented_control('任务类型', list(by_key), format_func=lambda k: by_key[k].title,
                                  key='dw_intent', default='plan_modify') or 'plan_modify'
    sel = by_key[choice]
    st.caption(sel.dest_hint)
    if sel.dest_page:
        st.button(f'进入「{sel.title}」工具配置 →', key='dw_go_' + sel.key, on_click=navigate,
                  args=(sel.dest_page,), disabled=not sel.available)
    if not sel.available:
        st.caption(sel.reason)


# ───────────── chat stream & pipeline ─────────────
def chat_stream(vm: ConversationVM) -> None:
    section('对话快照', '真实的当前请求与回答，不是完整历史聊天记录')
    if vm.empty:
        empty('尚无对话记录。先在下方助手输入要求；含糊条件会先澄清，不会自动求解。')
        return
    for m in vm.messages:
        avatar = {'user': 'user', 'assistant': 'assistant', 'tool': ':material/build:'}[m.role]
        with st.chat_message('user' if m.role == 'user' else 'assistant', avatar=avatar):
            st.html(f'<div class="dw-msghead dw-k-{_h(m.kind.lower())}"><span class="dw-kind">{_h(m.title)}</span>'
                    f'{_badges(m.chips)}</div>')
            if m.body:
                st.write(m.body)  # untrusted model text: native rendering, never raw HTML
            if m.items:
                st.html('<ul class="dw-list">' + ''.join(f'<li>{_h(i)}</li>' for i in m.items) + '</ul>')
            if m.metrics:
                st.html('<div class="dw-mini">' + ''.join(
                    f'<div><span>{_h(l)}</span><b>{_h(v)}</b><small>{_h(u)}</small></div>' for l, v, u in m.metrics) + '</div>')


def pipeline(stages, *, vertical: bool = False) -> None:
    items = ''.join(
        f'<li class="dw-st dw-st-{_h(s.state)}"><span class="dw-dot">{i + 1}</span><b>{_h(s.label)}</b>'
        f'<em>{_h(STATE_TEXT[s.state])}</em>' + (f'<small>{_h(s.detail)}</small>' if s.detail else '') + '</li>'
        for i, s in enumerate(stages))
    st.html(f'<ol class="dw-pipe{" v" if vertical else ""}" aria-label="执行阶段">{items}</ol>')
    st.caption('阶段状态来自已保存的请求、契约与运行结果；没有实时求解器内部进度，不显示虚构进度条。')


def task_summary(vm: TaskSummaryVM | None, stages, *, navigate: Callable[[str], None]) -> None:
    st.html('<span class="dw-aside"></span>')
    section('当前任务', '只读摘要')
    if vm is None:
        empty('尚无任务。加载并评估全年任务后，这里显示基准、版本、锁定条件与差异。')
        return
    st.html('<div class="dw-card">' + _kv((('请求 ID', vm.request_id), ('确认基准 run_id', vm.base_run_id),
                                           ('基准输入版本', vm.input_version),
                                           ('结果 / 当前确认 run_id', vm.result_run_id or '尚无结果'),
                                           ('结果 / 当前版本', vm.result_version),
                                           ('对话状态', vm.dialog_status))) + '</div>')
    if vm.conditions:
        st.html('<div class="dw-card"><div class="dw-eyebrow">已确认条件</div>' + _kv(vm.conditions) + '</div>')
    if vm.preserves or vm.preserves_text:
        st.html('<div class="dw-card"><div class="dw-eyebrow">用户锁定 / 保留</div><ul class="dw-chips">'
                + ''.join(f'<li>{_h(p)}</li>' for p in vm.preserves) + '</ul>'
                + (f'<p class="dw-sm">{_h(vm.preserves_text)}</p>' if vm.preserves_text else '') + '</div>')
    if vm.changes:
        st.html('<div class="dw-card"><div class="dw-eyebrow">修改清单</div><ul class="dw-list">'
                + ''.join(f'<li>{_h(c)}</li>' for c in vm.changes) + '</ul></div>')
    if vm.basis_text or vm.before_after or vm.before_after_note:
        body = (f'<p class="dw-sm">{_h(vm.basis_text)}</p>' if vm.basis_text else '')
        if vm.before_after:
            body += '<table class="dw-tbl"><thead><tr><th>指标</th><th>修改前</th><th>修改后</th><th>差值</th></tr></thead><tbody>' + ''.join(
                f'<tr><th scope="row">{_h(a)}</th><td>{_h(b)}</td><td>{_h(c)}</td><td>{_h(d)}</td></tr>'
                for a, b, c, d in vm.before_after) + '</tbody></table>'
        body += f'<p class="dw-sm">{_h(vm.before_after_note)}</p>' if vm.before_after_note else ''
        st.html('<div class="dw-card"><div class="dw-eyebrow">修改前后差异</div><div class="dw-scroll">' + body + '</div></div>')
    st.html('<div class="dw-card"><div class="dw-eyebrow">执行轨迹</div></div>')
    pipeline(stages, vertical=True)
    st.html(f'<div class="dw-card"><div class="dw-eyebrow">独立校验</div>{_badge(vm.verify_text, vm.verify_tone)}</div>')
    st.button('查看证据详情 →', key='dw_goto_evidence', on_click=navigate, args=('证据详情',))
    if vm.tool_rows:
        with st.expander('工具调用记录'):
            st.dataframe([dict(zip(('工具', '状态', '耗时 秒', '摘要'), r)) for r in vm.tool_rows], hide_index=True, width='stretch')


# ───────────── counterfactual ─────────────
def boundary_html(b: BoundaryVM) -> str:
    if not b.drawable:
        return '<div class="dw-bound-none">' + _h(b.readout[0]) + '</div>'
    segs = ''.join(f'<i class="seg {k}"{_pos(s, max(e - s, 0.0))} title="{_h(label)}"></i>' for k, s, e, label in b.segments)
    marks = ''.join(f'<b class="mk {k}"{_pos(p)} title="{_h(label)}"></b>' for k, p, label in b.markers)
    dots = ''.join(f'<u class="tr {"ok" if f == "feasible" else "bad" if f == "infeasible" else "unk"}"{_pos(p)} title="{_h(t)}"></u>'
                   for f, p, t in b.trials)
    legend = ('<li class="inf">已验证不可行</li><li class="gap">未判定区间</li><li class="ok">可行</li>'
              '<li class="tr-ok">已测可行点</li><li class="tr-bad">已测不可行点</li>')
    return (f'<div class="dw-bound" role="img" aria-label="可行性边界搜索图"><div class="dw-axis">{segs}{dots}{marks}</div>'
            f'<div class="dw-scale"><span>{_h(b.scale[0])}</span><span>{_h(b.scale[1])}</span></div>'
            f'<ul class="dw-legend2">{legend}</ul><ul class="dw-read">'
            + ''.join(f'<li>{_h(r)}</li>' for r in b.readout) + '</ul></div>')


def _path_card_html(p: PathVM) -> str:
    head = (f'<div class="dw-pc-head"><span class="dw-eyebrow">路径 {"ABC"[p.index % 3]} · 单独调整一个上限</span>'
            f'<h3>{_h(p.title)}</h3>{_badge(p.status_label, p.tone)}</div>')
    if p.verified:
        hero = (f'<div class="dw-hero"><span class="o">{_h(p.original_text)}</span><i>→</i><span class="n">{_h(p.suggested_text)}</span></div>'
                f'<div class="dw-adj">调整量 {_h(p.adjustment_text)}</div>')
    else:
        hero = f'<div class="dw-hero muted"><span class="o">{_h(p.original_text)}</span><small>原值</small></div>'
    body = hero + boundary_html(p.boundary)
    if p.metrics:
        body += '<div class="dw-mini">' + ''.join(f'<div><span>{_h(l)}</span><b>{_h(v)}</b></div>' for l, v in p.metrics) + '</div>'
    if p.candidate_name:
        body += (f'<div class="dw-eyebrow">对应设备配置</div><p class="dw-sm"><b>{_h(p.candidate_name)}</b></p><ul class="dw-chips">'
                 + ''.join(f'<li>{_h(a)} {_h(b)}</li>' for a, b in p.capacities) + '</ul>')
        body += ('<div class="dw-proof">' + _badge(p.solver_label, 'good' if p.solver_label and '最优' in p.solver_label and '未证明' not in p.solver_label else 'warn')
                 + _badge('gap ' + p.gap_text, 'muted') + _badge(p.validation_text, 'good' if p.validation_ok else 'bad')
                 + _badge('已达指定边界精度' if p.boundary.reached else '未达指定边界精度', 'good' if p.boundary.reached else 'warn') + '</div>')
    if p.caveat:
        body += f'<p class="dw-caveat">{_h(p.caveat)}</p>'
    if p.note:
        body += f'<p class="dw-sm">{_h(p.note)}</p>'
    return f'<article class="dw-card dw-path dw-tone-{_h(p.tone)}">{head}{body}</article>'


def repair_board(result, *, adopt: Callable[[PathVM], None] | None = None) -> None:
    """Strategy cards + feasibility-boundary chart. ``adopt`` renders the EXISTING adopt button."""
    decision_theme()
    if result is None:
        cols = st.columns(3)
        for col, field_name in zip(cols, ('budget_yuan', 'emission_limit_kg', 'grid_limit_kw')):
            with col:
                st.html(f'<article class="dw-card dw-path"><h3>{_h(path_title(field_name))}</h3>{_badge("待执行 / 未授权")}'
                        '<p class="dw-sm">尚无搜索结果；不显示虚构边界或数值。</p></article>')
        return
    vm: CounterfactualVM = build_counterfactual_vm(result)
    st.html('<div class="dw-banner"><div>' + _badge(vm.status_label, vm.status_tone) + _badge(vm.baseline_label, vm.baseline_tone)
            + f'<span class="dw-sm">调用 {_h(vm.solver_calls)} · 耗时 {_h(vm.elapsed)} · 基准 {_h(vm.base_run_id[:8])} v{_h(vm.input_version)}</span></div>'
            '<p>三条路径<b>互为替代</b>，每条只调整一个上限，其余负荷、时段、服务与输入保持；不是累计修改，也不是唯一不可行原因。探索结果未自动采用。</p>'
            + ('<ul class="dw-list">' + ''.join(f'<li>{_h(r)}</li>' for r in vm.baseline_reasons) + '</ul>' if vm.baseline_reasons else '')
            + '</div>')
    fields = ('budget_yuan','emission_limit_kg','grid_limit_kw')
    cols = st.columns(3)
    for col, field in zip(cols, fields):
        with col:
            p=next((p for p in vm.paths if p.field==field),None)
            if p is None:
                st.html(f'<article class="dw-card dw-path"><h3>{_h(path_title(field))}</h3>{_badge("待执行 / 未授权")}</article>')
                continue
            st.html(_path_card_html(p))
            if p.trace_rows:
                with st.expander(f'搜索轨迹（{len(p.trace_rows)} 次）'):
                    st.dataframe([dict(zip(p.trace_header, r)) for r in p.trace_rows], hide_index=True, width='stretch')
            if p.can_adopt and adopt is not None:
                adopt(p)  # caller renders the existing keyed button + adopt_counterfactual_path()
    if vm.monotonicity:
        st.caption(vm.monotonicity)


# ───────────── regret ─────────────
def _td(c, mode: str, selected: bool) -> str:
    if c is None:
        return '<td class="dw-cell dw-x">—</td>'
    text, level = (c.cost_text, c.cost_level) if mode == 'cost' else (c.regret_text, c.regret_level)
    has_value = (c.cost is not None) if mode == 'cost' else (c.regret is not None)
    cls = ['dw-cell']
    if has_value:
        cls.append('dw-zero' if mode == 'regret' and c.regret_zero else f'l{level or 0}')
        if c.kind == 'upper_bound':
            cls.append('dw-ub')
        if mode == 'cost' and c.scenario_best:
            cls.append('dw-best')
    else:
        cls += ['dw-x', f'dw-x-{c.kind}']  # null / infeasible / unknown are TEXT, never 0 and never a cost
    if selected:
        cls.append('dw-sel')
    return f'<td class="{" ".join(cls)}" tabindex="0" title="{_h(c.tooltip)}">{_h(text)}</td>'


def heat_table(vm: RegretVM, mode: str, selected) -> str:
    head = ''.join(f'<th scope="col" title="{_h(s.assumption)}"><span>{_h(s.name)}</span>'
                   f'<small>{_h(s.id)}{" · 基准" if s.is_baseline else ""}</small></th>' for s in vm.scenarios)
    rows = []
    for cand in vm.candidates:
        mark = ' ★' if cand.recommended else ' ☆' if cand.provisional else ''
        cells = ''.join(_td(vm.cells.get((cand.id, s.id)), mode, selected == (cand.id, s.id)) for s in vm.scenarios)
        rows.append(f'<tr><th scope="row"><b>{_h(cand.id)}{mark}</b><small>{_h(cand.name)}</small></th>{cells}</tr>')
    title = ('成本矩阵 · ' + vm.basis_title) if mode == 'cost' else '后悔矩阵 · 相对各情景当前候选集最佳'
    return (f'<div class="dw-scroll" role="region" aria-label="{_h(title)}" tabindex="0">'
            f'<table class="dw-heat dw-{mode}"><thead><tr><th class="dw-corner" scope="col">配置 ＼ 情景</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def legend_html(vm: RegretVM, mode: str) -> str:
    lo, hi = vm.cost_range if mode == 'cost' else (0.0, vm.regret_max)
    scale = (f'<span>{_h(num(lo, 0))}</span><span class="dw-ramp {mode}" aria-hidden="true"></span>'
             f'<span>{_h(num(hi, 0))} 元</span>')
    keys = ('<li class="k ub">斜纹 = 可行但成本为上界（未证明最优）</li>'
            '<li class="k xi">已确认不可行（无成本，不是 0）</li>'
            '<li class="k xu">求解未完成 / 未执行（未确定，不等于不可行）</li>')
    keys += ('<li class="k best">绿框 = 该情景当前候选集最低成本</li>' if mode == 'cost'
             else '<li class="k zero">绿底 0 = 该情景下已是当前候选集最佳</li>')
    return f'<div class="dw-legend"><div class="dw-scalebar">{scale}</div><ul>{keys}</ul></div>'


def candidate_cards_html(vm: RegretVM) -> str:
    cards = []
    for c in vm.candidates:
        tags = ''
        if c.recommended:
            tags += _badge('★ 最小最大后悔' if vm.status=='certified' else '★ 近似排序候选', 'good' if vm.status=='certified' else 'warn')
        elif c.provisional:
            tags += _badge('☆ 暂定（部分结果）', 'warn')
        if c.baseline_cheapest:
            tags += _badge('基准情景最便宜', 'info')
        if c.minimax_cost:
            tags += _badge('最小最大成本（另一准则）', 'muted')
        cap = ('<li class="ok">跨情景容量一致 ✓</li>' if c.capacities_consistent is True else
               '<li class="bad">容量不一致 ✗</li>' if c.capacities_consistent is False else
               '<li>容量一致性：无可行单元，未验证</li>')
        cards.append(
            f'<article class="dw-card dw-cand{" rec" if c.recommended else ""}"><div class="dw-pc-head">'
            f'<h3>{_h(c.id)} · {_h(c.name)}</h3>{tags}</div>'
            f'<div class="dw-eyebrow">固定装机 · {_h(c.origin)}</div><ul class="dw-chips">'
            + ''.join(f'<li>{_h(a)} {_h(b)}</li>' for a, b in c.capacities) + '</ul>'
            f'<dl class="dw-kv"><div><dt>初始投资</dt><dd>{_h(c.investment)}</dd></div>'
            f'<div><dt>可行情景</dt><dd>{c.feasible_count} / {c.total}</dd></div>'
            f'<div><dt>已确认不可行</dt><dd>{c.infeasible_count}</dd></div>'
            f'<div><dt>未定（未完成/未执行）</dt><dd>{c.unresolved_count}</dd></div></dl>'
            f'<ul class="dw-flags">{cap}<li>容量指纹 {_h(c.capacity_sha8)}…</li></ul></article>')
    return '<div class="dw-cands">' + ''.join(cards) + '</div>'


def worst_regret_html(vm: RegretVM) -> str:
    vals = [c.worst_regret for c in vm.candidates if c.worst_regret is not None]
    top = max(vals) if vals else 0
    ordered = sorted(vm.candidates, key=lambda c: (c.worst_regret is None, c.worst_regret or 0, c.id))
    rows = []
    for c in ordered:
        mark = ' ★' if c.recommended else ' ☆' if c.provisional else ''
        left = f'<div><b>{_h(c.id)}{mark}</b><small>{_h(c.name)}</small></div>'
        if c.worst_regret is None:
            rows.append(f'<div class="dw-wr na">{left}<div class="bar" aria-hidden="true"></div>'
                        f'<div class="val">无全情景可行见证<small>可行 {c.feasible_count}/{c.total} · 不参与最小最大后悔</small></div></div>')
            continue
        width = 0 if top <= 0 else max(1.5, c.worst_regret / top * 100) if c.worst_regret > 0 else 0
        where = '、'.join(c.worst_scenarios) or '—'
        note = ('各情景均为当前候选集最佳' if vm.status=='certified' else '各情景当前已得成本最小（近似/部分状态见上）') if c.worst_regret <= vm_tol(vm) else f'最坏情景：{where}'
        rows.append(f'<div class="dw-wr{" rec" if c.recommended else ""}">{left}'
                    f'<div class="bar"><i{_pos(None, width)}></i></div>'
                    f'<div class="val">{_h(num(c.worst_regret, 0))} 元<small>{_h(note)}</small></div></div>')
    return '<div class="dw-worst" role="list">' + ''.join(rows) + '</div>'


def vm_tol(vm: RegretVM) -> float:
    return vm.tolerance  # original arithmetic tolerance; no invented display threshold


def regret_board(result, *, key_prefix='live', download_files=None) -> None:
    """Read-only decision board for a RegretResult. Replaces regret_ui.show_regret_result's body."""
    decision_theme()
    vm = build_regret_vm(result)
    st.html(f'<div class="dw-banner dw-tone-{_h(vm.status_tone)}"><div class="dw-bn-top">{_badge(vm.status_label, vm.status_tone)}'
            f'<span class="dw-sm">基准 {_h(vm.base_run_id[:8])} · v{_h(vm.input_version)} · 请求 {_h(vm.request_id[:18])}</span></div>'
            f'<p>{_h(vm.status_note)}</p></div>')
    feasible = sum(c.feasible_count for c in vm.candidates)
    rec = ('、'.join(vm.recommended_ids) + ' ★') if vm.recommended_ids else \
        ('暂定 ' + '、'.join(vm.provisional_ids) + '（部分结果）') if vm.provisional_ids else '无完整推荐'
    kpis = (('基准情景最便宜', '、'.join(vm.baseline_cheapest_ids) or '不可用', ''),
            ('最小最大后悔', rec, vm.status_label), ('求解适配器调用', str(vm.solver_calls), vm.elapsed),
            ('单元状态', f'{feasible} 可行 · {vm.infeasible} 不可行 · {vm.unresolved} 未定', ''))
    st.html('<div class="dw-kpis">' + ''.join(
        f'<div class="dw-kpi"><span>{_h(a)}</span><b>{_h(b)}</b><small>{_h(c)}</small></div>' for a, b, c in kpis) + '</div>')
    st.html(f'<div class="dw-card"><div class="dw-eyebrow">成本口径</div><p class="dw-sm"><b>{_h(vm.basis_title)}</b>（元）· {_h(vm.basis_note)}'
            + (f' · {_h(vm.period_note)}' if vm.period_note else '') + f'</p><p class="dw-sm">{_h(vm.case_label)}</p></div>')
    with st.expander('决策解释', expanded=True):
        st.html('<div class="dw-explain">' + ''.join(f'<p>{_h(p)}</p>' for p in vm.paragraphs) + '</div>')
    section('情景假设', '人为研究假设，不是预测；未分配概率')
    st.html('<div class="dw-scen">' + ''.join(
        f'<div class="dw-card"><b>{_h(s.name)}</b>{_badge("基准") if s.is_baseline else ""}<ul class="dw-chips">'
        + (''.join(f'<li>{_h(c)}</li>' for c in s.chips) or '<li>全部倍数 = 1</li>') + '</ul></div>' for s in vm.scenarios) + '</div>')
    section('固定装机配置', '容量沿用已确认任务，跨情景保持不变；只有逐时运行适应情景')
    st.html(candidate_cards_html(vm))
    pairs = [(c.id, s.id) for c in vm.candidates for s in vm.scenarios]
    names = {s.id: s.name for s in vm.scenarios}
    picked = st.selectbox('聚焦单元（高亮并显示详情；手机无悬停时使用）', [None] + pairs, key='dw_cell_' + key_prefix + '_' + vm.request_id,
                          format_func=lambda p: '不聚焦' if p is None else f'{p[0]} × {names.get(p[1], p[1])}')
    for mode, title in (('cost', '成本矩阵'), ('regret', '后悔矩阵')):
        section(title, vm.basis_title + ' · 元' if mode == 'cost' else '相对各情景当前候选集最佳 · 元')
        st.html(legend_html(vm, mode))
        st.html(heat_table(vm, mode, picked))
    if picked is not None and picked in vm.cells:
        st.html('<div class="dw-card"><div class="dw-eyebrow">单元详情 · ' + _h(f'{picked[0]} × {names.get(picked[1], picked[1])}')
                + '</div>' + _kv(vm.cells[picked].detail) + '</div>')
    section('最坏后悔对比', '仅全部指定情景均有可行见证的配置参与；部分/近似状态不表示精确最优')
    st.html(worst_regret_html(vm))
    files = download_files if download_files is not None else (g(result, 'files', {}) or {})
    for kind, label, mime in (('json', '下载结构化结果', 'application/json'), ('csv', '下载矩阵CSV', 'text/csv'),
                              ('markdown', '下载中文报告', 'text/markdown')):
        raw = files.get(kind) if isinstance(files, dict) else None
        p = Path(raw) if raw else None
        if p is not None and p.is_file():
            st.download_button(label, p.read_bytes(), file_name=p.name, mime=mime, key=f'dw_regret_dl_{kind}_{key_prefix}_{vm.request_id}')
    st.caption('排放物质与核算边界见原任务，排放未折现。没有“采用”按钮：本分析不改写当前确认任务。')
    with st.expander('逐单元证据与完整结构化结果'):
        st.dataframe([{'配置': cid, '情景': sid, **dict(c.detail)} for (cid, sid), c in vm.cells.items()],
                     hide_index=True, width='stretch')
        st.json(result.model_dump(mode='json') if hasattr(result, 'model_dump') else result)
