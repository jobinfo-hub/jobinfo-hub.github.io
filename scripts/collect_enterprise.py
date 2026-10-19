#!/usr/bin/env python3
"""Approval-gated Saramin collector. Never publishes fake postings."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'enterprise_jobs.json'
STATUS = ROOT / 'enterprise_status.json'
API = 'https://oapi.saramin.co.kr/job-search'
UTC = dt.timezone.utc

def stamp():
    return dt.datetime.now(UTC).isoformat(timespec='seconds')

def save(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)

def load():
    try:
        obj=json.loads(DATA.read_text(encoding='utf-8'))
        return obj if isinstance(obj.get('jobs'), list) else {'schema_version':1,'updated_at':None,'jobs':[]}
    except (OSError,ValueError,AttributeError):
        return {'schema_version':1,'updated_at':None,'jobs':[]}

def safe_str(v):
    return str(v or '').strip()

def iso_epoch(v):
    try:
        return dt.datetime.fromtimestamp(int(v), UTC).isoformat(timespec='seconds') if v else None
    except (ValueError, TypeError, OverflowError):
        return None

def normalize(raw, seen):
    if not isinstance(raw,dict):return None
    company=raw.get('company') or {}
    position=raw.get('position') or {}
    if not isinstance(company,dict) or not isinstance(position,dict):return None
    name=safe_str((company.get('detail') or {}).get('name') if isinstance(company.get('detail'),dict) else company.get('name'))
    title=safe_str(position.get('title'))
    url=safe_str(raw.get('url'))
    if not name or not title or not url.startswith('https://'):return None
    key=safe_str(raw.get('id')) or hashlib.sha256((name+'|'+title+'|'+url).encode()).hexdigest()[:20]
    previous=seen.get('saramin:'+key,{})
    group=next((g for g,aliases in GROUPS.items() if any(x in name.replace(' ','').lower() for x in aliases)), '기타')
    career=(position.get('experience-level') or {}).get('name','') if isinstance(position.get('experience-level'),dict) else ''
    location=(position.get('location') or {}).get('name','') if isinstance(position.get('location'),dict) else ''
    return {'id':'saramin:'+key,'company':name,'group':group,'title':title,'career':safe_str(career),'location':safe_str(location),'deadline':iso_epoch(raw.get('expiration-timestamp')),'url':url,'source':'사람인','first_seen_at':previous.get('first_seen_at') or stamp(),'last_checked_at':stamp(),'status':'확인 필요'}

GROUPS={'삼성':['삼성'],'SK':['sk','에스케이'],'현대차':['현대자동차','현대모비스','기아'],'LG':['lg','엘지'],'롯데':['롯데'],'포스코':['포스코','posco'],'한화':['한화'],'CJ':['cj','씨제이']}

def collect(key):
    # Endpoint and response fields must be validated against the approved API documentation.
    params={'access-key':key,'count':'100','start':'0'}
    url=API+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':'CareerPick/1.0 (approved API client)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as res:
        payload=json.load(res)
    if not isinstance(payload,dict):raise ValueError('Unexpected API response')
    data=payload.get('jobs')
    if not isinstance(data,dict):raise ValueError('Missing jobs object: verify API response and approval')
    raw=data.get('job',[])
    if isinstance(raw,dict):raw=[raw]
    if not isinstance(raw,list):raise ValueError('Unexpected jobs.job')
    return raw

def main():
    now=stamp()
    key=os.environ.get('SARAMIN_API_KEY','').strip()
    enabled=os.environ.get('ENTERPRISE_COLLECTION_ENABLED','false').lower()=='true'
    if not enabled or not key:
        save(STATUS,{'last_run_at':now,'last_success_at':None,'result':'awaiting_approval','sources':{'saramin':{'state':'disabled','count':0}},'message':'API 승인 및 이용 조건 확인 후 활성화하세요.'})
        print('Approval gate closed: no public jobs changed')
        return 0
    try:
        raw=collect(key)
        old=load()
        seen={j['id']:j for j in old['jobs'] if isinstance(j,dict) and j.get('id')}
        parsed=[normalize(item,seen) for item in raw]
        parsed=[j for j in parsed if j]
        # Fail closed on unexpected empty/malformed responses, preventing data loss.
        if not parsed:raise ValueError('No valid jobs returned; refusing to overwrite existing data')
        combined={j['id']:j for j in old['jobs'] if isinstance(j,dict) and j.get('id')}
        combined.update({j['id']:j for j in parsed})
        save(DATA,{'schema_version':1,'updated_at':now,'jobs':list(combined.values())})
        save(STATUS,{'last_run_at':now,'last_success_at':now,'result':'success','sources':{'saramin':{'state':'ok','count':len(parsed)}},'message':'수집 성공. 페이지 범위 및 사용 조건을 확인하세요.'})
        print(f'Success: {len(parsed)} items received')
        return 0
    except Exception as exc:
        save(STATUS,{'last_run_at':now,'last_success_at':None,'result':'error','sources':{'saramin':{'state':'error','count':0}},'message':str(exc)[:200]})
        print('Collection failed:',type(exc).__name__,str(exc)[:200],file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
