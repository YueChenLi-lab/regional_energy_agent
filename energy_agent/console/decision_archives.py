"""Read-only presentation of existing published witnesses, never synthetic fallback."""
import hashlib
import json
from pathlib import Path

import streamlit as st

from ..counterfactual import CounterfactualResult
from ..regret import RegretResult
from .decision_components import regret_board, repair_board

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = {
    '反事实 · 24小时三路径': ('cf','docs/v04_evidence','three_paths_24h'),
    '后悔决策 · 合成24小时3×4': ('regret','docs/v041_evidence','synthetic_24h'),
    '后悔决策 · 混合8760小时2×3': ('regret','docs/v041_evidence','mixed_heat_8760h'),
}


def load_archive(name):
    kind,folder,stem=ARCHIVES[name]
    directory=ROOT/folder
    if kind=='regret':
        filename=stem+'_result.json'
        manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))['files']
        content=(directory/filename).read_bytes()
        if hashlib.sha256(content).hexdigest()!=manifest[filename]:
            raise ValueError('归档SHA256不符，拒绝显示为已验证证据')
        result=RegretResult.model_validate_json(content)
        downloads={'json':str(directory/filename),'csv':str(directory/(stem+'_matrix.csv')),
                   'markdown':str(directory/(stem+'_report.md'))}
        for path in downloads.values():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=manifest[Path(path).name]:
                raise ValueError('归档下载校验失败')
    else:
        filename=stem+'_repair.json'
        content=(directory/filename).read_bytes()
        # Pin the published v0.4 result; its old manifest hashes compressed
        # witnesses, not this JSON. Never invent a manifest entry.
        if hashlib.sha256(content).hexdigest()!='d577c85fda0e3dff047f32f79d435773886c2062873b4aca3dc712a686d20293':
            raise ValueError('原v0.4归档JSON校验值不符')
        result=CounterfactualResult.model_validate_json(content)
        downloads={'json':str(directory/filename),'markdown':str(directory/(stem+'_report.md'))}
    return result, downloads


def render_archived_decisions():
    with st.expander('决策实验归档 · 只读证据，不重新计算'):
        name=st.selectbox('查看已归档决策实验',[None,*ARCHIVES],
                          format_func=lambda x:x or '请选择归档（不自动求解）',key='dw_archive_select')
        if name is None:
            st.caption('尚未选择归档；不会调用求解器或模型。')
            return
        st.info('已归档的实际计算证据，不是当前项目的新计算，也不是实时模型输出；不允许从此处采用路径。来源与研究假设沿用原报告。')
        try:
            result,downloads=load_archive(name)
            if ARCHIVES[name][0]=='regret':
                regret_board(result,key_prefix='archive',download_files=downloads)
            else:
                repair_board(result)
                for key,path in downloads.items():
                    item=Path(path)
                    if item.is_file():
                        st.download_button('下载归档 '+key,item.read_bytes(),file_name=item.name,key='dw_archive_cf_'+key)
                with st.expander('归档权限、输入来源和独立校验证据'):
                    st.json(result.model_dump(mode='json'))
        except (OSError,ValueError,KeyError,StopIteration) as exc:
            st.error(f'归档不可用，未替换为示例数据：{exc}')
