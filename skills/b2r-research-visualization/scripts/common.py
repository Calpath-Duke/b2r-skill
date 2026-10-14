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


def _rendered_text_and_paths(fig):
    """Observe one actual draw, including order, renderer fonts and rectangular clips.

    Hooks are temporary and restored even on failure. No artist is moved or edited.
    Complex clips, dashed strokes and bitmap interiors are deliberately not inferred.
    """
    from matplotlib.text import Text
    from matplotlib.textpath import TextPath
    from matplotlib.mathtext import MathTextParser
    from matplotlib.transforms import Affine2D, Bbox
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts, strokes, covers, saved = [], [], [], []
    math_parser = MathTextParser('path')
    active, sequence, annotation_arrow = [None], [0], [False]
    def state(gc):
        clip = gc.get_clip_rectangle()
        return {'clip': clip.frozen() if clip is not None else None,
                'complex_clip': gc.get_clip_path()[0] is not None}
    def order():
        sequence[0] += 1
        return sequence[0]
    def hook(obj, name, replacement):
        saved.append((obj, name, name in vars(obj), vars(obj).get(name)))
        setattr(obj, name, replacement)
    original_text, original_path = renderer.draw_text, renderer.draw_path
    def draw_text(gc, x, y, s, prop, angle, ismath=False, mtext=None):
        t = mtext if mtext is not None else active[0]
        if t is not None and gc.get_rgb()[-1] > 0 and s.strip():
            record = {'artist': t, 'order': order(), 'em_pixels': renderer.points_to_pixels(prop.get_size_in_points()),
                      'glyph': None, **state(gc)}
            if ismath:
                # The actual math layout contains smaller script runs. A base
                # Text fontsize alone would miss sub/superscripts below 6 pt.
                parsed = math_parser.parse(s, dpi=renderer.dpi, prop=prop)
                if parsed.glyphs:
                    record['em_pixels'] = min(renderer.points_to_pixels(g[1]) for g in parsed.glyphs)
                else:
                    return original_text(gc, x, y, s, prop, angle, ismath=ismath, mtext=mtext)
            if not ismath and not record['complex_clip']:
                glyph = TextPath((0, 0), s, prop=prop, size=prop.get_size_in_points())
                y_display = renderer.get_canvas_width_height()[1] - y if renderer.flipy() else y
                record['glyph'] = glyph.transformed(Affine2D().scale(renderer.points_to_pixels(1)).rotate_deg(angle).translate(x, y_display))
            texts.append(record)
        return original_text(gc, x, y, s, prop, angle, ismath=ismath, mtext=mtext)
    def draw_path(gc, path, transform, rgbFace=None):
        n = order()
        transformed = path.transformed(transform)
        style = state(gc)
        if rgbFace is not None and len(rgbFace) == 4 and rgbFace[-1] == 1 and gc.get_alpha() == 1:
            covers.append({'path': transformed, 'order': n, **style})
        if (active[0] is None or annotation_arrow[0]) and gc.get_linewidth() > 0 and gc.get_rgb()[-1] > 0 and not gc.get_dashes()[1] and not style['complex_clip']:
            strokes.append({'path': transformed, 'order': n, **style})
        return original_path(gc, path, transform, rgbFace)
    original_image = renderer.draw_image
    def draw_image(gc, x, y, im, *args, **kwargs):
        # An overlaid bitmap can hide a crossing. Its interior is not audited.
        covers.append({'box': Bbox.from_bounds(x, y, im.shape[1], im.shape[0]), 'order': order(), **state(gc)})
        return original_image(gc, x, y, im, *args, **kwargs)
    try:
        hook(renderer, 'draw_text', draw_text)
        hook(renderer, 'draw_path', draw_path)
        hook(renderer, 'draw_image', draw_image)
        for t in fig.findobj(Text):
            arrow = getattr(t, 'arrow_patch', None)
            if arrow is not None:
                arrow_original = arrow.draw
                def draw_arrow(r, original=arrow_original):
                    previous = annotation_arrow[0]; annotation_arrow[0] = True
                    try: return original(r)
                    finally: annotation_arrow[0] = previous
                hook(arrow, 'draw', draw_arrow)
            original = t.draw
            def draw(r, t=t, original=original):
                previous = active[0]; active[0] = t
                try: return original(r)
                finally: active[0] = previous
            hook(t, 'draw', draw)
        fig.canvas.draw()
    finally:
        for obj, name, existed, value in reversed(saved):
            if existed: setattr(obj, name, value)
            else: delattr(obj, name)
    return renderer, texts, strokes, covers


