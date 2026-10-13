"""B2R local I/O, capability checks and versioned delivery. No network calls."""
from __future__ import annotations

import copy
import hashlib
import html
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parent / "vendor"
sys.path.insert(0, str(VENDOR))
from _common import CliError, checked_input_file, atomic_write_bytes

VERSION = "0.3.9"
SKILL_ROOT = Path(__file__).resolve().parents[1]
FONT = SKILL_ROOT / "assets/fonts/B2RSansSC-Regular.ttf"


def require(condition, message):
    if not condition:
        raise CliError(message)


def finite(value, name, minimum=None, maximum=None):
    require(not isinstance(value, bool) and isinstance(value, (float, int)), f"{name} 必须是数字")
    require(math.isfinite(value), f"{name} 必须是有限数")
    require(minimum is None or value >= minimum, f"{name} 过小")
    require(maximum is None or value <= maximum, f"{name} 过大")
    return float(value)


def fields(obj, allowed, name):
    require(isinstance(obj, dict), f"{name} 必须是对象")
    require(not set(obj) - set(allowed), f"{name} 含未知字段：{', '.join(sorted(set(obj)-set(allowed)))}")


def text_value(value, name, max_length=400):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= max_length,
            f"{name} 必须是 1—{max_length} 字符的文本")
    require(all(ord(c) >= 32 or c == '\n' for c in value), f"{name} 含控制字符")
    return value


def color(value):
    require(isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value), "颜色必须是 #RRGGBB")
    return value


def read_json(path):
    path = checked_input_file(path, max_bytes=2_000_000)
    try:
        def reject(value):
            raise CliError(f"JSON 不允许 {value}")
        return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject)
    except (ValueError, UnicodeError) as exc:
        raise CliError(f"JSON 无法读取：{exc}") from None


def write_json(path, value):
    atomic_write_bytes(Path(path), (json.dumps(value, ensure_ascii=False, indent=2,
                                             allow_nan=False) + '\n').encode())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capabilities(host=None):
    host = host or {}
    fields(host, ['file_read', 'code_execution', 'image_generation', 'image_editing', 'web_search',
                  'external_service', 'notes'], 'host_capabilities')
    for key, value in host.items():
        if key != 'notes':
            require(value in ['available', 'unavailable', 'unknown'], f"{key} 状态不合法")
    return {
        'b2r_version': VERSION, 'python': platform.python_version(),
        'platform': platform.platform(), 'architecture': platform.machine(),
        'local': {n: importlib.util.find_spec(n) is not None for n in ['matplotlib', 'numpy', 'PIL', 'openpyxl']},
        'bundled_chinese_font': FONT.is_file(),
        'host_reported': {k: host.get(k, 'unknown') for k in ['file_read', 'code_execution',
                         'image_generation', 'image_editing', 'web_search', 'external_service']},
        'notes': host.get('notes', []),
        'external_api': 'NO_DIRECT_API_CLIENT; use authorized host tools; no keys read, no network requests',
        'notice': '本地探测不证明宿主工具可用；宿主声明不证明在线调用成功。'
    }


def new_version(output):
    root = Path(output).expanduser()
    require(not root.is_symlink(), '输出目录不能是符号链接')
    root.mkdir(parents=True, exist_ok=True)
    for i in range(1, 10000):
        folder = root / f'v{i:03d}'
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            continue
    raise CliError('版本目录过多')


def matplotlib_setup():
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        require(FONT.is_file(), '缺少随附中文字体；请重新安装完整 Skill')
        font_manager.fontManager.addfont(str(FONT))
        family = font_manager.FontProperties(fname=str(FONT)).get_name()
        matplotlib.rcParams.update({
            'font.family': family, 'font.size': 11, 'axes.unicode_minus': False,
            'svg.hashsalt': 'b2r-v0.1', 'svg.fonttype': 'none', 'pdf.fonttype': 42,
            'figure.facecolor': 'white', 'axes.facecolor': 'white',
            'text.color': '#202E40', 'axes.labelcolor': '#202E40',
            'xtick.color': '#455468', 'ytick.color': '#455468',
        })
        return plt
    except ImportError:
        raise CliError('缺少绘图依赖；在隔离环境安装 requirements.txt') from None


