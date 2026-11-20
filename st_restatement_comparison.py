"""Three independent companies share one disclosure date, not three independent regimes."""
from decimal import Decimal as D,ROUND_HALF_UP
from hashlib import sha256
from copy import deepcopy
import json
from canonical_json import digest
from st_period_event_windows import event_windows
PRIOR_KEYS=['twentysixth_period_followup', 'twentyseventh_period_followup', 'lingnan_exit_followup']
SCOPE_KEYS=['twentysixth_period_followup', 'twentyseventh_period_followup', 'lingnan_exit_followup', 'endpoint_selection_audit', 'endpoint_reasons']
PRIOR_DIGEST='79fb462f93986c6500cde29dceeb6b9fda511d6f744907f74dfd6028152a41ba'
SCOPE_DIGEST='9ce71313ce39c69d978578d38f99b38c295d27ad6a6b48978b1c150a3b482b41'
VIEW_DIGEST='7d39ba1b3c8885d95600f96a43ca74d4c54654805abc0047095e85f8319d8344'

def restatement_comparison(inputs,priors):
    packet=inputs.get('restatement_comparison')
    if packet is None:return None
    if packet['version']!=1 or packet['content_digest']!=digest({k:v for k,v in packet.items()if k!='content_digest'}):raise ValueError('restatement comparison packet changed')
    if digest(priors)!=PRIOR_DIGEST or packet['prior_digest']!=PRIOR_DIGEST:raise ValueError('restatement comparison priors changed')
    from st_regime_comparison import build
    i=inputs
    scope={k:i[k]for k in SCOPE_KEYS};scope['market_inputs']=i['current_extension']['market_inputs'];scope['official_index']=next(s for s in i['initial_twentyseventh_four']['cross_sources']if s['key']=='000985')
    if digest(scope)!=SCOPE_DIGEST or packet['scope_digest']!=SCOPE_DIGEST:raise ValueError('restatement comparison source scope changed')
    plan={'603838':('twentysixth_period_followup','1225629182'),'603959':('twentyseventh_period_followup','1225631527'),'002717':('lingnan_exit_followup','1225632584')};source_pool={}
    for key in ['twentysixth_period_followup','twentyseventh_period_followup','lingnan_exit_followup']:
     for s in i[key]['sources']:source_pool[s['announcement_id']]=s
    ids=['1225629182','1225608268','1225516212','1225629255','1225631527','1225631555','1225631518','1225632584','1225644904','1225609701'];source_pool.update({s['announcement_id']:s for s in i['endpoint_reasons']['sources']if s['announcement_id']in ids});sources=[source_pool[a]for a in ids]
    def text(a,n):
     s=source_pool[a];return (s['selected_pages'][str(n)]if 'selected_pages'in s else s['texts'][n-1]).replace(',','').replace(' ','').replace('\n','')
    current='204439311.81';before='173729613.67';after='159424111.01';change='-14305502.66';assert all(x in text('1225516212',5)for x in [current,before,'17.68']);assert all(x in text('1225629182',2)for x in [before,after,change]);assert D(before)+D(change)==D(after)
    a=(D(current)/D(before)-1)*100;b=(D(current)/D(after)-1)*100;assert a.quantize(D('.01'),rounding=ROUND_HALF_UP)==D('17.68');growth=dict(current_h1_revenue=current,old_comparison_h1_revenue=before,corrected_comparison_h1_revenue=after,original_reported_yoy_pct='17.68',original_recomputed_yoy_pct=str(a),corrected_basis_yoy_pct=str(b),original_display_pct='17.68',corrected_display_pct=format(b.quantize(D('.01'),rounding=ROUND_HALF_UP),'.2f'),boundary='更正后的同比为本轮按新比较基数复算，不冒充原半年报当时已经披露；当期收入仍为204439311.81元，且原半年报说明新增并表业务贡献。')
    selected=[]
    for c,(key,aid)in plan.items():
     s=source_pool[aid];selected.append(dict(announcement_id=aid,symbol=c,published_on=s.get('published_on',s.get('announcement_date'))))
    market=i['current_extension']['market_inputs'];raw_windows=event_windows(market,build(market)['daily'],selected,allow_nontraded=True,allow_missing=True);quotes={s['symbol']:s for s in i['endpoint_selection_audit']['sources']if s['symbol']in plan};reviews=[];prices={(r['symbol'],r['trade_date']):r for r in market['fixed_prices']}
    for g in raw_windows:
     s=quotes[g['symbol']];assert sha256(s['text'].encode()).hexdigest()==s['sha256'];data=json.loads(s['text'])['data'][s['provider_key']];q={r[0]:r for r in data.get('qfqday')or data.get('day')or[]}
     for w in g['windows']:
      actual=all(d in q and D(q[d][5])>0 for d in [w['anchor'],w['through']])
      if w['stock_pct']is None:assert not actual;status='nontraded_or_missing';r=None
      else:
       assert actual;assert all(abs(D(q[d][2])-D(str(prices[(g['symbol'],d)]['close'])))<D('1e-9')for d in [w['anchor'],w['through']]);r=(D(q[w['through']][2])/D(q[w['anchor']][2])-1)*100;assert abs(r-D(w['stock_pct']))<D('1e-9');status='matched'
      reviews.append(dict(symbol=g['symbol'],aid=g['aid'],requested_days=w['requested_days'],status=status,cross_return_pct=None if r is None else str(r)))
    index_source=next(s for s in i['initial_twentyseventh_four']['cross_sources']if s['key']=='000985');assert sha256(index_source['text'].encode()).hexdigest()==index_source['sha256'];official={r['tradeDate']:D(str(r['close']))for r in json.loads(index_source['text'])['data']};indices={r['trade_date']:D(str(r['close']))for r in market['benchmarks']if r['benchmark_id']=='csi_all_share'};index_rows=[]
    for d in sorted({d for g in raw_windows for w in g['windows']for d in [w['anchor'],w['through']]}):
     a=indices[d];b=official[d.replace('-','')];assert a.quantize(D('.01'),rounding=ROUND_HALF_UP)==b;index_rows.append(dict(date=d,provider=str(a),official=str(b),difference=str(a-b)))
    index_review={'source':{k:v for k,v in index_source.items()if k!='text'},'rows':index_rows,'precision':'official_two_decimal_places','boundary':'官方精度端点一致不等于原始未取整值完全一致；ST为既有研究序列复算。'}
    refids={s['announcement_id']:{'announcement_id':s['announcement_id'],'symbol':s['symbol'],'title':s['title'],'url':s['url'],'published_on':s.get('published_on',s.get('announcement_date')),'sha256':s['sha256']}for s in sources}
    cases=[{'symbol':'603838','name':'四通','source':'1225629182','affected':'更正2025年前三季度比较数，不涉及年度报表；当期半年收入不变。','update':'重算同比基数，不能把同比读数提高当新增收入。10月20日已摘帽，早于28日更正，不能倒因为果。','operations':'第三季度归母仍亏约1611万元，单季经营现金净流出约3872万元；原半年报另说明新增并表业务贡献。','watch':'继续核可比经营、并表贡献和真实收款；摘帽不等于季度扭亏。','refs':[{'id':'1225629182','pages':[1,2,3]},{'id':'1225608268','pages':[1]},{'id':'1225516212','pages':[5]},{'id':'1225629255','pages':[1]}]}, {'symbol':'603959','name':'百利','source':'1225631527','affected':'更正2026年半年净利润和权益，归母净利润调低约477万元，利润总额不变。','update':'更新半年亏损与权益缓冲，并用更正半年数衔接季度。利润总额不变，不等于净利润未变。','operations':'第三季度直接归母亏约1.29亿元；更正半年差额衔接保留0.01元差异，更正半年扣非缺直接值不补造。','watch':'核政策原文、更正依据及主营收款；部分赠与收款另核，不混成经营盈利。','refs':[{'id':'1225631527','pages':[2]},{'id':'1225631555','pages':[2,3]},{'id':'1225631518','pages':[1,2]}]}, {'symbol':'002717','name':'岭南','source':'1225632584','affected':'更正2021—2025年度及2026年一季度，2025年归母多亏约47万元，合并总权益仍为负。','update':'更新历史数值和对应口径；此前连续低于面值触发及10月13日停牌不被更正公告替代。','operations':'第三季度归母亏约1.27亿元，前三季现金净流入约2659万元；最终决定与摘牌仍未认证。','watch':'等正式最终文件及新时点回款，保留停牌端点空值；旧余额不冒充最新余额。','refs':[{'id':'1225632584','pages':[1,5,6,9]},{'id':'1225644904','pages':[2,6]},{'id':'1225609701','pages':[1]}]}]
    result=dict(through='2026-11-19',title='财报更正后，应该改哪一层判断？',answer='先确认更正影响的是当期数字、历史比较基数，还是风险条件。四通先摘帽后更正；百利半年亏损扩大；岭南更正后仍保留交易触发与退出程序缺口。三种情况不能统一当成经营改善或摘帽催化。',cases=cases,growth_recalculation=growth,event_windows=raw_windows,window_reviews=reviews,source_refs=list(refids.values()),index_review=index_review,counts=dict(companies=3,common_disclosure_dates=1,windows=9,complete_windows=6,unfinished_windows=3,matched_stock_windows=6,nontraded_stock_windows=3,new_primary_documents=0,reused_primary_documents=10,new_quote_requests=0,independent_regime_tests=0),experience=dict(status='阅读方法归纳，行情假设仍待检验',retain='先核影响期间和科目，再分别更新同比、经营与风险条件；用实际发生顺序检查解释，保留反例和空值。',not_supported='更正通常利好、摘帽后必涨、现金转正就恢复，均不能由这组三家公司确认。',falsification='若新原件、可比口径或正式程序推翻当前事实，逐项改判断；若要检验行情预测，还需其他独立时段与事先定义的样本，不能把同日横截面或重复窗口当多次验证。'),boundaries=['三家公司共用10月28日披露日，是一个同期横截面，不是三段独立市场检验。','同日还披露季度报告或其他事项，且四通摘帽在更正之前；同窗涨跌不识别更正公告净影响。','20日窗口截至11月19日仅17个市场日，统一标未满；岭南停牌无共同成交端点，收益留空，不借最后交易价。','旧财务差异、原价接口限制、最终退出原件及完整历史名单缺口仍保留，不自动晋级经验方法。'],method_promotions=0)
    if digest(result)!=VIEW_DIGEST or packet['result']!=result:raise ValueError('restatement comparison result changed')
    return deepcopy(result)