def _segments(path):
    from matplotlib.path import Path as MPath
    start = previous = None
    for point, code in path.iter_segments(curves=False, simplify=False):
        if code == MPath.MOVETO: start = previous = tuple(point)
        elif code == MPath.LINETO:
            current = tuple(point)
            if previous is not None: yield previous, current
            previous = current
        elif code == MPath.CLOSEPOLY and previous is not None and start is not None:
            yield previous, start
            previous = start


def _clipped_segment(a, b, box):
    """Liang-Barsky clipping of an actual stroke centreline."""
    lo, hi = 0., 1.
    dx, dy = b[0]-a[0], b[1]-a[1]
    for p, q in [(-dx,a[0]-box.x0),(dx,box.x1-a[0]),(-dy,a[1]-box.y0),(dy,box.y1-a[1])]:
        if p == 0:
            if q < 0: return None
        elif p < 0: lo = max(lo, q/p)
        else: hi = min(hi, q/p)
    if lo > hi: return None
    return ((a[0]+lo*dx,a[1]+lo*dy),(a[0]+hi*dx,a[1]+hi*dy))


def _intersection(a, b, c, d):
    dx, dy, ex, ey = b[0]-a[0], b[1]-a[1], d[0]-c[0], d[1]-c[1]
    denom = dx*ey-dy*ex
    if abs(denom) < 1e-9: return None  # Coincident/tangent strokes stay uncertain.
    cx, cy = c[0]-a[0], c[1]-a[1]
    t, u = (cx*ey-cy*ex)/denom, (cx*dy-cy*dx)/denom
    return (a[0]+t*dx,a[1]+t*dy) if 0 <= t <= 1 and 0 <= u <= 1 else None


def _covered(point, order, covers):
    for cover in covers:
        if cover['order'] <= order: continue
        if cover['clip'] is not None and not cover['clip'].contains(*point): continue
        if cover['complex_clip']: return True  # Cannot prove this later overlay leaves ink visible.
        if 'box' in cover and cover['box'].contains(*point): return True
        if 'path' in cover and cover['path'].contains_point(point): return True
    return False


