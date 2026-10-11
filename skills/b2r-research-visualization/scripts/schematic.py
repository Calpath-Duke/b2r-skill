"""Source-backed editable vector diagrams. Coordinates use a top-left canvas."""
from __future__ import annotations

import math
import textwrap

from common import (CliError, require, finite, fields, text_value, color, write_json,
                    matplotlib_setup, export, text_checks, finish)

STATUSES = {'user_confirmed', 'user_hypothesis', 'source_explicit', 'author_hypothesis', 'ai_inference', 'visual_simplification'}
STATUS_ZH = {'user_confirmed':'用户确认', 'user_hypothesis':'用户明确提出的假设', 'source_explicit':'来源明确陈述',
             'author_hypothesis':'作者假设', 'ai_inference':'AI 推断，待确认', 'visual_simplification':'视觉简化'}


def uncertain(obj,spec):
    # Checking a quotation is different from the epistemic status of a relation.
    return obj['evidence'] in {'user_hypothesis','author_hypothesis','ai_inference'}


def evidence(obj, sources):
    require(obj.get('evidence') in STATUSES, f"{obj.get('id')} 缺少合法 evidence 状态")
    refs = obj.get('sources', [])
    require(isinstance(refs, list) and all(r in sources for r in refs), '来源 ID 未定义')
    if obj['evidence'] in {'source_explicit', 'author_hypothesis'}:
        require(bool(refs), f"{obj['id']} 来源陈述/作者假设必须关联来源")


