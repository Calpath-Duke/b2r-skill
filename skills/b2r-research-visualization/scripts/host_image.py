"""Deliver actual host images and follow-up edits; no simulated model client."""
from pathlib import Path
import shutil
import hashlib
import json
from common import fields,text_value,require,checked_input_file,write_json,digest,finish,finite


def compare_edit(previous,current,regions):
    """Describe actual pixel drift; never infer scientific or perceptual approval."""
    from PIL import Image
    import numpy as np
    with Image.open(previous) as im: a=np.asarray(im.convert('RGB')).astype('int16')
    with Image.open(current) as im: b=np.asarray(im.convert('RGB')).astype('int16')
    require(isinstance(regions,list),'expected_regions 必须是矩形列表')
    for box in regions:
        require(isinstance(box,list) and len(box)==4,'区域须为归一化 [左,上,右,下]')
        for v in box: finite(v,'region',0,1)
        require(box[0]<box[2] and box[1]<box[3],'区域边界顺序错误')
    report={'method':'Decoded RGB, no alignment or resampling; regions are approximate bounding rectangles',
            'same_dimensions':a.shape==b.shape,'before_pixels':[a.shape[1],a.shape[0]],
            'after_pixels':[b.shape[1],b.shape[0]],'expected_regions':regions,
            'notice':'像素差异可能来自纹理、抗锯齿和再生成；不能替代实际查看或科学核对。'}
    if a.shape!=b.shape:
        report['comparison']='NOT_COMPARABLE_DIMENSIONS_CHANGED';return report
    mask=np.ones(a.shape[:2],dtype=bool)
    for x0,y0,x1,y1 in regions:
        mask[int(y0*a.shape[0]):int(np.ceil(y1*a.shape[0])),int(x0*a.shape[1]):int(np.ceil(x1*a.shape[1]))]=False
    delta=np.abs(a-b)
    def stats(v):
        if not len(v):return {'pixels':0}
        return {'pixels':len(v),'changed_pixels':int((v.max(axis=1)>0).sum()),'percent_max_channel_delta_gt_20':float((v.max(axis=1)>20).mean()*100),'mean_absolute_rgb_delta':float(v.mean())}
    report['overall']=stats(delta.reshape(-1,3))
    report['outside_expected_regions']=stats(delta[mask]) if regions else {'status':'NO_REGION_SPECIFIED; no local-invariance claim'}
    return report