def export(fig, folder, provenance, dpi=300):
    from figure_export import export_figure
    report = export_figure(fig, folder / 'figure', formats=['svg', 'png', 'pdf'], dpi=dpi,
                          bbox_inches=None, provenance=provenance, write_manifest=True,
                          metadata={'Creator': 'Bench2Result '+VERSION})
    # Same scene, glyph paths for portable appearance; editable text remains in figure.svg.
    export_figure(fig, folder / 'figure-outlined', formats=['svg'], dpi=dpi,
                  font_mode='paths', bbox_inches=None,
                  metadata={'Creator': 'Bench2Result '+VERSION})
    report['outputs'] = [{**o, 'path': Path(o['path']).name} for o in report['outputs']]
    report['manifest'] = 'figure.export.json'
    # Upstream wrote its manifest before adding the manifest field; rewrite portable paths.
    p = folder / 'figure.export.json'
    p.unlink()
    write_json(p, report)
    return report


def package_replay(folder, kind, input_name=None):
    replay=folder/'reproduce'
    replay.mkdir()
    shutil.copytree(SKILL_ROOT/'scripts',replay/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(SKILL_ROOT/'assets/fonts',replay/'assets/fonts')
    for name in ['requirements.txt','requirements-compose.txt','requirements-xlsx.txt','LICENSE','THIRD_PARTY_NOTICES.md','upstream-provenance.json']:
        if (SKILL_ROOT/name).exists(): shutil.copyfile(SKILL_ROOT/name,replay/name)
    shutil.copyfile(SKILL_ROOT/'assets/LICENSE-K-Dense.txt',replay/'assets/LICENSE-K-Dense.txt')
    data_args=",'--data',str(p/"+repr(input_name)+")" if input_name else ''
    if kind in ['artwork','assemble']: data_args+=",'--assets',str(p)"
    runner="from pathlib import Path\nimport subprocess,sys\np=Path(__file__).resolve().parent\nsubprocess.run([sys.executable,str(p/'reproduce/scripts/b2r.py'),"+repr(kind)+",'--spec',str(p/'source.json')"+data_args+",'--out',str(p/'rerun')],check=True)\n"
    (folder/'reproduce.py').write_text(runner,encoding='utf-8')


def text_checks(fig):
    """Real renderer bounds; screening only, not a scientific/layout certificate."""
    from matplotlib.text import Text
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    page = fig.bbox
    labels, issues = [], []
    hidden_ticks=set()
    for ax in fig.axes:
        for axis in [ax.xaxis,ax.yaxis]:
            low,high=sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                # Matplotlib creates locator labels outside the visible view.
                # Those Text objects report visible=True but are never drawn.
                if tick.get_loc()<low-1e-9 or tick.get_loc()>high+1e-9:
                    hidden_ticks.update([id(tick.label1),id(tick.label2)])
    for t in fig.findobj(Text):
        if id(t) in hidden_ticks or not t.get_visible() or not t.get_text():
            continue
        b = t.get_window_extent(renderer)
        if b.width == 0 or b.height == 0:
            continue
        if b.x0 < page.x0 - 1 or b.y0 < page.y0 - 1 or b.x1 > page.x1 + 1 or b.y1 > page.y1 + 1:
            issues.append({'kind': 'text_outside_page', 'text': t.get_text()})
        labels.append((t, b))
    # Tick offsets / intentionally invisible text are already excluded above.
    for i, (a, ba) in enumerate(labels):
        for b, bb in labels[i+1:]:
            if ba.overlaps(bb):
                issues.append({'kind': 'text_overlap', 'texts': [a.get_text(), b.get_text()]})
    return {'screening': 'REVIEW_REQUIRED' if issues else 'NO_TEXT_BOUND_ISSUES_DETECTED',
            'issues': issues, 'manual_visual_review': 'PENDING', 'scientific_review': 'PENDING',
            'notice': '仅真实渲染的文本边界筛查；未检查所有线条、图片或科学关系。'}


def verify_files(folder):
    import xml.etree.ElementTree as ET
    from PIL import Image
    from fontTools.ttLib import TTFont
    font = TTFont(FONT)
    cmap = font.getBestCmap()
    details = {}
    for name in ['figure.svg', 'figure-outlined.svg']:
        tree = ET.parse(folder / name)
        texts = tree.findall('.//{http://www.w3.org/2000/svg}text')
        missing = sorted({c for t in texts for c in ''.join(t.itertext()) if ord(c) not in cmap and not c.isspace()})
        require(not missing, f'字体不支持字符：{" ".join(missing)}')
        details[name] = {'parsed': True, 'text_elements': len(texts),
                         'raster_elements': len(tree.findall('.//{http://www.w3.org/2000/svg}image'))}
    with Image.open(folder / 'figure.png') as im:
        im.load()
        details['figure.png'] = {'decoded': True, 'pixels': list(im.size)}
    payload = (folder / 'figure.pdf').read_bytes()
    require(payload.startswith(b'%PDF-') and b'%%EOF' in payload[-1024:], 'PDF 文件不完整')
    details['figure.pdf'] = {'header_and_eof_checked': True}
    return details


def finish(folder, manifest, notes, qa=None):
    if qa is not None:
        qa['file_checks'] = verify_files(folder)
        write_json(folder / 'qa.json', qa)
    atomic_write_bytes(folder / '交付说明.md', ('# B2R 交付\n\n' + notes + '\n').encode())
    status = manifest.get('status', 'GENERATED_REVIEW_PENDING')
    figure = '<img src="figure-outlined.svg" alt="科研图件预览">' if (folder / 'figure.svg').exists() else ('<img src="figure.png" alt="科研图件预览">' if (folder/'figure.png').exists() else '')
    names = sorted({p.name for p in folder.iterdir() if p.is_file()} | {'manifest.json'})
    links = ''.join(f'<li><a href="{html.escape(n, quote=True)}">{html.escape(n)}</a></li>'
                    for n in names if n != 'index.html')
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>B2R 交付</title>
    <style>body{{font:16px system-ui;margin:32px auto;max-width:1100px;padding:0 20px;color:#202e40}}
    img{{width:100%;border:1px solid #dde4eb}}pre{{white-space:pre-wrap;line-height:1.7}}a{{color:#176a9e}}</style>
    <h1>Bench2Result · {folder.name}</h1>{figure}
    <p>{' · '.join(f'<a href="{n}">{n}</a>' for n in ['figure.png','figure.pdf','figure.svg'] if (folder/n).exists())}</p>
    <pre>{html.escape(notes)}</pre><details><summary>制作源、来源与检查记录</summary><p>{html.escape(status)}</p><ul>{links}</ul></details></html>'''
    atomic_write_bytes(folder / 'index.html', page.encode())
    manifest.update({'b2r_version': VERSION, 'version': folder.name,
                     'files': {str(p.relative_to(folder)).replace(os.sep,'/'): digest(p)
                               for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='manifest.json'}})
    write_json(folder / 'manifest.json', manifest)
    return {'status': status, 'output_directory': str(folder.resolve()), 'preview': str((folder/'index.html').resolve())}


def pending(folder, original, questions, materials=None):
    write_json(folder / 'source.json', original)
    if materials:
        shutil.copyfile(materials, folder / Path(materials).name)
    write_json(folder / 'questions.json', {'questions': questions})
    return finish(folder, {'status': 'NEEDS_INPUT', 'questions': questions},
                  '材料已保留，尚未绘制定量结果图。请确认：\n' + '\n'.join(f'- {q}' for q in questions))


def patch_source(source, patch):
    """Whitelisted edits; caller rerenders and records every actual changed path."""
    fields(patch, ['changes', 'reason'], 'patch')
    require(isinstance(patch.get('changes'), list) and 1 <= len(patch['changes']) <= 30, 'changes 必须包含 1—30 项')
    result = copy.deepcopy(source)
    changes = []
    for c in patch['changes']:
        fields(c, ['target', 'id', 'set'], 'change')
        target, attrs = c.get('target'), c.get('set')
        require(isinstance(attrs, dict) and bool(attrs), 'set 必须是非空对象')
        if source['kind'] == 'artwork':
            from artwork import EDITABLE
            require(target=='object' and set(attrs)<=EDITABLE,'artwork 补丁只允许视觉属性；科学关系改变需重新确认')
            matches=[o for o in result['objects'] if o['id']==c.get('id')]
            require(len(matches)==1,'修改对象 ID 不存在或不唯一')
            obj=matches[0]
        elif source['kind'] == 'schematic':
            allowed = {'node': {'label','subtitle','color','x','y','w','h','chain_length'},
                       'edge': {'label','color','label_x','label_y','via'},
                       'panel': {'label','color','x','y','w','h'}, 'figure': {'title'}}
            require(target in allowed and set(attrs) <= allowed[target], '修改含不允许的目标或字段')
            if target == 'figure':
                obj = result
            else:
                objects = result.get({'node':'nodes','edge':'edges','panel':'panels'}[target], [])
                matches = [o for o in objects if o['id'] == c.get('id')]
                require(len(matches) == 1, '修改对象 ID 不存在或不唯一')
                obj = matches[0]
        else:
            allowed = {'title','xlabel','ylabel','colors','width_mm','height_mm'}
            require(target == 'figure' and set(attrs) <= allowed, '结果图局部修改仅支持标题、轴标签、颜色和尺寸；数据变化需新任务')
            obj = result
        for key, val in attrs.items():
            old = obj.get(key)
            obj[key] = val
            changes.append({'target':target, 'id':c.get('id'), 'field':key, 'before':old, 'after':val})
    return result, changes
