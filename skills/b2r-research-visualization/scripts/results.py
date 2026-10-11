"""Visualization of supplied numeric tables; no hypothesis tests or bioinformatics."""
from __future__ import annotations

import csv
import io
import math
import shutil
import statistics
from pathlib import Path

from common import (require, fields, finite, text_value, color, CliError, checked_input_file,
                    matplotlib_setup, write_json, export, text_checks, finish, pending, digest)
from color_palettes import OKABE_ITO_ON_WHITE

MODES={'raw_points','raw_mean_sd','raw_mean_sem','summary_point','summary_bar','line'}


def load_table(path):
    p=checked_input_file(path,max_bytes=20_000_000)
    if p.suffix.lower() in ['.csv','.tsv']:
        rows=list(csv.reader(io.StringIO(p.read_text(encoding='utf-8-sig')),
                             delimiter='\t' if p.suffix.lower()=='.tsv' else ','))
    elif p.suffix.lower()=='.xlsx':
        import zipfile
        with zipfile.ZipFile(p) as z:
            require(sum(i.file_size for i in z.infolist())<=80_000_000,'XLSX 解压内容过大；请导出 CSV')
        try:
            import openpyxl
        except ImportError:
            raise CliError('XLSX 需要可选依赖 openpyxl；也可另存为 CSV') from None
        wb=openpyxl.load_workbook(p,read_only=True,data_only=True)
        try:
            require(len(wb.sheetnames)==1,'v0.1 XLSX 仅接受单工作表；请明确选择后导出 CSV')
            rows=[list(r) for r in wb.active.iter_rows(values_only=True)]
        finally: wb.close()
    else: raise CliError('输入只支持 CSV、TSV、单工作表 XLSX')
    require(2<=len(rows)<=20001,'表格需要标题和 1—20000 行数据')
    header=[str(c).strip() if c is not None else '' for c in rows[0]]
    require(all(header) and len(header)==len(set(header)),'列名为空或重复')
    require(len(header)<=100,'列数最多 100')
    result=[]
    for i,row in enumerate(rows[1:],2):
        require(len(row)==len(header),f'第 {i} 行列数不一致')
        result.append({k:'' if v is None else str(v) for k,v in zip(header,row)})
    return header,result


def number(raw, name, missing_values, allow_missing=True):
    if raw.strip() in missing_values:
        require(allow_missing,f'{name} 不允许缺失')
        return None
    try: v=float(raw)
    except (ValueError,TypeError): raise CliError(f'{name} 不是数字') from None
    require(math.isfinite(v),f'{name} 含非有限数；请明确缺失值编码')
    return v


