"""Verify dated pre-rule exits without promoting a partial chain into a complete official list."""
from decimal import Decimal as D
from hashlib import sha256
from collections import Counter
from urllib.parse import urlparse
import re,unicodedata
from canonical_json import digest
KEYS=('calendar','through','members','dynamic_reference_audit','member_entries','member_transitions')
def scope_digest(i):return digest({k:i[k]for k in KEYS})
def norm(t):return re.sub(r'\s+','',unicodedata.normalize('NFKC',t))
def document_date(s):
 t=norm(s['selected_pages'][str(s['pages'])]);tail=t[t.rfind('董事会'):]if'董事会'in t else t[-250:]
 dates=re.findall(r'(?:2026|二[〇○零OＯ]二六)年([一二三四五六七八九十〇零0-9]{1,3})月([一二三四五六七八九十〇零0-9]{1,3})日',tail)
 def num(x):
  if x.isdigit():return int(x)
  v={c:n for n,c in enumerate('零一二三四五六七八九')};return(v.get(x.split('十')[0],1)*10+v.get(x.split('十')[1],0))if'十'in x else v[x]
 return f'2026-{num(dates[-1][0]):02d}-{num(dates[-1][1]):02d}'if dates else None

def pre_rule_membership_view(i):
 p=i.get('pre_rule_membership')
 if p is None:return None
 if p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'})or p['scope_digest']!=scope_digest(i)or p['through']!=i['through']:raise ValueError('pre-rule membership binding changed')
 fixed={r['symbol']for r in i['members']if r['trade_date']=='2026-07-03'and r['symbol'].startswith(('000','001','002','003','600','601','603','605'))};all_subjects={c['symbol']for c in i['dynamic_reference_audit']['original_prices']['companies']};subjects={s for s in all_subjects-fixed if any(r['symbol']==s and r['trade_date']<='2026-07-03'for r in i['members'])};rows=p['rows'];sources={s['announcement_id']:s for s in p['sources']}
 if len(rows)!=48 or len(sources)!=48 or len(p['sources'])!=48 or {r['symbol']for r in rows}!=subjects:raise ValueError('pre-rule 48 boundary scope changed')
 for s in sources.values():
  if not s['protected_gate_passed']or len(s['selected_pages'])!=s['pages']or s['source_format']not in ('pdf_official','pdf_mirror'):raise ValueError('pre-rule unverified source body')
  if s['host_is_official']!=(s['source_format']=='pdf_official')or s['host_is_official']!=(urlparse(s['url']).hostname in {'disc.static.szse.cn','static.cninfo.com.cn','dataclouds.cninfo.com.cn','www.sse.com.cn','static.sse.com.cn'}):raise ValueError('mirror became official original')
  for page,t in s['selected_pages'].items():
   if sha256(norm(t).encode()).hexdigest()!=s['page_text_hashes'][int(page)-1]:raise ValueError('pre-rule page text changed')
 result=[]
 for r in rows:
  s=sources[r['source_id']];head=norm(s['selected_pages'][str(r['source_page'])]);body=norm(''.join(s['selected_pages'].values()));symbol=r['symbol'];effective=r['effective_on'];y,m,d=effective.split('-');token=f'{y}年{int(m)}月{int(d)}日';iso=f'{y}/{int(m)}/{int(d)}';dates=sorted(x['trade_date']for x in i['members']if x['symbol']==symbol and x['trade_date']<='2026-07-03');first=dates[0];last=dates[-1];nextday=i['calendar'][i['calendar'].index(last)+1]
  if r['first_provider_member']!=first or r['last_provider_member']!=last or r['member_days']!=len(dates)or effective!=nextday or effective!=r['first_provider_absent']or effective>='2026-07-06':raise ValueError('pre-rule provider boundary differs')
  if symbol!=s['symbol']or symbol not in head or(token not in head and iso not in head)or r['metadata_published_on']!=s['published_on']or s['published_on']>effective:raise ValueError('pre-rule issuer or effective date absent')
  expected_level='official_body'if s['host_is_official']else'exchange_catalog_plus_pdf_mirror'
  if r['verification_level']!=expected_level:raise ValueError('pre-rule provenance overstated')
  if r['document_dated_on']!=document_date(s)or r['date_conflict']!=bool(r['document_dated_on']and r['document_dated_on']>r['metadata_published_on']):raise ValueError('document date conflict was hidden')
  kind=r['kind']
  if kind=='warning_removed':
   if '撤销'not in head or not r['post_name']or r['post_name']not in head or re.search(r'ST|退市',r['post_name'],re.I):raise ValueError('partial warning removal became full exit')
   if not re.search(r'涨跌幅.{0,60}?10%',body):raise ValueError('post-removal limit unsupported')
   if r['band_page']:
    t=norm(s['selected_pages'][str(r['band_page'])])
    if r['band_excerpt']not in t or not re.search(r'涨跌幅.{0,50}?(?<!\d)5%.{0,35}?10%',r['band_excerpt']):raise ValueError('explicit old band unsupported')
  elif kind=='terminal_entry':
   if '退市整理期'not in head or not any(k in head for k in ('起始','进入')):raise ValueError('terminal start not supported')
  elif kind=='delisted':
   if '摘牌'not in head or '摘牌'not in s['title']:raise ValueError('delisting date unsupported')
  else:raise ValueError('unknown pre-rule exit classification')
  src={k:v for k,v in s.items()if k not in ('selected_pages','page_text_hashes','rank')};src['page']=r['source_page']
  result.append({**r,'source':src,'source_sha256':s['sha256'],'matches_provider_boundary':True,'old_band_explicit':bool(r['band_page'])})
 counts=Counter(r['kind']for r in result);mirrors=sum(not s['host_is_official']for s in sources.values());return {'through':i['through'],'answer':f'制度前48处移出边界均已对照所读公告日期：{counts["warning_removed"]}次撤销风险警示、{counts["terminal_entry"]}次进入退市整理、{counts["delisted"]}次公告摘牌。43份来自官方文档，5份为发行人公告PDF镜像并与交易所目录核对；镜像不冒充已取到官方原PDF字节。','rows':result,'total':len(result),'warning_removed':counts['warning_removed'],'terminal_entry':counts['terminal_entry'],'delisted':counts['delisted'],'official_body_files':48-mirrors,'mirror_files':mirrors,'files':48,'pages':sum(s['pages']for s in sources.values()),'explicit_5_to_10':sum(r['kind']=='warning_removed'and r['old_band_explicit']for r in result),'post_rule_removed':sum(r['status']=='warning_removed'for r in i['member_transitions']['rows']),'date_conflicts':sum(r['date_conflict']for r in result),'catalog_companies':p['catalog_summary']['complete'],'catalog_rows':p['catalog_summary']['rows'],'catalog_pages':p['catalog_summary']['pages'],'boundary':'核的是48处移出生效边界，不是197只期初全名单、7月3日150只或125日全体成员的独立官方认证。整理期开始不等于当日已摘牌；后来再次ST与历史首次分开。目录元数据日期与原文落款冲突保留；五份镜像的官方PDF原字节仍待补。不由摘帽、独立公司数量或重复公告推导制度净因果或经验验证次数。'}

def boundary_price_inputs(i):
 if not i.get('pre_rule_membership'):return i
 # Extend only temporary event-window inputs, leaving all frozen input keys untouched.
 prior={(r['symbol'],r['trade_date']):r for r in i['fixed_prices']};prior_symbols={s for s,_ in prior};extra=[]
 for c in i['dynamic_reference_audit']['original_prices']['companies']:
  if c['symbol'] in prior_symbols:continue
  factor=next((r['adj_factor']for r in reversed(c['rows'])if r['adj_factor']and r['adj_factor']>0),None)
  for r in c['rows']:
   key=(c['symbol'],r['date'])
   if key in prior:continue
   close=float(D(str(r['raw_close']))*D(str(r['adj_factor']))/D(str(factor)))if r['raw_close']is not None and r['adj_factor']and factor else None
   extra.append({'symbol':c['symbol'],'trade_date':r['date'],'close':close,'has_trade':r['has_trade'],'source':'frozen_provider_cache_for_pre_rule_boundary_context'})
 return {**i,'fixed_prices':[*i['fixed_prices'],*extra]}