def text_checks(fig, final_size_mm=None, min_font_pt=6):
    """Final-size text screening from renderer operations, never scientific QA.

    final_size_mm is only for a known subsequent physical resize; normal exports
    use the Figure's actual physical size. Position transforms do not themselves
    scale Matplotlib Text glyphs. Font em pixels come from the real renderer.
    """
    from matplotlib.transforms import Bbox
    from matplotlib.path import Path as MPath
    renderer, rendered, strokes, covers = _rendered_text_and_paths(fig)
    page = fig.bbox
    size = list(final_size_mm) if final_size_mm is not None else [v*25.4 for v in fig.get_size_inches()]
    require(len(size) == 2, 'final_size_mm 需为 [width, height]')
    for value in size: finite(value, 'final size', 0.01)
    finite(min_font_pt, 'min_font_pt', 0)
    pt_per_pixel = min(size[0]*72/25.4/page.width, size[1]*72/25.4/page.height)
    labels, issues, seen = [], [], set()
    for record in rendered:
        t = record['artist']
        if id(t) in seen: continue
        seen.add(id(t))
        b = t.get_window_extent(renderer)
        tight = t.get_tightbbox(renderer)
        if tight is None or not tight.overlaps(page) or b.width == 0 or b.height == 0: continue
        runs = [r for r in rendered if r['artist'] is t]
        corners = [(b.x0,b.y0),(b.x1,b.y0),(b.x0,b.y1),(b.x1,b.y1)]
        if all(_covered(p, max(r['order'] for r in runs), covers) for p in corners): continue
        if b.x0 < page.x0 - 1 or b.y0 < page.y0 - 1 or b.x1 > page.x1 + 1 or b.y1 > page.y1 + 1:
            issues.append({'kind': 'text_outside_page', 'text': t.get_text()})
        effective = min(r['em_pixels'] for r in runs)*pt_per_pixel
        if effective < min_font_pt-1e-8:
            issues.append({'kind': 'text_small', 'text': t.get_text(), 'effective_font_pt': round(effective, 3), 'threshold_pt': min_font_pt})
        labels.append((t, b))
        crossed = False
        for run in runs:
            glyph = run['glyph']
            if glyph is None: continue
            ink = glyph.get_extents()
            glyph_segments = list(_segments(glyph))
            for stroke in strokes:
                if stroke['order'] <= run['order'] or not ink.overlaps(stroke['path'].get_extents()): continue
                clips = [page] + [c for c in (run['clip'],stroke['clip']) if c is not None]
                clip = Bbox.intersection(clips[0], clips[1]) if len(clips)>1 else page
                for c in clips[2:]: clip = Bbox.intersection(clip, c) if clip is not None else None
                if clip is None: continue
                for a,b_ in _segments(stroke['path']):
                    segment = _clipped_segment(a,b_,clip)
                    if segment is None or not MPath(segment).intersects_path(glyph, filled=False): continue
                    hits = [p for c,d in glyph_segments if (p := _intersection(*segment,c,d)) is not None and not _covered(p, stroke['order'], covers)]
                    if len(hits)>1 and any(math.dist(hits[0],p)>1 for p in hits[1:]):
                        issues.append({'kind':'text_crossed_by_line','text':t.get_text(),
                                       'basis':'visible solid stroke drawn after text intersects actual glyph outlines',
                                       'draw_order':stroke['order']})
                        crossed = True; break
                if crossed: break
            if crossed: break
    for i, (a, ba) in enumerate(labels):
        for b, bb in labels[i+1:]:
            if ba.overlaps(bb):
                issues.append({'kind': 'text_overlap', 'texts': [a.get_text(), b.get_text()]})
    return {'screening': 'REVIEW_REQUIRED' if issues else 'NO_TEXT_BOUND_ISSUES_DETECTED',
            'issues': issues, 'manual_visual_review': 'PENDING', 'scientific_review': 'PENDING',
            'final_size_mm': size, 'rendered_text_objects': len(labels),
            'notice': '最终物理尺寸、实际渲染字体（含 mathtext 子/上标）与有限字形交叉筛查；复杂裁切、虚线、数学字形压线、路径特效、外部 TeX 及位图内部需人工查看，不是全面排版或科学认证。'}