def validate(spec, header):
    fields(spec,['kind','title','purpose','language','mode','columns','unit','xlabel','ylabel',
                 'group_order','missing_values','transform','error_definition','replication_unit',
                 'independence_confirmed','width_mm','height_mm','colors','notes'], '结果图')
    require(spec.get('kind')=='results','kind 必须是 results')
    mode=spec.get('mode')
    require(mode in MODES, '不支持 mode；请参考 input-contracts.md')
    for k in ['title','purpose','unit']: text_value(spec.get(k),k,180)
    require(spec.get('language') in ['zh','en','bilingual'],'language 必须是 zh/en/bilingual')
    cols=spec.get('columns',{})
    fields(cols,['group','value','sample_id','x','error','lower','upper','n'],'columns')
    require('group' in cols and 'value' in cols,'columns 需要 group 和 value')
    require(all(isinstance(v,str) and v in header for v in cols.values()),'指定列不存在')
    require(len(set(cols.values()))==len(cols),'多个变量不能映射同一列')
    raw=mode.startswith('raw_')
    require(not(raw and set(cols)&{'error','lower','upper','n','x'}),'raw 模式不接收已有误差、n 或 x')
    require(not('error' in cols and set(cols)&{'lower','upper'}),'对称与上下界误差不能混用')
    require(('lower' in cols)==('upper' in cols),'上下界必须同时提供')
    if mode=='line': require('x' in cols,'line 模式需要数值 x 列')
    if mode in {'summary_point','summary_bar'}: require('x' not in cols,'分组汇总模式不接受 x')
    require(spec.get('transform','none') in ['none','log2'],'transform 仅支持 none/log2')
    finite(spec.get('width_mm',165),'width_mm',80,400)
    finite(spec.get('height_mm',115),'height_mm',60,400)
    for c in spec.get('colors',[]): color(c)
    require(isinstance(spec.get('colors',[]),list),'colors 必须是列表')
    missing=spec.get('missing_values',['','NA','N/A'])
    require(isinstance(missing,list) and all(isinstance(v,str) for v in missing),'missing_values 是字符串列表')
    questions=[]
    if mode in {'raw_mean_sd','raw_mean_sem'}:
        if not cols.get('sample_id') or not spec.get('replication_unit') or spec.get('independence_confirmed') is not True:
            questions.append('独立实验单位是什么？每行是否为独立样本，并可提供 sample_id 列？技术重复请先确认合并规则。')
    if set(cols)&{'error','lower','upper'}:
        if not spec.get('error_definition'):
            questions.append('误差列/上下界表示 SD、SEM、CI 或什么范围？请提供定义与计算尺度。')
        if not cols.get('n') or not spec.get('replication_unit'):
            questions.append('各组样本量 n 和重复单位是什么？若无法确认，请去掉误差映射，只显示已有点估计并标注限制。')
        if spec.get('transform','none')!='none':
            raise CliError('已有误差的数据不自动 log2；请提供同尺度的变换后估计与区间')
    require(not(raw and spec.get('error_definition')),'raw 模式误差由 mode 明确；不接收自定义 error_definition')
    return questions[:3]


def prepare(spec, rows):
    cols=spec['columns'];mode=spec['mode'];raw=mode.startswith('raw_')
    missing=spec.get('missing_values',['','NA','N/A']);clean=[];seen=set()
    groups=[]
    for rowno,row in enumerate(rows,2):
        g=text_value(row[cols['group']].strip(),f'第 {rowno} 行 group',100)
        if g not in groups: groups.append(g)
        v=number(row[cols['value']],f'第 {rowno} 行 value',missing)
        value=v
        if v is not None and spec.get('transform','none')=='log2':
            require(v>0,'log2 需要所有非缺失值 > 0；不自动增加伪计数')
            value=math.log2(v)
        item={'source_row':rowno,'group':g,'input_value':v,'plot_value':value}
        if 'sample_id' in cols:
            sid=text_value(row[cols['sample_id']].strip(),'sample_id',180)
            require((g,sid) not in seen,'同组 sample_id 重复；先确认技术/重复测量结构，不作独立重复计数')
            seen.add((g,sid));item['sample_id']=sid
        if 'x' in cols:
            x=number(row[cols['x']],'x',missing,False)
            require((g,x) not in seen,'同组 x 重复；本版不自动聚合时间点')
            seen.add((g,x));item['x']=x
        for key in ['error','lower','upper','n']:
            if key in cols:
                z=number(row[cols[key]],key,missing,False)
                if key=='n': require(z>=1 and z.is_integer(),'n 必须是正整数')
                if key=='error': require(z>=0,'误差不能是负数')
                item[key]=int(z) if key=='n' else z
        if 'lower' in item:
            require(v is not None and item['lower']<=v<=item['upper'],'区间需要 lower <= value <= upper')
        clean.append(item)
    order=spec.get('group_order',groups)
    require(isinstance(order,list) and len(order)==len(set(order)) and set(order)==set(groups),'group_order 必须恰好包含所有组')
    require(1<=len(order)<=5,'v0.1 每图支持 1—5 组；更多组请分面或明确额外设计')
    summary=[]
    for g in order:
        gr=[r for r in clean if r['group']==g]
        vals=[r['plot_value'] for r in gr if r['plot_value'] is not None]
        require(bool(vals),f'{g} 全部缺失，不自动隐藏组')
        if raw:
            agg={'group':g,'observed_rows':len(vals),'missing_rows':len(gr)-len(vals)}
            if mode!='raw_points':
                require(len(vals)>=2,'SD/SEM 至少需要两个已确认独立观测')
                agg['mean']=statistics.mean(vals)
                agg['sd']=statistics.stdev(vals)
                agg['sem']=agg['sd']/math.sqrt(len(vals))
            summary.append(agg)
        elif mode!='line':
            require(len(gr)==1,'已有汇总每组只能一行；不自动平均已有结果')
            summary.append(gr[0])
    return clean,summary,order


