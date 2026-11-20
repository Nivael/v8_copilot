import {useState} from 'react'
import audit from './cashMarketComparison.json'
import type {STRegimeData} from './stRegimeTypes'

type Window={through:string|null;stock_pct:number|null;market_pct:number|null;st_pct:number|null}
type Event={id?:string;event_id?:string;published_on:string;windows?:Record<string,Window>;observation?:{anchor:string;windows:Record<string,Window>}}
export function cashMarketBound(data:STRegimeData){
 if(data.through!==audit.observation_cutoff)return false
 const themes=data.themes as unknown as Record<string,Record<string,unknown>>|undefined
 if(JSON.stringify(themes?.removal_followup?.warning)!==JSON.stringify(audit.warning_binding))return false
 return audit.rows.every(row=>{
  const theme=themes?.[row.theme]
  const events=(theme?.[row.theme==='removal_followup'?'new_event_windows':'observations']??[]) as Event[]
  const event=events.find(e=>(e.event_id??e.id)===row.event_id)
  if(!event||event.published_on!==row.anchor)return false
  const windows=event.windows??event.observation?.windows
  return Object.entries(row.windows).every(([n,w])=>{
   const actual=windows?.[n]
   return actual&&Object.entries(w.expected).every(([k,v])=>JSON.stringify((actual as unknown as Record<string,unknown>)[k])===JSON.stringify(v))
  })
 })
}
const pct=(n:number|null)=>n===null?'缺成交端点':`${n>0?'+':''}${n.toFixed(2)}%`
export function STCashMarketComparison({data}:{data:STRegimeData}){
 const [horizon,setHorizon]=useState<'1'|'5'>('5')
 if(!cashMarketBound(data))return <p role="status">行情对照尚未与当前证据对应，暂不显示旧窗口结论。</p>
 const cash=audit.rows[0].windows['20']!
 return <section aria-label="兑现事项与同期行情对照">
  <h4>实际进展发生后，股价一定上涨吗？</h4>
  <p><strong>事实推进与价格上涨，需要分别判断。</strong>京蓝披露补偿已收齐后，下一交易日上涨{Math.abs(audit.rows[0].windows['1']!.stock!).toFixed(2)}%，但20个市场交易日后为{pct(cash.stock)}；神雾过户披露后的5日下跌{Math.abs(audit.rows[2].windows['5']!.stock!).toFixed(2)}%，同时比同期大盘和ST参考跌得少。不能仅凭后来下跌否定已完成的交付，也不能用进展属实承诺上涨。</p>
  <div role="group" aria-label="选择公告后比较长度">{(['1','5'] as const).map(n=><button type="button" key={n} aria-pressed={horizon===n} onClick={()=>setHorizon(n)}>公告日收盘后{n}个市场交易日</button>)}</div>
  <p>每件事项从各自公告日收盘起算；日期不同，长度一致。表内个股、ST参考与大盘使用同一起止日，不包含公告日当天涨跌，也不代表最早市场反应或可执行买入收益。</p>
  <div className="table-scroll"><table><caption>各事项公告日收盘后{horizon}个市场交易日的表现</caption><thead><tr><th scope="col">事项</th><th scope="col">起止收盘日</th><th scope="col">个股</th><th scope="col">动态ST参考</th><th scope="col">大盘·中证全指</th></tr></thead><tbody>{audit.rows.map(row=>{
   const w=row.windows[horizon]!
   return <tr key={row.event_id}><th scope="row">{row.title}</th><td>{row.anchor} → {w.end}</td><td>{pct(w.stock)}</td><td>{pct(w.st)}</td><td>{pct(w.market)}</td></tr>
  })}</tbody></table></div>
  {horizon==='5'?<p>京蓝收齐补偿后的第5个市场交易日是8月28日，当日停牌，个股端点留空；不填零、不顺延，也不把大盘和ST的涨幅当作京蓝表现。另一批补偿追偿披露后，京蓝5日下跌14.64%，同期大盘上涨0.65%、ST参考上涨1.02%，仅凭大盘方向不能解释这段背离。</p>:<p>两件京蓝事项的下一交易日都上涨，但“款已收齐”与“仍在追偿”是不同事实，不能从单日同涨把兑现程度判成相同。两行属于同一家公司，也不是两次独立实验。</p>}
  <details><summary>京蓝：首日上涨，为何还要看20日与期间新消息？</summary><p>{audit.rows[0].anchor} → {cash.end}，个股{pct(cash.stock)}，大盘{pct(cash.market)}，动态ST参考{pct(cash.st)}。个股相对大盘落后{Math.abs(cash.stock_minus_market_pp!).toFixed(2)}个百分点。这是同期差额，尚未控制其他影响，不能称作公告净效应。</p><p>期间8月25日另有摘帽申请，8月28日摘帽公告且股票停牌，8月31日起恢复交易并撤销其他风险警示，9月2日又披露另一批补偿追偿的更正公告。20日窗口叠加这些新消息，不能全归于8月21日收齐补偿，也不能倒填为当时已知。</p><a href={audit.warning_binding.source.url} target="_blank" rel="noreferrer">核对摘帽与停复牌公告 ↗</a> · <a href="#st-removal-followup">回到京蓝完整事项与摘帽时间线 →</a></details>
  <p>岭南10月28日公告时股票已停牌，本表不补造一段公告后成交收益。这里比较的是两家公司三件事项的历史窗口，不将四件事项强行凑成完整收益样本。</p>
  <details><summary>查看端点、行情来源与复核范围</summary>
   <p>旧研究资料截至{audit.observation_cutoff}。本表重算已保存的7个窗口，不把旧短窗称为截至11月19日的最新表现；其中1个窗口股票缺成交端点。个股采用同基准前复权收盘，并以已保存腾讯原价/前复权两路核对；大盘按保存的中证全指收盘重算，ST按保存的动态参考线重算。动态参考并非独立官方ST指数，京蓝摘帽后个股仍保留、动态ST成员会变化。</p>
   <p>算法为（期末收盘÷起点收盘−1）×100；市场交易日窗口保留股票停牌。核对{audit.unique_stock_date_positions}个唯一股票日期位置，其中1个无成交；重复端点不增加独立样本数。</p>
   {audit.rows.map(row=><article key={row.event_id}><h5>{row.title} · 当前{horizon}日窗口端点</h5>{row.windows[horizon]!.points.map(p=><p key={p.date}>{p.date}：个股{p.stock_close??'无成交端点'}；中证全指{p.market_close}；ST参考点位{p.st_level}。</p>)}</article>)}
   {audit.quote_sources.map(s=><p key={s.sha256}>{s.symbol} · {s.key} · <a href={s.url} target="_blank" rel="noreferrer">原行情请求 ↗</a> · 保存SHA256：<code>{s.sha256}</code></p>)}
   <p>本轮没有新请求；独立渠道核对的是股票价格，不声称重新取得独立官方ST指数或重新检验全部历史成员。原快照：<code>{audit.snapshot_digest}</code>。</p>
  </details>
 </section>
}
