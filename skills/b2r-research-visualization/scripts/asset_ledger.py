"""Register one already-downloaded, individually licensed scientific asset."""
from pathlib import Path
from urllib.parse import urlparse
import shutil,re,xml.etree.ElementTree as ET
from common import fields,text_value,require,checked_input_file,digest,write_json,finish

LICENSES={'CC0-1.0','Public-Domain','CC-BY-3.0','CC-BY-4.0','CC-BY-SA-3.0','CC-BY-SA-4.0','MIT'}

def validate_record(record):
    fields(record,['name','creator','collection','entry_url','download_url','license','license_url','license_verified','version','retrieved','changes','evidence','usage','share_alike_acknowledged','license_text'],'asset record')
    for key in ['name','creator','collection','entry_url','download_url','license_url','version','retrieved','changes','evidence','usage']:
        text_value(record.get(key),key,4000)
    require(record.get('license_verified') is True,'必须先核对该素材的实际许可，不能用未验证的授权占位')
    require(record.get('license') in LICENSES,'许可不在已处理范围；先确认条款，或换用明确许可素材')
    for key in ['entry_url','download_url','license_url']:
        u=urlparse(record[key]);require(u.scheme=='https' and u.hostname and not u.username and not u.password,'素材来源需为无凭证的 HTTPS 地址')
        require(not (u.hostname=='biorender.com' or u.hostname.endswith('.biorender.com')),'不收录或重新分发 BioRender 专有素材')
    if '-SA-' in record['license']:require(record.get('share_alike_acknowledged') is True,'选用 ShareAlike 前须明确本次改编/组合的许可义务')
    if record['license']=='MIT':text_value(record.get('license_text'),'MIT copyright and license text',20000)

def register(file,record,folder):
    validate_record(record);source=checked_input_file(file)
    require(source.suffix.lower() in {'.svg','.png','.jpg','.jpeg','.pptx'},'素材格式不在支持范围')
    if source.suffix.lower()=='.svg':
        raw=source.read_text(encoding='utf-8')
        urls=re.findall(r'url\(([^)]*)\)',raw,re.I)
        require(not re.search(r'@import',raw,re.I) and all(u.strip().strip('\"\x27').startswith('#') for u in urls),'SVG 含外部 CSS 依赖，需自包含素材')
        root=ET.parse(source).getroot()
        for e in root.iter():
            require(e.tag.rsplit('}',1)[-1] not in {'script','foreignObject'},'SVG 含活动内容')
            for key,value in e.attrib.items():
                require(not key.lower().startswith('on'),'SVG 含事件处理器')
                if key.endswith('href'):require(value.startswith(('#','data:image/')),'SVG 含外部依赖，需先取得明确的自包含文件')
    (folder/'original').mkdir();shutil.copyfile(source,folder/'original'/source.name)
    rec={**record,'file':'original/'+source.name,'sha256':digest(source),'bytes':source.stat().st_size}
    write_json(folder/'asset.json',rec)
    attribution=f"{record['name']} — {record['creator']} / {record['collection']}. {record['license']} ({record['license_url']}).\n来源：{record['entry_url']}\n版本：{record['version']}；取得：{record['retrieved']}。\n改动/用法：{record['changes']}\n"
    (folder/'ATTRIBUTION.md').write_text(attribution,encoding='utf-8')
    if record.get('license_text'):(folder/'LICENSE-ASSET.txt').write_text(record['license_text'],encoding='utf-8')
    return finish(folder,{'kind':'licensed_asset','status':'ASSET_RECORDED','asset_sha256':rec['sha256']},'已保存单个素材、原文件、哈希与署名。脚本不替代实际授权核对；按任务使用，不构建再分发图库。')
