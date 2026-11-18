"""Small reviewed advisory catalog; version matches are not exploit detection."""
import re

PRODUCTS={'oracle_java_8':'Oracle Java 8','teamviewer':'TeamViewer','chrome':'Google Chrome','edge':'Microsoft Edge','git':'Git','nvidia_driver':'NVIDIA graphics driver','hp_connection_optimizer':'HP Connection Optimizer'}
CATALOG='2026-11-19: Oracle July 2020 / TeamViewer TV-2024-1006 (3 CVEs only)'

def review(software):
    if software is None:return {'available':False,'items':[],'matches':[],'catalog':CATALOG,'coverage':'No software inventory supplied; no software CVEs assessed.'}
    if not isinstance(software,dict) or type(software.get('available')) is not bool:raise ValueError('Software inventory needs an available flag.')
    if not software['available']:return {'available':False,'items':[],'matches':[],'catalog':CATALOG,'coverage':'Software inventory unavailable; no software CVEs assessed.'}
    rows=software.get('items',[])
    if not isinstance(rows,list) or len(rows)>80:raise ValueError('Software inventory must contain at most 80 records.')
    items=[];matches=[];seen=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid software item.')
        product=row.get('product');version=row.get('version');evidence=row.get('evidence')
        if product not in PRODUCTS or not isinstance(version,str) or not re.fullmatch(r'\d{1,6}(?:\.\d{1,6}){1,3}',version) or evidence not in ('file_version','registry'):raise ValueError('Unsupported software product, version or evidence type.')
        if (product,version) in seen:continue
        seen.add((product,version));items.append({'product':product,'name':PRODUCTS[product],'version':version,'evidence':evidence})
        parts=tuple(map(int,version.split('.')));v=parts+(0,)*(4-len(parts))
        if product=='oracle_java_8' and v==(8,0,2510,8):
            matches.append({'product':PRODUCTS[product],'version':version,'cves':['CVE-2020-14556'],'severity':'medium','basis':'Oracle explicitly lists Java 8u251 as affected. Exposure depends on Java usage and handling of untrusted input; exploitation was not tested.','source_url':'https://www.oracle.com/security-alerts/cpujul2020.html','action':'Update to a currently supported Java release compatible with your applications, or remove this old runtime if unused.'})
        fixes={15:(15,58,4,0),14:(14,7,48796,0),13:(13,2,36225,0),12:(12,0,259312,0),11:(11,0,259311,0)}
        if product=='teamviewer' and v[0] in fixes and v<fixes[v[0]]:
            matches.append({'product':PRODUCTS[product],'version':version,'cves':['CVE-2024-7479','CVE-2024-7481'],'severity':'high','basis':'Windows Full Client/Host service version matches the affected range. These flaws require an attacker to already have local access; a version match is not evidence of an attack.','source_url':'https://www.teamviewer.com/en-us/resources/trust-center/security-bulletins/tv-2024-1006/','action':'Update TeamViewer to the latest supported release, or uninstall it if unused. The 15.x fixes first appeared in 15.58.4.'})
    return {'available':True,'items':items,'matches':matches,'catalog':CATALOG,'coverage':'Limited checks: three CVEs across Oracle Java 8u251 and TeamViewer Windows Full Client/Host. Other versions/products and portable or Store apps are not comprehensively assessed. No match is not a clean bill of health.'}