def csv_out(path, records):
    keys=list(dict.fromkeys(k for r in records for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(records)


def render(spec, data_path, folder, changes=None, parent=None):
    header,rows=load_table(data_path)
    questions=validate(spec,header)
    original=checked_input_file(data_path,max_bytes=20_000_000)
    input_name='input'+original.suffix.lower()
    if questions:
        shutil.copyfile(original,folder/input_name)
        return pending(folder,spec,questions)
    clean,summary,order=prepare(spec,rows)
    plt=matplotlib_setup()
    import numpy as np
    from matplotlib import ticker
    fig,ax=plt.subplots(figsize=(spec.get('width_mm',165)/25.4,spec.get('height_mm',115)/25.4),layout='constrained')
    mode=spec['mode'];colors=spec.get('colors') or OKABE_ITO_ON_WHITE
    require(len(colors)>=len(order),'colors 数量小于组数')
    marks=['o','s','^','D','v']
    ax.spines[['top','right']].set_visible(False)
    ax.spines[['bottom','left']].set_color('#8795A5')
    ax.grid(axis='y',color='#E5EBF0',lw=.6,zorder=0)
    if mode.startswith('raw_'):
        for i,g in enumerate(order):
            vals=[r['plot_value'] for r in clean if r['group']==g and r['plot_value'] is not None]
            offsets=np.linspace(-.13,.13,len(vals)) if len(vals)>1 else np.array([0.])
            ax.scatter(i+offsets,vals,c=colors[i],marker=marks[i],s=33,edgecolors='white',linewidth=.5,zorder=3,gid='observations-'+str(i))
            if mode!='raw_points':
                s=summary[i];err=s['sd'] if mode=='raw_mean_sd' else s['sem']
                ax.errorbar(i,s['mean'],yerr=err,fmt='_',ms=21,lw=1.4,c='#25384B',capsize=5,zorder=4)
        ax.set_xticks(range(len(order)),order)
        ax.set_xlim(-.5,len(order)-.5)
    elif mode in {'summary_bar','summary_point'}:
        for i,s in enumerate(summary):
            y=s['plot_value']
            require(y is not None,'汇总估计缺失；请明确缺失展示设计')
            err=None
            if 'error' in s: err=s['error']
            if 'lower' in s: err=[[y-s['lower']],[s['upper']-y]]
            if mode=='summary_bar': ax.bar(i,y,color=colors[i],width=.55,edgecolor='#455468',lw=.5,zorder=2,hatch=['','//','..','xx','--'][i])
            else: ax.scatter(i,y,c=colors[i],marker=marks[i],s=48,zorder=3)
            if err is not None: ax.errorbar(i,y,yerr=err,fmt='none',c='#25384B',capsize=4,lw=1.2,zorder=4)
        ax.set_xticks(range(len(order)),order);ax.set_xlim(-.5,len(order)-.5)
        if mode=='summary_bar':
            lo,hi=ax.get_ylim();ax.set_ylim(min(0,lo),max(0,hi))
    else:
        for i,g in enumerate(order):
            gr=sorted([r for r in clean if r['group']==g],key=lambda r:r['x'])
            xs=[r['x'] for r in gr];ys=[np.nan if r['plot_value'] is None else r['plot_value'] for r in gr]
            ax.plot(xs,ys,color=colors[i],marker=marks[i],ls=['-','--','-.',':','-'][i],label=g,lw=1.4,ms=5)
            if 'error' in spec['columns']:
                ax.errorbar(xs,ys,yerr=[r['error'] for r in gr],fmt='none',c=colors[i],capsize=3)
            if 'lower' in spec['columns']:
                ax.errorbar(xs,ys,yerr=[[y-r['lower'] for y,r in zip(ys,gr)],
                                       [r['upper']-y for y,r in zip(ys,gr)]],fmt='none',c=colors[i],capsize=3)
        ax.legend(frameon=False,fontsize=9)
    unit=spec['unit'];transform=spec.get('transform','none')
    default_y=('log2'+' ('+unit+')') if transform=='log2' else unit
    ax.set(xlabel=spec.get('xlabel','分组' if spec['language']=='zh' else 'Group'),
           ylabel=spec.get('ylabel',default_y),title=spec['title'])
    ax.title.set_fontsize(13)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6))
    error_label={'raw_points':'不计算误差；逐行观测', 'raw_mean_sd':'均值 ± 样本 SD (ddof=1)',
                 'raw_mean_sem':'均值 ± SEM = SD/√n'}
    uncertainty=error_label.get(mode,spec.get('error_definition','未显示误差；仅已有估计'))
    if mode in {'raw_mean_sd','raw_mean_sem'}:
        ns=', '.join(str(s['observed_rows']) for s in summary)
        stat='SD' if mode=='raw_mean_sd' else 'SEM'
        footer=(f'Mean ± {stat}; n = {ns} (group order)' if spec['language']=='en'
                else f'均值 ± {stat}；各组 n = {ns}（按横轴顺序）')
    elif mode=='raw_points':
        footer='Observed rows; no error bars' if spec['language']=='en' else '逐行观测；未绘制误差条'
    else:
        footer=spec.get('error_definition', 'Supplied estimates; no uncertainty shown' if spec['language']=='en' else '用户已有估计；未提供误差')
    fig.supxlabel(footer,fontsize=8,color='#526477')
    caption={'purpose':spec['purpose'],'unit':unit,'group_order':order,'mode':mode,
             'uncertainty':uncertainty,'replication_unit':spec.get('replication_unit','未确认'),
             'transform': 'log2(value)，无伪计数；误差在变换后尺度计算' if transform=='log2' else 'none',
             'missing_rows':[r['source_row'] for r in clean if r['plot_value'] is None],
             'missing_policy':'保留原表和记录；原始点只绘制非缺失值；line 对明确缺失行保留断点；不存在的时间点无法识别',
             'statistical_tests':'未执行；未生成 p 值或显著性标记','notes':spec.get('notes',[])}
    qa=text_checks(fig)
    export(fig,folder,{'kind':'results','input':input_name,'input_sha256':digest(original),
                       'source':'source.json','caption':'caption.json','transform':caption['transform'],
                       'uncertainty':uncertainty,'group_order':order})
    plt.close(fig)
    shutil.copyfile(original,folder/input_name)
    csv_out(folder/'plot-data.csv',clean);csv_out(folder/'summary.csv',summary or clean)
    write_json(folder/'source.json',spec);write_json(folder/'caption.json',caption)
    if changes is not None: write_json(folder/'changes.json',{'parent':parent,'changes':changes})
    from common import package_replay
    package_replay(folder,'results',input_name)
    manifest={'status':'GENERATED_REVIEW_PENDING','kind':'results','parent':parent,
              'input_sha256':digest(original),'editability':{
                  'text':'figure.svg independent text; requires bundled font',
                  'data_and_styles':'source.json + input table + reproduce.py',
                  'geometry':'SVG vector paths; changes to values require rerender',
                  'raster_assets':[]}}
    notes='已生成真实数据图、SVG/PNG/PDF、原始输入副本、plot-data.csv、summary.csv 和 caption.json。\n误差：'+uncertainty+'；变换：'+caption['transform']+'。\n未执行统计检验或生信分析。变量、单位、分组、缺失和重复单位详见 caption.json。\n运行 reproduce.py 可在 rerun 新版本复现；所需脚本、字体和依赖说明随附。\nSVG 文字独立、几何为矢量；颜色与标签可局部修改；outlined 版本文字转轮廓。科学复核待完成。'
    if qa['issues']: notes+='\n边界筛查发现问题，详见 qa.json；使用前先修正布局。'
    return finish(folder,manifest,notes,qa)