def validate(spec):
    fields(spec, ['kind','title','purpose','language','canvas','nodes','edges','panels','sources','notes'], '示意图')
    require(spec.get('kind') == 'schematic', 'kind 必须是 schematic')
    text_value(spec.get('title'), 'title', 180)
    text_value(spec.get('purpose'), 'purpose', 80)
    require(spec.get('language') in ['zh','en','bilingual'], '指定图内 language: zh/en/bilingual')
    canvas = spec.get('canvas', {})
    fields(canvas, ['width','height','width_mm','height_mm'], 'canvas')
    w = finite(canvas.get('width',1200), 'canvas.width',400,2400)
    h = finite(canvas.get('height',700), 'canvas.height',300,1600)
    finite(canvas.get('width_mm',240), 'canvas.width_mm',80,400)
    finite(canvas.get('height_mm',140), 'canvas.height_mm',60,400)
    source_ids = set()
    for s in spec.get('sources', []):
        fields(s, ['id','citation','locator','excerpt','verified'], 'source')
        sid = text_value(s.get('id'), 'source.id',80)
        require(sid not in source_ids, '来源 ID 重复')
        source_ids.add(sid)
        for k in ['citation','locator','excerpt']:
            text_value(s.get(k), f'source.{k}',3000)
        require(isinstance(s.get('verified'), bool), 'source.verified 只表示宿主核对过该定位与摘录')
    ids, boxes = set(), []
    require(isinstance(spec.get('nodes'), list) and 1<=len(spec['nodes'])<=30, 'nodes 必须有 1—30 个元素')
    for n in spec['nodes']:
        fields(n, ['id','label','subtitle','x','y','w','h','color','shape','chain_length','evidence','sources'], 'node')
        ident = text_value(n.get('id'), 'node.id',80)
        require(ident not in ids, '节点 ID 重复')
        require(ident.replace('-','').replace('_','').isalnum(), 'ID 仅允许字母数字、下划线、连字符')
        ids.add(ident)
        text_value(n.get('label'), 'node.label',180)
        if n.get('subtitle'):
            text_value(n['subtitle'], 'subtitle',180)
        evidence(n, source_ids)
        require(n.get('shape','box') in ['box','ellipse','chain'], 'shape 只支持 box/ellipse/chain')
        if n.get('shape') == 'chain':
            v=n.get('chain_length',8)
            require(isinstance(v,int) and not isinstance(v,bool) and 2<=v<=30, 'chain_length 必须是 2—30 整数')
        color(n.get('color','#DDECF5'))
        x,y = finite(n.get('x'),'node.x',0,w),finite(n.get('y'),'node.y',0,h)
        nw,nh = finite(n.get('w',190),'node.w',40,w),finite(n.get('h',90),'node.h',40,h)
        require(x-nw/2>=16 and x+nw/2<=w-16 and y-nh/2>=95 and y+nh/2<=h-85,
                f'{ident} 越界或占用标题/图例区域')
        b=(x-nw/2,y-nh/2,x+nw/2,y+nh/2)
        for other, ob in boxes:
            require(not(b[0]<ob[2] and b[2]>ob[0] and b[1]<ob[3] and b[3]>ob[1]),
                    f'节点 {ident} 与 {other} 重叠；请调整布局')
        boxes.append((ident,b))
    edge_ids=set()
    require(isinstance(spec.get('edges',[]),list) and len(spec.get('edges',[]))<=60,'edges 最多 60 条')
    for e in spec.get('edges',[]):
        fields(e, ['id','from','to','relation','label','color','label_x','label_y','via','evidence','sources'], 'edge')
        eid=text_value(e.get('id'),'edge.id',80)
        require(eid not in edge_ids and eid not in ids, '边 ID 重复或与节点冲突')
        edge_ids.add(eid)
        require(e.get('from') in ids and e.get('to') in ids and e['from']!=e['to'], '箭头端点无效')
        require(e.get('relation') in ['activation','inhibition','association','flow'], 'relation 不合法')
        evidence(e,source_ids)
        require(e['evidence']!='visual_simplification' or e['relation'] in {'association','flow'},
                '方向性科学关系不能仅以 visual_simplification 作为证据')
        color(e.get('color','#425B72'))
        if e.get('label'):
            text_value(e['label'],'edge.label',120)
        for key,upper in [('label_x',w),('label_y',h)]:
            if key in e: finite(e[key],key,0,upper)
        via=e.get('via',[])
        require(isinstance(via,list) and len(via)<=8,'via 最多 8 个折点')
        for p in via:
            require(isinstance(p,list) and len(p)==2,'via 折点是 [x,y]')
            finite(p[0],'via.x',0,w);finite(p[1],'via.y',0,h)
    panel_ids=set()
    require(isinstance(spec.get('panels',[]),list) and len(spec.get('panels',[]))<=10,'panels 最多 10 个')
    for p in spec.get('panels',[]):
        fields(p,['id','label','x','y','w','h','color'],'panel')
        pid=text_value(p.get('id'),'panel.id',80)
        require(pid not in panel_ids and pid not in ids|edge_ids,'分区 ID 冲突')
        panel_ids.add(pid)
        text_value(p.get('label'),'panel.label',100)
        color(p.get('color','#F5F8FB'))
        for key,upper in [('x',w),('y',h),('w',w),('h',h)]: finite(p.get(key),'panel.'+key,0,upper)
        require(p['x']+p['w']<=w-8 and p['y']+p['h']<=h-65,'分区越界')
    return w,h


def boundary(n, toward):
    x,y=n['x'],n['y']
    dx,dy=toward[0]-x,toward[1]-y
    require(dx!=0 or dy!=0,'箭头折点不能与端点节点中心重合')
    rw,rh=n.get('w',190)/2+4,n.get('h',90)/2+4
    if n.get('shape')=='ellipse':
        f=1/math.sqrt((dx/rw)**2+(dy/rh)**2)
    else:
        f=min(rw/abs(dx) if dx else float('inf'),rh/abs(dy) if dy else float('inf'))
    return x+dx*f,y+dy*f


