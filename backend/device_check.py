"""Strictly typed, minimal laptop evidence. No uploaded instructions reach the model."""
import json
from datetime import datetime,timezone,timedelta

SCHEMA='signal-desk-device-check/v1'
FIELDS={
    'defender':{'antivirus_enabled':'bool','real_time_enabled':'bool','signature_age_days':'age','quick_scan_age_days':'age'},
    'firewall':{'domain_enabled':'bool','private_enabled':'bool','public_enabled':'bool'},
    'threats':{'active_count':'count','history_count':'count'},
    'updates':{'last_hotfix_date':'date'},
    'secure_boot':{'enabled':'bool'},'disk_encryption':{'enabled':'bool'},'remote_desktop':{'enabled':'bool'},
}
class ReportError(ValueError):pass

def date(value,label):
    if not isinstance(value,str) or len(value)>40:raise ReportError(label+' must be an ISO date.')
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except ValueError:raise ReportError(label+' must be an ISO date.') from None

def analyze(report,now=None):
    now=now or datetime.now(timezone.utc)
    if not isinstance(report,dict) or report.get('schema')!=SCHEMA:raise ReportError('Attach the JSON created by the Signal Desk Windows check script.')
    if len(json.dumps(report))>65536:raise ReportError('Laptop report must be under 64 KB.')
    generated=date(report.get('generated_at'),'Report time')
    if generated>now+timedelta(minutes=10):raise ReportError('Report timestamp is in the future. Correct the laptop clock and generate a new report.')
    checks=report.get('checks')
    if not isinstance(checks,dict):raise ReportError('Report checks are missing.')
    from .software_check import review
    try:software=review(report.get('software'))
    except ValueError as exc:raise ReportError(str(exc)) from None
    if software['available']:
        software_time=date(report['software'].get('collected_at',report['generated_at']),'Software collection time')
        if software_time>now+timedelta(minutes=10):raise ReportError('Software collection timestamp is in the future.')
        software['collected_at']=software_time.isoformat()
    clean={};findings=[];unknown=[]
    for name,fields in FIELDS.items():
        row=checks.get(name,{'available':False})
        if not isinstance(row,dict) or type(row.get('available')) is not bool:raise ReportError(name+': available must be true or false.')
        clean[name]={'available':row['available']}
        if not row['available']:
            unknown.append(name);continue
        for key,kind in fields.items():
            value=row.get(key)
            if value is None:
                unknown.append(name+'.'+key)
            elif kind=='bool' and type(value) is not bool:raise ReportError(name+'.'+key+' must be true, false or null.')
            elif kind in ('age','count') and (type(value) is not int or not 0<=value<=(36500 if kind=='age' else 1000000)):raise ReportError(name+'.'+key+' must be a nonnegative integer in range.')
            elif kind=='date':
                parsed=date(value,key)
                if parsed>now+timedelta(days=1):raise ReportError('Hotfix date is in the future.')
                value=parsed.date().isoformat()
            clean[name][key]=value
    def val(group,key):return clean[group].get(key) if clean[group]['available'] else None
    def add(level,title,basis,next_step):findings.append({'level':level,'title':title,'evidence':basis,'next_step':next_step})
    for match in software['matches']:
        add('vulnerability',match['product']+' '+match['version']+' — vendor-advisory match',', '.join(match['cves'])+'. '+match['basis'],match['action'])
        findings[-1]['source_url']=match['source_url']
    stale=now-generated>timedelta(days=7)
    if stale:add('review','Old snapshot','Report is over seven days old.','Generate a fresh report before assessing the current laptop.')
    active=val('threats','active_count');history=val('threats','history_count')
    if active is not None and history is not None and active>history:raise ReportError('Active threat count cannot exceed the history count.')
    if active:
        add('urgent','Defender reported active detections',f'{active} active threat record(s) at collection time; this does not establish a live attacker.','Open Windows Security > Virus & threat protection > Protection history. Follow Defender remediation; if you suspect ongoing misuse, disconnect from the network and seek trusted IT help.')
    elif history:
        add('review','Past Defender detections',f'{history} history record(s); active count is '+('unknown.' if active is None else 'zero.'),'Review Protection history to check remediation. Past records alone do not prove a current infection.')
    for key,label in [('antivirus_enabled','Microsoft Defender antivirus'),('real_time_enabled','Defender real-time protection')]:
        if val('defender',key) is False:add('attention',label+' is off',key+' = false','Check Windows Security for your active antivirus provider. Another antivirus may legitimately replace Defender; verify protection before changing settings.')
    age=val('defender','signature_age_days')
    if age is not None and age>7:add('attention','Defender definitions need review',f'Signatures were {age} days old. Seven days is a review threshold, not proof of infection.','Check protection updates in Windows Security and update definitions if Defender is your active antivirus.')
    for key in FIELDS['firewall']:
        if val('firewall',key) is False:add('attention',key.replace('_enabled','').title()+' firewall profile is off',key+' = false; this profile may not currently be in use.','Review Windows Security > Firewall & network protection. Enable appropriate protection unless your administrator manages another firewall.')
    for group,label,advice in [('secure_boot','Secure Boot','Review supported Secure Boot settings with your device manufacturer or IT administrator.'),('disk_encryption','System-drive BitLocker protection','Check Device encryption or BitLocker settings. Keep any recovery key private and backed up before making changes.')]:
        if val(group,'enabled') is False:add('review',label+' is off','enabled = false; this is a protection setting, not malware evidence.',advice)
    if val('remote_desktop','enabled') is True:add('review','Remote Desktop is enabled','Remote access setting is enabled; this does not show an external connection or attack.','Turn it off if unused, or ask IT to review who is allowed to connect and network exposure.')
    hotfix=val('updates','last_hotfix_date')
    if hotfix and (now-date(hotfix,'Hotfix')).days>45:add('review','Windows update history needs review','Newest visible hotfix is '+hotfix+'. Get-HotFix is incomplete; age does not establish missing security patches.','Open Windows Update and check for updates. This snapshot cannot identify specific CVEs or prove patch compliance.')
    if unknown:add('unknown','Some checks were unavailable',', '.join(unknown),'Unavailable is not a pass. Some commands require administrator access or supported Windows features; review these settings manually.')
    verdict='Defender-reported active detections require review.' if active else 'No active Defender detections were reported in this snapshot.' if active==0 else 'Active threat status could not be checked.'
    if stale:verdict='Historical snapshot only. '+verdict
    counts={'matched_cves':len({cve for m in software['matches'] for cve in m['cves']}),'affected_products':len({m['product'] for m in software['matches']}),'active_defender_detections':active,'historical_defender_records':history,'unknown_check_fields':len(unknown),'configuration_review_items':sum(f['level'] in ('attention','review') and f['title']!='Old snapshot' for f in findings)}
    return {'schema':SCHEMA,'generated_at':generated.isoformat(),'verdict':verdict,'counts':counts,'findings':findings,'checks':clean,'software':software,'limitations':'Self-reported, editable point-in-time snapshot. Vulnerable software and Defender detections are different counts. Cannot confirm or rule out an ongoing attack, identify all vulnerabilities, scan attached files, or replace antivirus/incident response. No file contents, addresses or device identity are needed.'}

def source(assessment):
    return {'title':'Uploaded laptop security snapshot','url':'','platform':'windows','stage':'unassessed','kind':'device_check','score':None,'text':json.dumps(assessment,ensure_ascii=True),'assessment':'Local checks supplied by the user; not independently verified.'}
