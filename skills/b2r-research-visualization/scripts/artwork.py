"""Layered scientific artwork: exact vector labels/relations + optional host assets.

Not a biological ontology or a replacement for host image generation. The host
interprets natural language; this module gives its edits concrete, stable objects.
"""
from __future__ import annotations
import math
import shutil
from pathlib import Path

from common import (require, fields, finite, text_value, color, checked_input_file,
                    write_json, digest, matplotlib_setup, export, text_checks,
                    package_replay, finish)
from schematic import evidence, uncertain

TYPES = {'region','ellipse','text','membrane','receptor','protein','chain','image','arrow','line'}
BASE = {'id','type','role','aliases','x','y','w','h','z','fill','stroke','line_width',
        'text','font_size','align','asset','points','from','to','relation','evidence',
        'sources','via','attachment','chain_length','label','opacity'}
EDITABLE = {'x','y','w','h','z','fill','stroke','line_width','text','font_size','align',
            'asset','points','via','chain_length','opacity'}


def asset_path(root, name):
    p=Path(name)
    require(not p.is_absolute() and '..' not in p.parts, '素材必须是制作目录内的相对路径')
    root=Path(root).resolve()
    target=checked_input_file(root/p)
    require(target.is_relative_to(root), '素材不能越过制作目录')
    return target


def validate(spec, assets=None):
    fields(spec,['kind','title','purpose','language','canvas','objects','sources','notes','materials','calls'], 'artwork')
    require(spec.get('kind')=='artwork','kind 必须是 artwork')
    for key in ['title','purpose']: text_value(spec.get(key),key,500)
    require(spec.get('language') in ['zh','en','bilingual'],'language 不合法')
    c=spec.get('canvas',{});fields(c,['width','height','width_mm','height_mm'],'canvas')
    w=finite(c.get('width'), 'width',300,5000);h=finite(c.get('height'),'height',200,4000)
    finite(c.get('width_mm',260),'width_mm',60,600);finite(c.get('height_mm',160),'height_mm',40,600)
    source_ids=set()
    for s in spec.get('sources',[]):
        fields(s,['id','citation','locator','excerpt','verified'],'source')
        for k in ['id','citation','locator','excerpt']: text_value(s.get(k),'source.'+k,5000)
        require(s['id'] not in source_ids,'重复来源 ID');source_ids.add(s['id'])
        require(isinstance(s.get('verified'),bool),'verified 只表示摘录已核对')
    require(isinstance(spec.get('objects'),list) and 1<=len(spec['objects'])<=150,'objects 需有 1—150 项')
    objects={}
    for o in spec['objects']:
        fields(o,BASE,'object');ident=text_value(o.get('id'),'id',80)
        require(ident.replace('-','').replace('_','').isalnum() and ident not in objects,'对象 ID 无效或重复')
        objects[ident]=o
        require(o.get('type') in TYPES,'不支持的 object.type；可另用任务专属 SVG/脚本')
        text_value(o.get('role',ident),'role',200)
        require(isinstance(o.get('aliases',[]),list) and all(isinstance(a,str) for a in o.get('aliases',[])),'aliases 必须是文本列表')
        for k in ['fill','stroke']:
            if k in o: color(o[k])
        for k in ['x','y']: finite(o.get(k,0),k,0,w if k=='x' else h)
        for k in ['w','h']:
            if k in o: finite(o[k],k,1,w if k=='w' else h)
        if o['type'] not in {'arrow','line','text'}:
            require(o.get('w',0)>0 and o.get('h',0)>0,'形状/素材需要 w,h')
            require(o['x']-o['w']/2>=0 and o['x']+o['w']/2<=w and o['y']-o['h']/2>=0 and o['y']+o['h']/2<=h,'对象越出画布')
        finite(o.get('opacity',1),'opacity',0,1)
        finite(o.get('font_size',11),'font_size',3,60)
        finite(o.get('z',3),'z',0,100)
        finite(o.get('line_width',1.2),'line_width',0,12)
        if o['type']=='text': text_value(o.get('text'),'text',1000)
        if o['type']=='image':
            text_value(o.get('asset'),'asset',400)
            if assets is not None: asset_path(assets,o['asset'])
        if o['type']=='chain':
            require(isinstance(o.get('chain_length',8),int) and not isinstance(o.get('chain_length',8),bool) and 2<=o.get('chain_length',8)<=40,'chain_length 需为 2—40 整数')
        if o['type']=='arrow':
            evidence(o,source_ids)
            require(o.get('relation') in {'activation','inhibition','association','flow'},'relation 不合法')
            require(o['evidence']!='visual_simplification' or o['relation'] in {'association','flow'},'视觉简化不能支持因果关系')
        if o['type']=='line': require(len(o.get('points',[]))>=2,'line 需要两个点')
        for p in o.get('points',[])+o.get('via',[]):
            require(isinstance(p,list) and len(p)==2,'点须为 [x,y]')
            finite(p[0],'point.x',0,w);finite(p[1],'point.y',0,h)
    for o in objects.values():
        if o['type']=='arrow':
            require(o.get('from') in objects and o.get('to') in objects and o['from']!=o['to'],'箭头对象无效')
            require(all(objects[o[k]]['type'] not in {'text','arrow','line'} for k in ['from','to']),'箭头需连接有面积的对象')
        a=o.get('attachment')
        if a:
            fields(a,['target','mode'],'attachment');require(a.get('target') in objects and a['target']!=o['id'],'attachment 对象无效')
            target=objects[a['target']]
            require(a.get('mode') in {'inside','on_membrane'},'attachment.mode 不合法')
            if a['mode']=='on_membrane':
                require(target['type']=='membrane','on_membrane 必须指定膜')
                require(abs(o['x']-target['x'])<=target['w']/2 and abs(o['y']-target['y'])<=target['h']/2,'受体需与指定膜相交')
            else:
                require(abs(o['x']-target['x'])+o.get('w',0)/2<=target['w']/2 and abs(o['y']-target['y'])+o.get('h',0)/2<=target['h']/2,'inside 对象需在容器的边界内')
    return w,h