def verify_files(folder, *, raster_pdf=False):
    """Integrity and actual structure only; these properties are never a QA PASS.

    raster_pdf is used only by capture's known bitmap-to-PDF producer. Arbitrary
    PDF streams are not classified as vector/editable from their suffix/header.
    """
    import xml.etree.ElementTree as ET
    import base64
    import io
    from PIL import Image
    from fontTools.ttLib import TTFont
    details = {}
    for name in ['figure.svg', 'figure-outlined.svg']:
        if not (folder / name).is_file(): continue
        tree = ET.parse(folder / name)
        require(tree.getroot().tag.rsplit('}', 1)[-1] == 'svg', 'XML 根节点不是 SVG')
        texts = tree.findall('.//{http://www.w3.org/2000/svg}text')
        with TTFont(FONT) as font:
            cmap = font.getBestCmap()
            missing = sorted({c for t in texts for c in ''.join(t.itertext()) if ord(c) not in cmap and not c.isspace()})
        require(not missing, f'字体不支持字符：{" ".join(missing)}')
        rasters = len(tree.findall('.//{http://www.w3.org/2000/svg}image'))
        verified_rasters = 0
        for image in tree.findall('.//{http://www.w3.org/2000/svg}image'):
            href = image.get('href') or image.get('{http://www.w3.org/1999/xlink}href', '')
            if href.startswith('data:') and ';base64,' in href:
                try:
                    with Image.open(io.BytesIO(base64.b64decode(''.join(href.split(',', 1)[1].split()), validate=True))) as asset:
                        asset.verify()
                        verified_rasters += 1
                except (ValueError, OSError):
                    pass  # External/vector/unknown assets never justify an all-vector claim.
        vectors = sum(e.tag.rsplit('}', 1)[-1] in
                      {'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'use'}
                      for e in tree.iter())
        details[name] = {'parsed': True, 'text_elements': len(texts),
                         'vector_elements': vectors, 'raster_elements': rasters,
                         'verified_embedded_raster_elements': verified_rasters,
                         'content_kind': 'MIXED_SVG_WITH_RASTER_ASSETS' if verified_rasters else
                                         'SVG_WITH_UNCLASSIFIED_IMAGE_ASSETS' if rasters else
                                         'NATIVE_VECTOR_SVG' if vectors or texts else 'SVG_NO_RENDERABLE_ELEMENTS',
                         'editability': {'text_elements_present': bool(texts),
                                         'vector_elements_present': bool(vectors),
                                         'embedded_raster_editable': False},
                         'auditability': {'text_layout': 'PARTIAL' if rasters and texts else
                                          'STRUCTURED_TEXT_AVAILABLE' if texts else 'NOT_AUDITABLE',
                                          'internal_geometry': 'PARTIAL' if rasters and vectors else
                                          'NOT_AUDITABLE' if rasters else 'STRUCTURED_VECTOR_AVAILABLE'},
                         'notice': 'Structure counts include definitions; presence does not prove full editability or a completed visual/scientific review.'}
    if (folder / 'figure.png').is_file():
        with Image.open(folder / 'figure.png') as im:
            im.load()
            details['figure.png'] = {'decoded': True, 'pixels': list(im.size),
                                    'content_kind': 'RASTER_'+im.format,
                                    'editability': {'independent_text_or_vectors': False},
                                    'auditability': {'text_layout': 'NOT_AUDITABLE', 'internal_geometry': 'NOT_AUDITABLE'}}
    if (folder / 'figure.pdf').is_file():
        payload = (folder / 'figure.pdf').read_bytes()
        require(payload.startswith(b'%PDF-') and b'%%EOF' in payload[-1024:], 'PDF 文件不完整')
        if raster_pdf:
            require(re.search(rb'/Subtype\s*/Image\b', payload), '位图 PDF 未找到图像 XObject')
        details['figure.pdf'] = {'header_and_eof_checked': True,
                                 'content_kind': 'RASTER_ONLY_PDF' if raster_pdf else 'PDF_CONTENT_NOT_CLASSIFIED',
                                 'classification_basis': 'known capture bitmap export + image XObject' if raster_pdf else 'header/EOF only; no PDF content parser',
                                 'editability': {'independent_text_or_vectors': False if raster_pdf else 'NOT_VERIFIED'},
                                 'auditability': {'text_layout': 'NOT_AUDITABLE' if raster_pdf else 'NOT_VERIFIED',
                                                  'internal_geometry': 'NOT_AUDITABLE' if raster_pdf else 'NOT_VERIFIED'}}
    return details


def finish(folder, manifest, notes, qa=None):
    if qa is not None:
        qa['file_checks'] = verify_files(folder)
        qa['auditability'] = {name: check['auditability'] for name, check in qa['file_checks'].items()}
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
