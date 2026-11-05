import {useState} from 'react'
import type {BroadETFReading} from './readingTypes'
import {percent} from './readingFormat'

export function BroadETFSection({data}:{data:BroadETFReading}){
  const [selected,setSelected]=useState('科创50')
  const group=data.groups.find(item=>item.name===selected)||data.groups[0]
  return <div className="reading-broad" aria-label="六组宽基资金观察">
    <p className="reading-caption">截至 {data.as_of} · {data.sample_funds}只固定样本 · 份额与指数价格一起看</p>
    <div className="reading-scroll"><table><thead><tr><th>宽基</th><th>近5日份额</th><th>指数近5日</th><th>指数近20日</th></tr></thead><tbody>{data.groups.map(item=><tr key={item.name}><th><button aria-label={`宽基组 ${item.name}`} aria-pressed={group.name===item.name} onClick={()=>setSelected(item.name)}>{item.name}</button></th><td>{item.increasing_5d===item.sample_count?`${item.sample_count}/${item.sample_count}只增加`:item.decreasing_5d===item.sample_count?`${item.sample_count}/${item.sample_count}只减少`:`${item.increasing_5d}增 ${item.decreasing_5d}减`}</td><td>{percent(item.five_day_price_change_pct)}</td><td>{percent(item.twenty_day_price_change_pct)}</td></tr>)}</tbody></table></div>
    <p className="reading-next"><strong>{group.name}：</strong>{group.reading}。</p>
    <details className="reading-disclosure" key={group.name}><summary>查看{group.name}的{group.sample_count}只ETF与依据</summary><div className="reading-funds">{group.funds.map(fund=><div key={fund.code}><span><strong>{fund.name}</strong><small>{fund.code}</small></span><span>近5日份额 {percent(fund.five_day_share_change_pct)}<small>近20日 {percent(fund.twenty_day_share_change_pct)} · {data.start}起 {percent(fund.period_share_change_pct)}</small></span></div>)}</div><a href={group.source_url} target="_blank" rel="noreferrer">{group.name}指数原始来源 ↗</a><a href={data.source_url} target="_blank" rel="noreferrer">上交所ETF份额 ↗</a></details>
    {data.capital_actions&&<section className="reading-capital-actions" aria-label="险资与国家队公开动态"><h3>{data.capital_actions.headline}</h3><p>{data.capital_actions.summary}</p>{data.capital_actions.actions.map(action=><article key={action.name}><div><strong>{action.name}</strong><span>{action.date}</span></div><h4>{action.judgment}</h4><details className="reading-disclosure"><summary>具体动作与来源</summary><p>{action.detail}</p><p className="reading-caption">{action.scope}</p>{action.sources.map(source=><p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a></p>)}</details></article>)}</section>}
    <details className="reading-disclosure"><summary>国家队、险资，能从这里看出什么？</summary><p>{data.institution_reading}</p><p>先观察汇金等机构曾配置的宽基样本是否同向变化，再与公开持仓、增减持公告对照。份额总量包含其他投资者，不能把一只基金的总变化直接标成某家机构买入或卖出。</p></details>
  </div>
}