def object_map(spec):
    return [{'id':o['id'],'role':o.get('role',o['id']),'aliases':o.get('aliases',[]),
             'type':o['type'],'text':o.get('text'),
             'bounds':[o.get('x',0)-o.get('w',0)/2,o.get('y',0)-o.get('h',0)/2,o.get('w',0),o.get('h',0)],
             'editability':'bitmap interior requires host image editing; placement is direct' if o['type']=='image' else 'direct vector object',
             'attachment':o.get('attachment')} for o in spec['objects']]


def endpoint(o,toward):
    dx,dy=toward[0]-o['x'],toward[1]-o['y']
    require(dx or dy,'箭头折点不能等于对象中心')
    rw,rh=o['w']/2+5,o['h']/2+5
    if o['type'] in {'ellipse','protein'}:
        t=1/math.sqrt((dx/rw)**2+(dy/rh)**2)
    else: t=min(rw/abs(dx) if dx else math.inf,rh/abs(dy) if dy else math.inf)
    return o['x']+t*dx,o['y']+t*dy


def render(spec, assets, folder, changes=None, parent=None):
    w,h=validate(spec,assets);plt=matplotlib_setup()
    from matplotlib.patches import FancyBboxPatch,Ellipse,Circle,PathPatch,FancyArrowPatch
    from matplotlib.path import Path as MPath
    from PIL import Image
    import numpy as np
    c=spec['canvas'];fig=plt.figure(figsize=(c.get('width_mm',260)/25.4,c.get('height_mm',160)/25.4))
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,w),ylim=(h,0));ax.axis('off')
    objects={o['id']:o for o in spec['objects']};rasters=[]
    for o in sorted(spec['objects'],key=lambda o:o.get('z',3)):
        kind=o['type'];x=o.get('x',0);y=o.get('y',0);ow=o.get('w',0);oh=o.get('h',0)
        fill=o.get('fill','#DDECF0');stroke=o.get('stroke','#537487');gid='object-'+o['id']
        kw={'zorder':o.get('z',3),'alpha':o.get('opacity',1),'gid':gid}
        style={'facecolor':fill,'edgecolor':stroke,'lw':o.get('line_width',1.2),**kw}
        if kind=='region': ax.add_patch(FancyBboxPatch((x-ow/2,y-oh/2),ow,oh,boxstyle='round,pad=0,rounding_size=22',**style))
        elif kind=='ellipse': ax.add_patch(Ellipse((x,y),ow,oh,**style))
        elif kind=='text': ax.text(x,y,o['text'],fontsize=o.get('font_size',11),ha=o.get('align','center'),va='center',color=fill,linespacing=1.5,**kw)
        elif kind=='image':
            source=asset_path(assets,o['asset']);target=folder/o['asset'];target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists(): shutil.copyfile(source,target)
            with Image.open(target) as im:
                im.load();array=np.asarray(im.convert('RGBA'))
                rasters.append({'id':o['id'],'file':o['asset'],'sha256':digest(target),'pixels':list(im.size),'editability':'bitmap interior; independent vector labels/arrows are separate'})
            ax.imshow(array,extent=[x-ow/2,x+ow/2,y+oh/2,y-oh/2],aspect='auto',interpolation='lanczos',**kw)
        elif kind=='protein':
            points=[]
            for i in range(120):
                angle=2*math.pi*i/119;r=1+.055*math.sin(5*angle)+.025*math.cos(9*angle)
                points.append((x+ow*.46*r*math.cos(angle),y+oh*.46*r*math.sin(angle)))
            ax.add_patch(PathPatch(MPath(points,[MPath.MOVETO]+[MPath.LINETO]*118+[MPath.CLOSEPOLY]),**style))
        elif kind=='receptor':
            # One membrane-spanning stem and two extracellular arms; a visual symbol.
            path=MPath([(x,y+oh*.47),(x,y-oh*.03),(x-ow*.37,y-oh*.45),(x-ow*.46,y-oh*.36),
                        (x,y+oh*.04),(x+ow*.46,y-oh*.36),(x+ow*.37,y-oh*.45),(x,y-oh*.03)],
                       [MPath.MOVETO,MPath.LINETO,MPath.LINETO,MPath.LINETO,MPath.MOVETO,MPath.LINETO,MPath.LINETO,MPath.MOVETO])
            ax.add_patch(PathPatch(path,facecolor='none',edgecolor=stroke,lw=10,capstyle='round',joinstyle='round',**kw))
            ax.add_patch(PathPatch(path,facecolor='none',edgecolor=fill,lw=6,capstyle='round',joinstyle='round',**{**kw,'gid':gid+'-highlight'}))
        elif kind=='membrane':
            n=max(8,int(ow/23));r=min(8,oh*.12)
            for i in range(n):
                px=x-ow/2+(i+.5)*ow/n
                for side in [-1,1]:
                    py=y+side*oh*.38
                    ax.add_patch(Circle((px,py),r,**{**style,'lw':.65,'gid':f'{gid}-head-{i}-{side}'}))
                    for j in [-1,1]:
                        ax.plot([px+j*2,px+j*4,px+j*2],[py-side*r,py-side*oh*.26,y+side*2],color=stroke,lw=.6,**{**kw,'gid':f'{gid}-tail-{i}-{side}-{j}'})
        elif kind=='chain':
            n=o.get('chain_length',8);points=[(x-ow/2+i*ow/(n-1),y+(-1)**i*oh*.25) for i in range(n)]
            ax.plot(*zip(*points),color=stroke,lw=1.5,**kw)
            for i,(px,py) in enumerate(points): ax.add_patch(Circle((px,py),min(oh*.18,ow/n*.25),**{**style,'gid':gid+f'-bead-{i}'}))
        elif kind=='line': ax.plot(*zip(*o['points']),color=stroke,lw=o.get('line_width',1.2),**kw)
        elif kind=='arrow':
            a,b=objects[o['from']],objects[o['to']];via=o.get('via',[])
            points=[endpoint(a,via[0] if via else (b['x'],b['y']))]+[tuple(p) for p in via]+[endpoint(b,via[-1] if via else (a['x'],a['y']))]
            path=MPath(points,[MPath.MOVETO]+[MPath.LINETO]*(len(points)-1))
            ax.add_patch(FancyArrowPatch(path=path,arrowstyle={'activation':'-|>','flow':'-|>','inhibition':'-[','association':'-'}[o['relation']],mutation_scale=12,lw=o.get('line_width',1.5),color=stroke,linestyle=(0,(4,3)) if uncertain(o,spec) else '-',**kw))
    qa=text_checks(fig);export(fig,folder,{'kind':'artwork','source':'source.json','evidence':'evidence.json','raster_assets':rasters})
    mapping=object_map(spec)
    with Image.open(folder/'figure.png') as preview: pw,ph=preview.size
    sx,sy=pw/fig.bbox.width,ph/fig.bbox.height
    artists={a.get_gid():a for a in fig.findobj() if hasattr(a,'get_gid') and a.get_gid()}
    for entry in mapping:
        artist=artists.get('object-'+entry['id'])
        if artist is not None:
            b=artist.get_window_extent(fig.canvas.get_renderer())
            entry['rendered_bounds_pixels']=[b.x0*sx,ph-b.y1*sy,b.x1*sx,ph-b.y0*sy]
    plt.close(fig)
    write_json(folder/'source.json',spec);write_json(folder/'objects.json',mapping)
    write_json(folder/'evidence.json',{'materials':spec.get('materials',[]),'sources':spec.get('sources',[]),'relationships':[o for o in spec['objects'] if o['type']=='arrow'],'notes':spec.get('notes',[]),'source_verification_is_not_hypothesis':True})
    write_json(folder/'calls.json',{'calls':spec.get('calls',[]),'notice':'Host-provided trace; a prompt alone is not proof of a successful call.'})
    if changes is not None: write_json(folder/'changes.json',{'parent':parent,'changes':changes})
    package_replay(folder,'artwork')
    notes='图件已生成。可直接说“修改某个标签/箭头/位置”，由宿主定位 objects.json 对象并保存新版。\n文字和箭头为独立矢量；位图素材内部需要图片编辑，详见 manifest.json。\n待确认：'+ ('；'.join(spec.get('notes',[])) or '专家科学复核尚未进行。')
    return finish(folder,{'status':'GENERATED_REVIEW_PENDING','kind':'artwork','parent':parent,'editability':{'text':'independent SVG text','arrows':'independent vector paths','layout':'source.json objects','raster_assets':rasters},'science_review':'PENDING'},notes,qa)
