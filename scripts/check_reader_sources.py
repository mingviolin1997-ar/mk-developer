#!/usr/bin/env python3
"""Check upstream originals without evaluating scripts or replacing vetted configs."""
import concurrent.futures, datetime, hashlib, html, ipaddress, json, pathlib, urllib.request, urllib.parse
ROOT=pathlib.Path(__file__).resolve().parents[1]
MAX_BYTES=8*1024*1024
PUBLIC='https://dev.mk-musician.com/reader-sources/upstream-status.json'
UPSTREAMS=[
 {'id':'legado-xiu2','name':'Legado公开格式样本（XIU2）','urls':['https://raw.githubusercontent.com/XIU2/Yuedu/master/shuyuan'],'mode':'monitor-only'},
 {'id':'dahuilang','name':'大灰狼','urls':['https://api.langge.cf/version','https://20.langge.tk/version','https://v4.czyl.cf/version'],'mode':'version-api'},
]
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def allowed(url):
 p=urllib.parse.urlsplit(url)
 if p.scheme!='https' or p.username or p.password or p.port or not p.hostname or '.' not in p.hostname or p.hostname.endswith(('.local','.localhost')): raise ValueError('unsafe URL')
 try: ipaddress.ip_address(p.hostname)
 except ValueError: pass
 else: raise ValueError('IP literal not allowed')
 return url
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  allowed(newurl)
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(url):
 req=urllib.request.Request(allowed(url),headers={'User-Agent':'AccessReader-SourceCheck/1.0','Cache-Control':'no-cache'})
 with urllib.request.build_opener(Redirect()).open(req,timeout=15) as r:
  data=r.read(MAX_BYTES+1)
 if len(data)>MAX_BYTES: raise ValueError('response too large')
 return data

def check(entry,previous,download=fetch,timestamp=None):
 stamp=timestamp or now()
 result={k:entry[k] for k in ('id','name','mode')}
 result.update(checkedAt=stamp,status='failed')
 if previous.get('lastSuccess'): result['lastSuccess']=previous['lastSuccess']
 for url in entry['urls']:
  try:
   data=download(url);obj=json.loads(data)
   if entry['mode']=='version-api':
    version=obj['version3']
    if not isinstance(version,str) or len(version)>80 or not all(p.isdigit() for p in version.split('.')): raise ValueError('invalid version')
    success={'version':version,'notes':str(obj.get('update_log',{}).get(version,''))[:4000]}
   else:
    values=obj if isinstance(obj,list) else [obj]
    if not values or len(values)>500 or not all(isinstance(v,dict) and isinstance(v.get('bookSourceUrl'),str) and isinstance(v.get('bookSourceName'),str) for v in values): raise ValueError('not Legado sources')
    success={'sourceCount':len(values),'sha256':hashlib.sha256(data).hexdigest()}
   success.update(checkedAt=stamp,url=url)
   result.update(status='checked',lastSuccess=success)
   if previous.get('lastSuccess'):
    before={k:v for k,v in previous['lastSuccess'].items() if k not in ('checkedAt','url')}
    after={k:v for k,v in success.items() if k not in ('checkedAt','url')}
    result['changedSincePreviousCheck']=before!=after
   return result
  except (OSError,ValueError,KeyError,TypeError): continue
 result['message']='本次检查失败；上次成功结果不代表当前最新。'
 return result

def main():
 output=ROOT/'docs/reader-sources/upstream-status.json'
 previous={}
 try:
  old=json.loads(fetch(PUBLIC));previous={e['id']:e for e in old.get('upstreams',[])}
 except (OSError,ValueError,KeyError,TypeError):
  if output.exists():
   old=json.loads(output.read_text());previous={e['id']:e for e in old.get('upstreams',[])}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  entries=list(pool.map(lambda e:check(e,previous.get(e['id'],{})),UPSTREAMS))
 managed=[]
 for file in ['sources-v1.json','shenhua-v1.json','sangshi-v1.json','luoxia-v1.json','discovery-sources-v1.json']:
  data=(output.parent/file).read_bytes();obj=json.loads(data)
  if obj.get('format')!='xiaoming-reader-sources' or not obj.get('sources'): raise ValueError('invalid maintained config')
  managed.append({'file':file,'sha256':hashlib.sha256(data).hexdigest(),'sourceCount':len(obj['sources']),'maintenance':'developer-maintained; no separate upstream URL'})
 report={'format':'accessreader-source-status','version':1,'checkedAt':now(),'scheduledIntervalMinutes':30,'scheduleMayBeDelayed':True,'scope':'配置版本检测，不代表网站可读性；原始脚本不执行，不自动替换已验证配置。','upstreams':entries,'maintainedFiles':managed}
 temp=output.with_suffix('.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');temp.replace(output)
 rows=[]
 for entry in entries:
  successful=entry.get('lastSuccess',{})
  value=successful.get('version') or (str(successful['sourceCount'])+'个原始书源；仅检测配置变化' if 'sourceCount' in successful else '尚无成功结果')
  status='检查成功' if entry['status']=='checked' else '本次检查失败'
  rows.append('<li><h2>'+html.escape(entry['name'])+'</h2><p>'+html.escape(status+'：'+value)+'</p><p>上次成功：'+html.escape(successful.get('checkedAt','无'))+'</p></li>')
 page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>书源更新检测</title><style>body{font:20px/1.8 system-ui;max-width:760px;margin:auto;padding:24px;color:#161616;background:#fff}li{margin:24px 0}a:focus{outline:3px solid #0058bd}</style><main><h1>书源更新检测</h1><p>计划每30分钟检查一次，调度可能延迟。检查配置版本不代表所有网站可阅读；不会自动替换手机书源。</p><p>本次运行：'+html.escape(report['checkedAt'])+'</p><ul>'+''.join(rows)+'</ul><p>小铭维护的五个网站配置随开发者修复发布，不存在独立的第三方版本接口。</p><a href="../reader-guide/">返回使用引导</a></main></html>'
 (output.parent/'update-status.html').write_text(page)
 print(json.dumps({'checked':len(entries),'failed':sum(e['status']=='failed' for e in entries),'maintained':len(managed)}))
if __name__=='__main__': main()
