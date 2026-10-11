"""Compose existing SVG panel deliveries without flattening their vector layers."""
from __future__ import annotations
import re
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from common import (require,fields,finite,text_value,write_json,matplotlib_setup,
                    export,text_checks,finish,package_replay)
from artwork import asset_path

SVG='http://www.w3.org/2000/svg'
ET.register_namespace('',SVG)
ET.register_namespace('xlink','http://www.w3.org/1999/xlink')


def merge(base,panels,folder,outlined=False):
    tree=ET.parse(base);root=tree.getroot()
    width,height=map(float,root.get('viewBox').split()[2:])
    cw,ch=panels['canvas']['width'],panels['canvas']['height']
    for p in panels['panels']:
        name='figure-outlined.svg' if outlined else 'figure.svg'
        node=ET.parse(folder/p['source']/name).getroot()
        # Reject active/external content; inputs must be self-contained SVG exports.
        ids={e.get('id'):p['id']+'-'+e.get('id') for e in node.iter() if e.get('id')}
        for e in node.iter():
            require(e.tag.rsplit('}',1)[-1] not in {'script','foreignObject'},'面板 SVG 含可执行内容')
            css=' '.join(list(e.attrib.values())+[e.text or ''])
            require('@import' not in css.lower(),'面板 SVG 含外部样式导入')
            require(all(v.strip(' \"\'').startswith('#') for v in re.findall(r'url\(([^)]+)\)',css,re.I)),'面板 SVG 含非内部 URL 引用')
            for key,val in list(e.attrib.items()):
                require(not key.lower().startswith('on'),'面板 SVG 含事件处理器')
                if key.endswith('href'): require(val.startswith(('#','data:image/png;','data:image/jpeg;')),'面板 SVG 不能引用外部文件/地址或嵌套活动图像')
                if key=='id': e.set(key,ids[val]);continue
                for old,new in ids.items():
                    val=val.replace('url(#'+old+')','url(#'+new+')')
                    if val=='#'+old: val='#'+new
                e.set(key,val)
        node.set('x',str(p['x']*width/cw));node.set('y',str(p['y']*height/ch))
        node.set('width',str(p['w']*width/cw));node.set('height',str(p['h']*height/ch))
        node.set('id','panel-'+p['id']);node.set('preserveAspectRatio','xMidYMid meet')
        root.append(node)
    tree.write(base,encoding='utf-8',xml_declaration=True)


def render(spec,assets,folder):
    fields(spec,['kind','title','canvas','panels','footer'],'assembly')
    require(spec.get('kind')=='assembly','kind 必须是 assembly')
    text_value(spec.get('title'),'title',300)
    c=spec['canvas'];fields(c,['width','height','width_mm','height_mm'],'canvas')
    w=finite(c['width'],'width',400,5000);h=finite(c['height'],'height',300,4000)
    require(1<=len(spec.get('panels',[]))<=8,'组合图版需要 1—8 个面板')
    ids=set()
    for p in spec['panels']:
        fields(p,['id','title','source','x','y','w','h'],'panel')
        for k in ['id','title','source']:text_value(p.get(k),k,300)
        require(p['id'] not in ids,'面板 ID 重复');ids.add(p['id'])
        for k in ['x','y','w','h']: finite(p[k],k,0,w if k in ['x','w'] else h)
        require(p['w']>0 and p['h']>0 and p['x']+p['w']<=w and p['y']+p['h']<=h,'面板越界')
        svg=asset_path(assets,str(Path(p['source'])/'figure.svg'))
        asset_path(assets,str(Path(p['source'])/'figure-outlined.svg'))
        shutil.copytree(svg.parent,folder/p['source'],ignore=shutil.ignore_patterns('rerun','__pycache__'))
    plt=matplotlib_setup();fig=plt.figure(figsize=(c.get('width_mm',300)/25.4,c.get('height_mm',220)/25.4))
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,w),ylim=(h,0));ax.axis('off')
    ax.text(45,40,spec['title'],fontsize=18,va='center',gid='assembly-title')
    for p in spec['panels']:
        ax.text(p['x']+8,p['y']-18,p['id']+'  '+p['title'],fontsize=11,va='center',gid='panel-title-'+p['id'])
    ax.text(45,h-24,spec.get('footer',''),fontsize=8,color='#65758A',va='center',gid='assembly-footer')
    qa=text_checks(fig);export(fig,folder,{'kind':'assembly','source':'source.json'});plt.close(fig)
    merge(folder/'figure.svg',spec,folder)
    merge(folder/'figure-outlined.svg',spec,folder,True)
    try: import cairosvg
    except ImportError: raise ValueError('组合导出需要按需安装 requirements-compose.txt；已保留面板与 SVG') from None
    # Outlined SVG avoids depending on Cairo finding the task's private font.
    cairosvg.svg2png(url=str(folder/'figure-outlined.svg'),write_to=str(folder/'figure.png'),output_width=2400)
    cairosvg.svg2pdf(url=str(folder/'figure-outlined.svg'),write_to=str(folder/'figure.pdf'))
    report={'kind':'assembly','renderer':'CairoSVG on outlined master','source':'source.json','notice':'Nested vector panels; raster components remain raster. Each panel includes original source and provenance.'}
    (folder/'figure.export.json').unlink();write_json(folder/'figure.export.json',report)
    write_json(folder/'source.json',spec);package_replay(folder,'assemble')
    qa['notice']+=' 组合图只自动筛查顶层标题；每个面板沿用自己的 QA，仍须实际查看完整图版。'
    notes='组合图版已生成。可按面板名称提出修改；先更新对应面板，再重新组合。\nSVG 保留各面板的独立矢量对象，生成素材仍是位图。完整制作源、数据和来源在面板目录。\n教学数据不代表真实研究结论；专家科学复核未完成。'
    return finish(folder,{'kind':'assembly','status':'GENERATED_REVIEW_PENDING','editability':{'panels':'nested SVG objects, edit panel source then reassemble','raster_assets':'see each panel manifest'}},notes,qa)
