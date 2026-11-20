import {useState} from 'react'
type Stats={members:number;primary_paired:number;primary_missing:number;verified_paired:number;unverified_paired:number;primary_median_pct:string|null;verified_subset_median_pct:string|null;verified_subset_positive:number;verified_subset_positive_denominator:number}
type Point={side:string;date:string;primary_state:string;primary_close:string|null;cross_close:string|null;difference:string|null;status:string}
type Row={symbol:string;name:string;provider_st_at_end:boolean;primary_return_pct:string|null;certified_return_pct:string|null;cross_return_pct:string|null;status:string;endpoints:Point[];existing_gap:string|null;source_sha256:string}
export type EndpointSelectionAudit={prior_snapshot:string;windows:{key:string;anchor:string;through:string;summary:Stats;groups:(Stats&{group:string})[];rows:Row[]}[];source_refs:{symbol:string;url:string;observed_at:string;sha256:string;reused_from_input:string|null}[];boundaries:string[]}
const pct=(s:string|null)=>s==null?'不计算':`${Number(s)>0?'+':''}${Number(s).toFixed(2)}%`
export function STEndpointSelectionAudit({data:d}:{data?:EndpointSelectionAudit|null}){
 const [key,setKey]=useState('full')
 if(!d)return null
 const w=d.windows.find(x=>x.key===key)??d.windows[0],s=w.summary,conflicts=w.rows.filter(r=>r.status==='quote_conflict_or_unverified')
 return <section className="regime-reading-section" aria-label="固定样本全量核价与选择范围">
  <h4>有成交、核价通过和仍在ST名单，是三件事</h4>
  <p>150家原样本全部保留。完整区间146家两端有成交，其中141家跨渠道复权端点一致，5家起点报价仍有差异；另4家缺成交端点。最近9日147家两端有成交，147家均一致，另3家缺端点。</p>
  <label>核对哪段窗口？<select aria-label="全量核价观察窗口" value={w.key} onChange={e=>setKey(e.target.value)}><option value="full">7月3日 → 11月19日</option><option value="recent">11月6日 → 11月19日</option></select></label>
  <table className="regime-table" aria-label="成交与核价范围"><thead><tr><th>原样本</th><th>主源两端有成交</th><th>跨渠道核价通过</th><th>报价仍待核</th><th>缺成交端点</th></tr></thead><tbody><tr><td>{s.members}</td><td>{s.primary_paired}</td><td>{s.verified_paired}</td><td>{s.unverified_paired}</td><td>{s.primary_missing}</td></tr></tbody></table>
  <p>核价通过子样本中位数{pct(s.verified_subset_median_pct)}，上涨{s.verified_subset_positive}/{s.verified_subset_positive_denominator}家。这只描述通过核价的子样本，不冒充全部150家的收益。原主源配对子样本中位数{pct(s.primary_median_pct)}，作为旧口径保留。</p>
  <h5>只看期末仍在ST名单，会漏掉什么？</h5><p>期末提供方名单仍有136家，另14家已不在名单。离开名单可能涉及摘帽、退市或名单口径，不能一律当成成功案例，也不能一律当成亏损。分组使用后来才知道的状态，只作事后核对。</p>
  <div className="regime-scroll"><table className="regime-table" aria-label="期末状态分组对照"><thead><tr><th>提供方期末状态</th><th>原样本数</th><th>核价通过</th><th>报价待核 / 缺端点</th><th>通过子样本中位数</th></tr></thead><tbody>{w.groups.map(g=><tr key={g.group}><th>{g.group==='provider_st_at_end'?'仍在ST参考名单':'不在ST参考名单'}</th><td>{g.members}</td><td>{g.verified_paired}</td><td>{g.unverified_paired} / {g.primary_missing}</td><td>{pct(g.verified_subset_median_pct)}</td></tr>)}</tbody></table></div>
  <details><summary>哪些报价仍待核？查看两源原值</summary>{conflicts.length===0?<p>本窗口有成交的147家端点均跨渠道一致。完整区间的起点差异没有因此解除。</p>:conflicts.map(r=><article key={r.symbol}><h5>{r.name} · {r.symbol}</h5><p>认证收益留空；主源未认证值{pct(r.primary_return_pct)}，另一渠道同窗{pct(r.cross_return_pct)}。</p>{r.endpoints.map(e=><p key={e.side}>{e.date}：主源前复权{e.primary_close??'缺价'}元，另一渠道{e.cross_close??'缺价'}元；{e.status==='matched'?'端点一致':'端点待核'}。</p>)}<a href={d.source_refs.find(s=>s.symbol===r.symbol)!.url} target="_blank" rel="noreferrer">对应跨渠道行情响应 ↗</a></article>)}</details>
  <details><summary>保留全部150家及每家的核验状态</summary><div className="regime-scroll"><table className="regime-table" aria-label="全量150家认证收益"><thead><tr><th>代码与历史名称</th><th>核价通过收益</th><th>范围</th></tr></thead><tbody>{w.rows.map(r=><tr key={r.symbol}><th>{r.symbol} {r.name}</th><td>{r.status==='matched'?pct(r.certified_return_pct):r.status==='primary_endpoint_gap'?'端点不足，留空':'报价待核，留空'}</td><td>{r.provider_st_at_end?'仍在期末参考名单':'不在期末参考名单'}{r.existing_gap&&<small>{r.existing_gap}</small>}</td></tr>)}</tbody></table></div></details>
  <details><summary>来源、复用与结论边界</summary><p>本轮复用已留档的全窗行情响应，只补取缺少全窗响应的代码。观察时间不改写为原研究当时已知；跨渠道一致不证明底层行情来源完全独立。复权价格用于收益比较，不是未经调整的实际交易价。</p>{d.boundaries.map(b=><p key={b}>{b}</p>)}</details>
 </section>
}