def capture(image,record,folder,parent=None):
    fields(record,['brief','prompt','tool','model','status','references','changes','visual_review','scientific_questions','editability','usage','output_reference','evidence','asset_credits','requested_change','expected_regions','host_observations','limitations','change_origin'],'host image record')
    for k in ['brief','prompt','tool','model','output_reference']: text_value(record.get(k),k,20000)
    require(record.get('status')=='succeeded','只有实际成功且取得输出的调用可交付图像')
    require(isinstance(record.get('scientific_questions',[]),list),'scientific_questions 必须是列表')
    from PIL import Image
    source=checked_input_file(image)
    # Decode before copying. The caller must already have a genuine host artifact.
    with Image.open(source) as im:
        source_format=im.format
        im.load();im=im.copy()
    from figure_brief import prepare_context,save_context
    figure_context=prepare_context(record,source)
    observations=record.get('host_observations',{})
    scientific_report=None
    contract=observations.get('figure_contract') if isinstance(observations,dict) else None
    if contract is not None:
        from scientific_qa import evaluate
        scientific_report=evaluate(contract,observations.get('scientific_observation'),source,observations.get('evidence_ledger'))
        prior=Path(parent).resolve().parent if parent else None
        if prior and prior.name=='original': prior=prior.parent
        if prior and (prior/'scientific-qa.json').is_file() and (prior/'figure-contract.json').is_file():
            previous=json.loads((prior/'scientific-qa.json').read_text())
            delivered=json.loads((prior/'source.json').read_text()).get('original_sha256') if (prior/'source.json').is_file() else None
            if previous.get('image_sha256') in {digest(parent),delivered if Path(parent).name=='figure.png' else None}:
                from scientific_qa import revision_review
                scientific_report['revision']=revision_review(previous,json.loads((prior/'figure-contract.json').read_text()),scientific_report,contract)
    elif isinstance(observations,dict):
        require('scientific_observation' not in observations,'科学观察需要对应 figure_contract')
        require('evidence_ledger' not in observations,'证据台账需要对应 figure_contract')
    option=observations.get('figure_option') if isinstance(observations,dict) else None
    option_record={}
    if option is not None:
        require(option in ('classic2d','refined2d'),'figure_option 需为 classic2d 或 refined2d')
        require(figure_context is not None,'方案收录需要共享 figure_brief；普通图可省略 figure_option')
        plan=json.dumps(figure_context['brief'],ensure_ascii=False,sort_keys=True,separators=(',',':'))
        option_record={'figure_option':{'name':option,'scientific_plan_sha256':hashlib.sha256(plan.encode('utf-8')).hexdigest()}}
    parent_file=checked_input_file(parent) if parent else None
    if parent_file:
        text_value(record.get('requested_change'),'requested_change',10000)
        require(record.get('change_origin','user_feedback') in {'user_feedback','visual_qa'},'change_origin 需为 user_feedback 或 visual_qa')
    (folder/'original').mkdir();shutil.copyfile(source,folder/'original'/source.name)
    if source_format == 'PNG':
        shutil.copyfile(source,folder/'figure.png')
    else:
        im.save(folder/'figure.png','PNG')
    source_hash, final_hash = digest(source), digest(folder/'figure.png')
    image_delivery={'source_file':'original/'+source.name,'source_format':source_format,
                    'source_sha256':source_hash,'final_file':'figure.png','final_sha256':final_hash,
                    'operation':'byte_preserving_copy' if source_format == 'PNG' else 'decoded_image_to_png',
                    'same_bytes':source_hash == final_hash,
                    'qa_input_sha256':source_hash,
                    'final_png_review':'SAME_ARTIFACT_AS_SOURCE' if source_hash == final_hash else 'NEEDS_REVIEW'}
    if scientific_report is not None:
        # Conversion is not a new observation. Never replace the supplied hash.
        scientific_report['image_delivery']=image_delivery
    # PDF is explicitly a raster presentation export, not independent SVG text.
    rgba=im.convert('RGBA');paper=Image.new('RGBA',rgba.size,'white');paper.alpha_composite(rgba)
    paper.convert('RGB').save(folder/'figure.pdf','PDF',resolution=150,quality=95)
    details={'decoded':True,'pixels':list(im.size),'source_sha256':source_hash,'image_delivery':image_delivery,'pdf':'raster image on white; 150 dpi nominal layout, no added detail'}
    source_record={'kind':'host_image','original':'original/'+source.name,'original_sha256':digest(source),'calls':'calls.json','model':record['model'],'reproducibility':'Exact original bytes retained; model regeneration is not deterministic and is not invoked by this package.'}
    source_record.update(option_record)
    source_record['image_delivery']=image_delivery
    if parent_file:
        (folder/'reference').mkdir();shutil.copyfile(parent_file,folder/'reference'/parent_file.name)
        diff=compare_edit(parent_file,folder/'figure.png',record.get('expected_regions',[]))
        write_json(folder/'edit-comparison.json',diff)
        source_record['parent']={'file':'reference/'+parent_file.name,'sha256':digest(parent_file)}
        write_json(folder/'changes.json',{'requested_change':record['requested_change'],'change_origin':record.get('change_origin','user_feedback'),'parent_sha256':digest(parent_file),'actual_review':record.get('visual_review','PENDING'),'pixel_comparison':'edit-comparison.json'})
    write_json(folder/'source.json',source_record)
    write_json(folder/'evidence.json',{'statements':record.get('evidence',[]),'questions':record.get('scientific_questions',[]),'scientific_expert_review':'PENDING'})
    if record.get('asset_credits'):
        require(isinstance(record['asset_credits'],list) and all(isinstance(s,str) for s in record['asset_credits']),'asset_credits 需为署名文本列表')
        (folder/'ATTRIBUTION.md').write_text('# 素材署名\n\n'+'\n\n'.join(record['asset_credits'])+'\n',encoding='utf-8')
    write_json(folder/'calls.json',record)
    gate=save_context(figure_context,folder)
    if scientific_report is not None:
        write_json(folder/'figure-contract.json',contract)
        write_json(folder/'scientific-qa.json',scientific_report)
        if observations.get('evidence_ledger') is not None:
            write_json(folder/'evidence-ledger.json',observations['evidence_ledger'])
        if scientific_report['evidence_qa'] is not None:
            write_json(folder/'evidence-qa.json',scientific_report['evidence_qa'])
    write_json(folder/'qa.json',{'file_checks':details,'visual_review':record.get('visual_review','PENDING'),'scientific_review':'PENDING','figure_quality_gate':gate,'scientific_qa':scientific_report})
    notes='AI 科研插画已保存（PNG / PDF）。直接用自然语言继续修改，例如“提高标签可读性，保留科学关系与其余结构”。\n本版主体、文字和线条都在位图内；修改内部元素需宿主图片编辑，不是全图可编辑 SVG。原图与调用记录随附。'
    if option is not None:
        notes+='\n本文件方案：'+('A · Classic 2D' if option=='classic2d' else 'B · Refined 2D')+'；后续修改以此版本为基础，其他方案独立保留。'
    if gate:
        brief_file='figure-brief.md' if isinstance(figure_context['brief'],str) else 'figure-brief.json'
        notes+='\n内部规划与逐项检查见 '+brief_file+' / quality-gate.json；这是查看记录，不是专家科学认证。'
        if gate['status']!='HOST_REVIEW_RECORDED':
            notes+='\n内容/视觉检查仍有待确认项或已知问题，见 quality-gate.json。'
    if record.get('scientific_questions'): notes+='\n待确认：'+'；'.join(record['scientific_questions'])
    if record.get('asset_credits'):notes+='\n使用第三方素材参考，署名见 ATTRIBUTION.md；传播图件时请携带相应署名。'
    if scientific_report:
        notes+='\n关系契约与需求/证据/图像三类核对见 figure-contract.json / scientific-qa.json。'
        if scientific_report.get('revision',{}).get('unrequested_regressions'):
            notes+='\n本次修改使未要求变化的科学关系变差：'+'、'.join(scientific_report['revision']['unrequested_regressions'])+'；见 scientific-qa.json 的 revision。'
        if scientific_report['disposition']=='REVIEW_DRAFT':
            notes+='\n评审稿：发现关键科学内容冲突，不能作为科学核验通过的正式图件。'
    status='REVIEW_DRAFT' if scientific_report and scientific_report['disposition']=='REVIEW_DRAFT' else 'GENERATED_REVIEW_PENDING'
    if source_hash != final_hash:
        notes+='\n输入已转换为 PNG；原有观察与 QA 仍绑定原文件，最终 figure.png 需另行查看，不能继承原图 PASS。转换与哈希见 source.json。'
    return finish(folder,{'kind':'host_image','status':status,'review_state':{'visual':record.get('visual_review','PENDING'),'scientific':'PENDING','final_png':image_delivery['final_png_review'],'figure_quality_gate':gate,'scientific_qa_disposition':scientific_report['disposition'] if scientific_report else 'NOT_REQUESTED','notice':'总体状态保留待复核；visual 与 QA 是输入图的观察，final_png 另列是否同一文件；不能替代专家科学复核。'},'editability':{'raster':'whole image; labels are not independent unless separately supplied'},'source_model':record['model'],**option_record},notes)
