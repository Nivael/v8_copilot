import {useState} from 'react'
import {ReadingChart} from './ReadingChart'
import {percent} from './readingFormat'
import {useReadingView} from './useReadingView'
import type {SwingReading} from './readingTypes'

const stages:Record<string,string>={early_repair:'价格初步修复',rebounded_far:'已反弹较多',still_weak:'仍在弱势',not_in_screen:'未满足本次筛选',liquidity_insufficient:'成交或价格条件不足'}

export function SwingWatchSection(){
  const {packet,error,busy,reload}=useReadingView<SwingReading>('swing')
  const [groupKey,setGroupKey]=useState('star50')
  const [symbol,setSymbol]=useState<string|null>(null)
  const [expanded,setExpanded]=useState(false)
  const data=packet?.data
  if(!data||data.availability!=='available')return <section className="reading-section"><h2>1–4周反弹观察</h2><p className="reading-muted">{error||'正在整理科创50和ST池的最新观察。'}</p></section>
  const group=data.groups.find(item=>item.key===groupKey)||data.groups[0]
  const focused=group.rows.find(row=>row.symbol===(data.analysis?.focus_by_group?.[group.key]||data.analysis?.preferred_symbol))
  const selected=group.rows.find(row=>row.symbol===symbol)||focused||group.rows[0]
  const tableRows=focused?[focused,...group.rows.filter(row=>row.symbol!==focused.symbol)]:group.rows
  return <section className="reading-section reading-swing" aria-label="1–4周反弹观察"><header className="reading-page-head"><div><p className="reading-kicker">寻找新的观察对象</p><h2>1–4周反弹观察</h2><p>收盘截至 {data.as_of} · 先筛价格，再核公司事实</p></div><button className="reading-sync" onClick={reload} disabled={busy}>{busy?'同步中…':'同步观察'}</button></header>
    {data.analysis&&<div className="reading-swing-judgment"><h3>{data.analysis.headline}</h3><p>{data.analysis.summary}</p></div>}
    {data.analysis?.previous_review&&<details className="reading-disclosure"><summary>上次的判断，还成立吗？</summary><p>上次基于 {data.analysis.previous_review.basis_date} 收盘。本次对照至 {data.as_of}；这段后续仍不足以检验完整的1–4周结果。</p><p>{data.analysis.previous_review.summary}</p><div className="reading-scroll"><table><thead><tr><th>标的</th><th>上次判断</th><th>最新交易日</th><th>本次复核</th></tr></thead><tbody>{data.analysis.previous_review.cases.map(row=><tr key={row.symbol}><th>{row.name}</th><td>{row.then_judgment}</td><td>{percent(row.day_change_pct)}</td><td>{row.now_judgment}</td></tr>)}</tbody></table></div></details>}
    <div className="reading-filters" role="group" aria-label="反弹观察范围">{data.groups.map(item=><button key={item.key} aria-pressed={group.key===item.key} onClick={()=>{setGroupKey(item.key);setSymbol(null);setExpanded(false)}}>{item.name}</button>)}</div>
    <p className="reading-caption">{group.name}共{group.pool_count}只，可比行情{group.observed_count}只；{group.oversold_count}只达到本次超跌条件，其中{group.early_repair_count}只符合初步修复条件。{group.excluded.length>0&&`${group.excluded.length}只停牌或行情不齐，已单列。`}</p>
    {!group.rows.length?<p>当前没有满足这组价格条件的股票。</p>:<><p className="reading-caption">点股票名称，查看公司判断和接下来要等的条件。</p><div className="reading-scroll"><table><thead><tr><th>股票</th><th>近20日</th><th>近5日</th><th>价格状态</th></tr></thead><tbody>{(expanded?tableRows:tableRows.slice(0,8)).map(row=><tr key={row.symbol}><th><button className="reading-stock-choice" aria-pressed={row.symbol===selected?.symbol} onClick={()=>setSymbol(row.symbol)}>{row.name}</button><small className="reading-code">{row.symbol}</small></th><td>{percent(row.twenty_day_change_pct)}</td><td>{percent(row.five_day_change_pct)}</td><td>{stages[row.stage]||'继续观察'}<small className="reading-row-status">{row.note?'已核公司事项':'公司事项待核'}</small></td></tr>)}</tbody></table></div>{group.rows.length>8&&<button className="reading-more" onClick={()=>setExpanded(!expanded)}>{expanded?'收起名单':`展开全部${group.rows.length}只`}</button>}
      {selected&&<article className="reading-swing-detail" aria-label={`${selected.name}反弹观察`}><header><h3>{selected.name}</h3><span>{selected.close.toFixed(2)}元 · {selected.as_of}</span></header><h4>{selected.note?.judgment||stages[selected.stage]}</h4>{selected.note?<><ul>{selected.note.reasons.map(text=><li key={text}>{text}</li>)}</ul><p className="reading-next">接下来盯：{selected.note.watch_next.join('；')}。</p><details className="reading-disclosure"><summary>这条判断的依据</summary>{selected.note.sources.map(source=><p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a></p>)}</details></>:<p>这里先记录价格形态，公司最新事项还需要进一步核查。</p>}
      <details className="reading-disclosure"><summary>走势与观察价位</summary><ReadingChart label={`${selected.name}反弹观察走势`} series={[{key:selected.symbol,name:selected.name,change_pct:selected.path.at(-1)?.level==null?null:selected.path.at(-1)!.level!-100,points:selected.path.map(point=>({date:point.date,value:point.close,level:point.level}))}]}/><p>最近5日均价 {selected.five_day_mean_close?.toFixed(2)||'待更新'}元；近20日最低收盘 {selected.twenty_day_low_close.toFixed(2)}元。用来观察回踩是否守住、是否又创新低。</p></details></article>}
    </>}
    <details className="reading-disclosure reading-secondary"><summary>这轮怎么筛 · 覆盖与日期</summary><p>{data.reading_note}</p><p>近20个交易日跌幅至少{Math.abs(data.rules.twenty_day_change_lte_pct)}%，且距观察期高点回落至少{Math.abs(data.rules.from_window_high_lte_pct)}%，进入超跌观察。近5日转涨、回到5日均价上方，才计作初步修复；近5日涨幅超过{data.rules.five_day_change_lte_pct}%或距近20日低点已反弹超过{data.rules.from_twenty_day_low_lte_pct}%，单列为反弹较多。</p><p>初步修复还要求最新成交额至少{(data.rules.latest_amount_gte_yuan/1e4).toFixed(0)}万元、收盘至少{data.rules.latest_close_gte_yuan}元。以上是本轮研究条件，可以随复盘修正，不是已经测出胜率的买入模型。</p>{group.excluded.length>0&&<p>本轮单列：{group.excluded.map(row=>row.name).join('、')}。</p>}</details>
  </section>
}
