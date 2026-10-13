#!/usr/bin/env python3
"""Single portable CLI. All core commands are local and network-free."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (CliError, read_json, capabilities, new_version, patch_source,
                    write_json, finish, require, digest, fields, text_value, VERSION)


def main():
    p=argparse.ArgumentParser(description=f'B2R AI-First 科研可视化 · 本地交付核心 {VERSION}')
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('doctor');d.add_argument('--host-capabilities')
    d.add_argument('--out')
    for name in ['schematic','results','artwork','assemble']:
        c=sub.add_parser(name);c.add_argument('--spec',required=True);c.add_argument('--out',required=True)
        if name=='results': c.add_argument('--data',required=True)
        if name in ['artwork','assemble']: c.add_argument('--assets')
    c=sub.add_parser('edit');c.add_argument('--source',required=True);c.add_argument('--patch',required=True)
    c.add_argument('--out',required=True);c.add_argument('--data');c.add_argument('--assets');c.add_argument('--record')
    c=sub.add_parser('inspect');c.add_argument('--source',required=True)
    c=sub.add_parser('inspect-data',help='只读识别表格结构，给出建议 spec 与必须确认的问题')
    c.add_argument('--data',required=True);c.add_argument('--sheet');c.add_argument('--spec-out')
    c=sub.add_parser('capture');c.add_argument('--image',required=True);c.add_argument('--record',required=True);c.add_argument('--out',required=True)
    c.add_argument('--parent',help='当前修改所引用的真实上一版图像')
    c=sub.add_parser('asset');c.add_argument('--file',required=True);c.add_argument('--record',required=True);c.add_argument('--out',required=True)
    c=sub.add_parser('handoff');c.add_argument('--brief',required=True);c.add_argument('--out',required=True)
    c=sub.add_parser('qa');c.add_argument('--contract',required=True);c.add_argument('--image',required=True)
    c.add_argument('--observations');c.add_argument('--ledger');c.add_argument('--out',required=True)
    c.add_argument('--previous',help='上一版图的 QA 输出目录（含 scientific-qa.json 与 figure-contract.json）')
    c=sub.add_parser('evidence');c.add_argument('--contract',required=True)
    c.add_argument('--ledger');c.add_argument('--out',required=True)
    c=sub.add_parser('render-plan');c.add_argument('--contract',required=True);c.add_argument('--plan')
    c.add_argument('--ledger');c.add_argument('--out',required=True)
    c.add_argument('--qa',help='scientific-qa.json：把关键错误编译为针对性修改请求')
    args=p.parse_args()
    try:
        if args.command=='doctor':
            result=capabilities(read_json(args.host_capabilities) if args.host_capabilities else None)
            if args.out: write_json(Path(args.out),result)
        elif args.command=='evidence':
            from evidence import evaluate_evidence
            contract=read_json(args.contract)
            ledger=read_json(args.ledger) if args.ledger else None
            result=evaluate_evidence(contract,ledger)
            folder=new_version(args.out)
            write_json(folder/'evidence-qa.json',result)
            write_json(folder/'figure-contract.json',contract)
            if ledger is not None: write_json(folder/'evidence-ledger.json',ledger)
            result['output_directory']=str(folder)
        elif args.command=='render-plan':
            from render_plan import compile_requests
            from evidence import evaluate_evidence
            contract=read_json(args.contract)
            require(args.plan or args.qa,'render-plan 需要 --plan（新图请求）或 --qa（修改请求）')
            folder=new_version(args.out)
            write_json(folder/'figure-contract.json',contract)
            result={}
            if args.plan:
                plan=read_json(args.plan)
                ledger=read_json(args.ledger) if args.ledger else None
                report=evaluate_evidence(contract,ledger) if ledger is not None or 'verification' in contract else None
                result=compile_requests(contract,plan,report)
                for option,text in result['requests'].items():
                    (folder/f'request-{option}.txt').write_text(text+'\n',encoding='utf-8')
                write_json(folder/'render-plan.json',result)
                write_json(folder/'layout-plan.json',plan)
                result={k:v for k,v in result.items() if k!='requests'}
            if args.qa:
                from render_plan import compile_correction
                correction=compile_correction(contract,read_json(args.qa))
                if correction['request']:
                    (folder/'request-correction.txt').write_text(correction['request']+'\n',encoding='utf-8')
                write_json(folder/'correction.json',correction)
                result['correction']={k:v for k,v in correction.items() if k!='request'}
            result['output_directory']=str(folder)
        elif args.command=='qa':
            from scientific_qa import evaluate
            from PIL import Image
            with Image.open(args.image) as im: im.load()
            ledger=read_json(args.ledger) if args.ledger else None
            result=evaluate(read_json(args.contract),read_json(args.observations) if args.observations else None,args.image,ledger)
            if args.previous:
                from scientific_qa import revision_review
                prior=Path(args.previous)
                result['revision']=revision_review(read_json(prior/'scientific-qa.json'),read_json(prior/'figure-contract.json'),result,read_json(args.contract))
            folder=new_version(args.out)
            write_json(folder/'scientific-qa.json',result)
            write_json(folder/'figure-contract.json',read_json(args.contract))
            if ledger is not None: write_json(folder/'evidence-ledger.json',ledger)
            if result['evidence_qa'] is not None: write_json(folder/'evidence-qa.json',result['evidence_qa'])
            result['output_directory']=str(folder)
        elif args.command=='inspect':
            source=read_json(args.source)
            if source.get('kind')=='artwork':
                from artwork import object_map
                result={'kind':'artwork','objects':object_map(source),'notice':'按语义定位对象；歧义时询问。自然语言理解由宿主完成。'}
            else: result={'kind':source.get('kind'),'source':source}
        elif args.command=='inspect-data':
            from results import load_table,profile
            header,rows=load_table(args.data,args.sheet)
            result=profile(header,rows)
            if args.sheet: result['suggested_spec']['sheet']=args.sheet
            if args.spec_out: write_json(Path(args.spec_out),result['suggested_spec'])
        elif args.command=='capture':
            from host_image import capture
            result=capture(args.image,read_json(args.record),new_version(args.out),args.parent)
        elif args.command=='asset':
            from asset_ledger import register
            result=register(args.file,read_json(args.record),new_version(args.out))
        elif args.command=='assemble':
            from assembly import render
            source=read_json(args.spec)
            result=render(source,args.assets or Path(args.spec).parent,new_version(args.out))
        elif args.command=='handoff':
            spec=read_json(args.brief)
            fields(spec,['goal','purpose','materials','completed','outputs','unresolved','changes','deadline','budget','contact'],'handoff')
            for k in ['goal','purpose']: text_value(spec.get(k),k,1000)
            labels={'goal':'目标','purpose':'用途','materials':'已提供材料','completed':'已完成',
                    'outputs':'输出文件','unresolved':'待解决','changes':'修改要求','deadline':'截止时间',
                    'budget':'预算（用户自愿提供）','contact':'用户配置的接续入口'}
            notes='本地人工接续草稿，请检查后自行提交。\n\n'
            for key,label in labels.items():
                v=spec.get(key,'未提供')
                if isinstance(v,list): v='\n'.join('- '+str(x) for x in v) or '未提供'
                notes+=f'{label}：\n{v}\n\n'
            folder=new_version(args.out);write_json(folder/'brief.json',spec)
            result=finish(folder,{'status':'LOCAL_HANDOFF_DRAFT','kind':'handoff'},notes)
        else:
            source=read_json(args.source if args.command=='edit' else args.spec)
            changes=None;parent=None
            if args.command=='edit':
                parent=digest(args.source)
                source,changes=patch_source(source,read_json(args.patch))
                if args.record:
                    require(source.get('kind')=='artwork','调用记录接续仅用于 artwork')
                    source['calls']=source.get('calls',[])+[read_json(args.record)]
            kind=source.get('kind')
            require(kind in ['schematic','results','artwork'],'未知 kind')
            if args.command!='edit': require(args.command==kind,'子命令与 spec.kind 不一致')
            if kind=='artwork':
                from artwork import render,validate
                assets=args.assets or Path(args.source if args.command=='edit' else args.spec).parent
                validate(source,assets)
                result=render(source,assets,new_version(args.out),changes,parent)
            elif kind=='schematic':
                from schematic import render,validate
                validate(source)
                folder=new_version(args.out)
                result=render(source,folder,changes,parent)
            else:
                require(args.data,'结果图需要 --data；请提供该版本的 input.csv/tsv/xlsx')
                from results import render,load_table,validate,prepare
                header,rows=load_table(args.data,source.get('sheet'))
                qs=validate(source,header)
                if not qs: prepare(source,rows)
                folder=new_version(args.out)
                result=render(source,args.data,folder,changes,parent)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result.get('status')!='NEEDS_INPUT' else 2
    except (CliError,OSError,KeyError,TypeError,ValueError) as exc:
        print(json.dumps({'status':'FAILED','error':str(exc),
                          'notice':'已存在的版本保持不变；本次未完成目录不能视为成功交付。'},ensure_ascii=False))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
