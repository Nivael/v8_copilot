import {useState} from 'react'
import {STRecoveryPath} from './STRecoveryPath'
import type {MarketStageExperience} from './stRegimeTypes'
const pct=(s:string)=>`${Number(s).toFixed(2)}%`
export function STMarketStageExperience({data}:{data?:MarketStageExperience|null}){
 const [common,setCommon]=useState(false)
 const [stage,setStage]=useState(0)
 if(!data)return null
 const selected=data.stages[stage]
 return <section id="st-market-stage-experience" aria-label="ST分阶段经验检验" style={{scrollMarginTop:80}}>
  <h2>{data.title}</h2><p>{data.answer}</p>
  <p>行情截至2026年11月19日。7月从3日收盘起，11月只到19日；表内是同窗表现，不是制度净效果。</p>
  <label><input type="checkbox" checked={common} onChange={e=>setCommon(e.target.checked)}/>用五段都通过核价的同一139家公司比较</label>
  <table className="regime-table"><caption>动态ST参考与大盘；固定150只原样本中核价通过子样本的分布</caption><thead><tr><th>观察区间</th><th>ST参考</th><th>中证全指</th><th>ST相对大盘</th><th>个股中位数</th><th>上涨／可比</th></tr></thead><tbody>{data.stages.map(s=><tr key={s.anchor}><th>{s.anchor} → {s.through}<small> {s.market_days}个市场日</small></th><td>{pct(s.st_pct)}</td><td>{pct(s.market_pct)}</td><td>{Number(s.st_minus_market_pp).toFixed(2)}个百分点</td><td>{pct(common?s.common_sample.median_pct:s.verified_median_pct)}</td><td>{common?s.common_sample.positive:s.verified_positive}／{common?s.common_sample.members:s.verified_paired}</td></tr>)}</tbody></table>
  <p>{common?data.common_sample_boundary:'各段可比数量不同；未通过核价、停牌和退出缺端点仍保留在150家明细，收益不填零。'}</p>
  <STRecoveryPath data={data}/>
  <h3>这会怎样改变原判断？</h3><p>{data.what_changed}</p>
  <h3>能留下什么，不能推出什么？</h3><p>{data.kept}</p><p>{data.not_established}</p>
  <details><summary>查看每段分母和全部150家核验状态</summary>
   <label>核对哪段？ <select value={stage} onChange={e=>setStage(Number(e.target.value))}>{data.stages.map((s,n)=><option key={s.anchor} value={n}>{s.anchor} → {s.through}</option>)}</select></label>
   <p>原样本150家；主源两端有成交{selected.primary_paired}家，跨源核价通过{selected.verified_paired}家，报价待核{selected.unverified_paired}家，缺主源成交端点{selected.primary_gaps}家。</p>
   <table className="regime-table"><caption>全部150家逐段核验，缺值保留</caption><thead><tr><th>代码</th><th>核验状态</th><th>核价通过收益</th><th>主源收益</th><th>起点／终点</th></tr></thead><tbody>{selected.rows.map(r=><tr key={r.symbol}><th><a href={data.source_refs.find(s=>s.symbol===r.symbol)?.url} target="_blank" rel="noreferrer">{r.symbol}</a></th><td>{r.status==='matched'?'两源一致':r.status==='primary_gap'?'缺成交端点':'报价待核'}</td><td>{r.certified_return_pct===null?'不计算':pct(r.certified_return_pct)}</td><td>{r.return_pct===null?'不计算':pct(r.return_pct)}</td><td>{r.endpoints.map(e=><span key={e.date}>{e.date}：{e.primary_close??'无主源成交'}／{e.cross_close??'无跨源成交'}<br/></span>)}</td></tr>)}</tbody></table>
  </details>
  <details><summary>来源、检验边界与证伪条件</summary><p>{data.boundary}</p><p>复用150份跨源历史响应、主源历史行情与官方指数原响应。六个唯一日期共900个逐股端点位置；相邻区间共用边界，不计为新增独立证据。ST参考仅复算既有研究序列，未认证完整官方逐日成员名单。</p><p><a href={data.official_index_source.url} target="_blank" rel="noreferrer">官方中证全指原响应</a> · 股票逐家历史响应链接在上方150家明细代码中，原观察时间和文件摘要随快照保留。</p><p>{data.falsification}</p></details>
 </section>
}