def render(spec, folder, changes=None, parent=None):
    w,h=validate(spec)
    plt=matplotlib_setup()
    from matplotlib.patches import FancyBboxPatch, Ellipse, FancyArrowPatch, Circle
    from matplotlib.lines import Line2D
    from matplotlib.path import Path as MPath
    fig=plt.figure(figsize=(spec.get('canvas',{}).get('width_mm',240)/25.4,
                            spec.get('canvas',{}).get('height_mm',140)/25.4))
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,w),ylim=(h,0));ax.axis('off')
    en=spec['language']=='en'
    ax.text(40,38,spec['title'],fontsize=17,va='center',gid='figure-title')
    draft=any(uncertain(o,spec) for o in spec['nodes']+spec.get('edges',[]))
    subtitle=('SOURCE-ANNOTATED STRUCTURE DRAFT' if en else '附来源的结构草案') if draft else ('CONFIRMED RELATIONSHIPS · REVIEW PENDING' if en else '按已提供关系绘制 · 科学复核待完成')
    ax.text(40,73,subtitle,fontsize=8.5,color='#66778A',gid='figure-subtitle')
    for p in spec.get('panels',[]):
        patch=FancyBboxPatch((p['x'],p['y']),p['w'],p['h'],boxstyle='round,pad=0,rounding_size=14',
                             facecolor=p.get('color','#F5F8FB'),edgecolor='#DDE5EC',lw=.8,gid='panel-'+p['id'])
        ax.add_patch(patch)
        ax.text(p['x']+18,p['y']+24,p['label'],fontsize=10,color='#65758A',va='center',gid='panel-label-'+p['id'])
    nodes={n['id']:n for n in spec['nodes']}
    for e in spec.get('edges',[]):
        a,b=nodes[e['from']],nodes[e['to']]
        via=e.get('via',[])
        start=boundary(a,via[0] if via else (b['x'],b['y']))
        end=boundary(b,via[-1] if via else (a['x'],a['y']))
        points=[start]+[tuple(p) for p in via]+[end]
        is_uncertain=uncertain(e,spec)
        style={'activation':'-|>','flow':'-|>','inhibition':'-[','association':'-'}[e['relation']]
        arrow=FancyArrowPatch(path=MPath(points,[MPath.MOVETO]+[MPath.LINETO]*(len(points)-1)),
                              arrowstyle=style,mutation_scale=12,lw=1.5,
                              linestyle=(0,(4,3)) if is_uncertain else '-',color=e.get('color','#425B72'),
                              zorder=2,gid='edge-'+e['id'])
        ax.add_patch(arrow)
        if e.get('label'):
            mx=e.get('label_x',(start[0]+end[0])/2)
            my=e.get('label_y',(start[1]+end[1])/2-16)
            label=e['label']+(' ?' if is_uncertain else '')
            ax.text(mx,my,label,ha='center',va='center',fontsize=9,
                    bbox={'facecolor':'white','edgecolor':'none','pad':2},zorder=4,gid='edge-label-'+e['id'])
    inside=[]
    for n in spec['nodes']:
        x,y,nw,nh=n['x'],n['y'],n.get('w',190),n.get('h',90)
        is_uncertain=uncertain(n,spec)
        options=dict(facecolor=n.get('color','#DDECF5'),edgecolor='#74899D',lw=1,
                     linestyle='--' if is_uncertain else '-',zorder=3,gid='node-'+n['id'])
        if n.get('shape')=='ellipse':
            patch=Ellipse((x,y),nw,nh,**options)
        else:
            patch=FancyBboxPatch((x-nw/2,y-nh/2),nw,nh,boxstyle='round,pad=0,rounding_size=12',**options)
        ax.add_patch(patch)
        if n.get('shape')=='chain':
            length=n.get('chain_length',8)
            for i in range(length):
                cx=x-nw*.36+i*nw*.72/(length-1)
                cy=y-nh*.21+(i%2)*nh*.10
                if i:
                    ax.plot([previous[0],cx],[previous[1],cy],lw=1.3,color='#6C5894',zorder=4,gid=f'chain-bond-{n["id"]}-{i}')
                ax.add_patch(Circle((cx,cy),min(nh*.07,nw*.22/length),facecolor='#8C79B4',edgecolor='white',lw=.6,zorder=5,gid=f'chain-{n["id"]}-{i}'))
                previous=(cx,cy)
        label=n['label']+(' ?' if is_uncertain else '')
        label_y=y+(nh*.19 if n.get('shape')=='chain' else (-nh*.10 if n.get('subtitle') else 0))
        t=ax.text(x,label_y,label,fontsize=11,ha='center',va='center',zorder=5,gid='node-label-'+n['id'])
        inside.append((t,n))
        if n.get('subtitle'):
            t=ax.text(x,y+nh*.25,n['subtitle'],fontsize=8,ha='center',va='center',color='#4B6075',zorder=5,gid='node-subtitle-'+n['id'])
            inside.append((t,n))
    legend=[Line2D([0],[0],color='#425B72',lw=1.5,label='Provided / confirmed' if en else '已提供 / 已确认'),
            Line2D([0],[0],color='#425B72',lw=1.5,ls='--',label='Hypothesis / inference ?' if en else '假设 / 推断 ?')]
    ax.legend(handles=legend,loc='lower left',bbox_to_anchor=(.026,.025),ncol=2,frameon=False,fontsize=8.5)
    qa=text_checks(fig)
    for t,n in inside:
        b=t.get_window_extent(fig.canvas.get_renderer())
        corners=ax.transData.transform([(n['x']-n.get('w',190)/2+9,n['y']-n.get('h',90)/2+9),
                                       (n['x']+n.get('w',190)/2-9,n['y']+n.get('h',90)/2-9)])
        xmin,xmax=sorted(corners[:,0]);ymin,ymax=sorted(corners[:,1])
        if b.x0<xmin or b.x1>xmax or b.y0<ymin or b.y1>ymax:
            qa['issues'].append({'kind':'label_outside_node','node':n['id'],'text':t.get_text()})
    qa['screening']='REVIEW_REQUIRED' if qa['issues'] else 'NO_TEXT_BOUND_ISSUES_DETECTED'
    ledger={'sources':spec.get('sources',[]), 'items':[
        {'id':o['id'],'type':typ,'label':o.get('label',''),'evidence':o['evidence'],
         'evidence_label':STATUS_ZH[o['evidence']],'sources':o.get('sources',[])}
        for typ,objects in [('node',spec['nodes']),('edge',spec.get('edges',[]))] for o in objects],
        'notice':'来源定位与摘录由宿主提供；本地脚本不验证论文真伪或机制正确性。'}
    provenance={'kind':'schematic','input':'source.json','evidence':'evidence.json','purpose':spec['purpose'],
                'language':spec['language'],'scientific_review':'PENDING','raster_assets':[]}
    export(fig,folder,provenance)
    plt.close(fig)
    write_json(folder/'source.json',spec);write_json(folder/'evidence.json',ledger)
    if changes is not None: write_json(folder/'changes.json',{'parent':parent,'changes':changes})
    from common import package_replay
    package_replay(folder,'schematic')
    status='DRAFT_REVIEW_PENDING' if draft else 'GENERATED_REVIEW_PENDING'
    manifest={'status':status,'kind':'schematic','purpose':spec['purpose'],'parent':parent,
              'editability':{'text':'figure.svg: independent text, font-dependent',
                             'arrows':'independent vector paths with stable edge IDs',
                             'shapes':'independent paths; layout in source.json',
                             'outlined':'figure-outlined.svg: glyph paths, appearance preserved, text not semantic',
                             'raster_assets':[]},'limitations':spec.get('notes',[])}
    notes='生成了可继续修改的机制结构草图。\n可直接说“只改某个标签/颜色/位置”，由宿主修改制作源并保存新版。\n文字、箭头、图形独立；无嵌入位图。假设/推断用虚线与问号，科学复核仍待完成。\n这是矢量结构草图；精细插画需另走宿主生图或专业制作路径。字体和制作记录见附带文件。'
    if qa['issues']: notes+='\n自动边界检查发现布局问题，详见 qa.json；请修正后使用。'
    return finish(folder,manifest,notes,qa)
