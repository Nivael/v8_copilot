import {percent} from './readingFormat'
import type {HistoryEvent,HistoryEventTimeline as Timeline} from './researchHistoryTypes'

const lensNames:Record<string,string>={'RL-C-001':'财务与现金流','RL-C-002':'股东行为','RL-C-003':'控制权','RL-C-004':'重组与资产交易'}
const scopeNames={issuer:'公司事项',shareholder:'股东事项',subsidiary:'子公司事项'}
const windowNames=[['1','1日'],['5','5日'],['20','20日']] as const
function change(value:string|null|undefined){return value==null?'暂无可比价格':percent(Number(value))}

export function HistoryEventTimeline({timeline,event,onSelect,stName}:{timeline:Timeline;event:HistoryEvent;onSelect:(id:string)=>void;stName:string}){
  const after=timeline.events.filter(e=>e.relation!=='before_question'),before=timeline.events.filter(e=>e.relation==='before_question')
  const groups:[string,HistoryEvent[]][]=[['原问后的变化',after],['提问前已公开的背景',before]]
  const five=event.context.windows['5']
  return <section className="history-events" aria-label="公告与后续变化">
    <header><h4>{after.length?'这之后发生了什么':'提问时已经知道什么'}</h4><span>{after.length?`已核${after.length}条后续或同日记录`:`已核${before.length}条提问前背景`}</span></header>
    <label>查看公告<select aria-label="查看历史公告" value={event.id} onChange={e=>onSelect(e.target.value)}>
      {groups.map(([label,items])=>items.length>0&&<optgroup key={label} label={label}>{items.map(e=><option key={e.id} value={e.id}>{e.published_on} · {e.title}</option>)}</optgroup>)}
    </select></label>
    <article aria-label="选中公告的判断变化" aria-live="polite">
      <p className="history-event-date"><time>{event.published_on}</time>披露 · {scopeNames[event.entity_scope]}{event.occurred_on&&event.occurred_on!==event.published_on&&<> · 实际发生于{event.occurred_on}{event.occurred_date_qualifier==='local_time'?'（当地时间）':''}</>}{event.scheduled_for&&<> · {event.scheduled_role==='warning_effective_date'?'公告安排于':'拟安排于'}{event.scheduled_for}{event.scheduled_role==='warning_effective_date'?'实施':''}</>}{event.report_period_end&&<> · 报告期截至{event.report_period_end}</>}</p>
      {event.relation==='before_question'&&<p className="reading-caption">这条属于提问前的背景，不能当作问后新增信息。</p>}
      {event.relation==='same_day'&&<p className="reading-caption">与原问同日，首发分钟未核，暂不判定提问时是否已经公开。</p>}
      <h5>{event.title}</h5><p>{event.change}</p>
      <p className="history-event-impact"><strong>怎样更新判断：</strong>{event.interpretation}</p>
      <a href={event.source.url} target="_blank" rel="noreferrer">查看原公告 · 第{event.source.page}页 ↗</a>
      <div className="history-event-context">
        <p>披露日之后5个完整交易日</p>
        <div>{(['stock','market','st'] as const).map(key=><span key={key}>{key==='stock'?'个股':key==='market'?'大盘':stName}<strong>{change(five?.change_pct[key])}</strong></span>)}</div>
        <small>{event.context.reference_close?`从${event.context.reference_close}收盘起`:'披露日前收盘未覆盖'}{five?.through?` · 至${five.through}`:' · 当前行情档案未覆盖完整窗口'}，与原问题起算的图表分别比较。</small>
      </div>
      {event.price_note&&<p className="reading-caption">{event.price_note}</p>}
      <details className="reading-disclosure"><summary>用哪些 lens 看 · 下一步观察</summary>
        <p>{event.lens_ids.map(id=>lensNames[id]||id).join(' · ')}</p><p>{event.watch}</p>
        {timeline.version==='history_event_timeline_v1'?<a href={`#method-${timeline.experience_id}`}>查看这条复盘方法 ↓</a>:<><p><strong>这次学到什么：</strong>{timeline.learning.lesson}</p><p><strong>怎样继续检验：</strong>{timeline.learning.next_check}</p></>}
      </details>
      <details className="reading-disclosure"><summary>其他窗口与比较口径</summary>
        <div className="reading-scroll"><table><thead><tr><th>窗口</th><th>截至</th><th>个股</th><th>大盘</th><th>{stName}</th></tr></thead><tbody>{windowNames.map(([key,label])=>{const w=event.context.windows[key];return <tr key={key}><th scope="row">{label}</th><td>{w?.through||'待完整窗口行情'}</td>{(['stock','market','st'] as const).map(k=><td key={k}>{change(w?.change_pct[k])}</td>)}</tr>})}</tbody></table></div>
        <p>按公开日期之后的完整交易日比较；交易日以当天收盘为参照，休市日以前一市场收盘为参照。它不包含最早反应，也不代表已经识别某一事件的因果贡献。缺价格保留空缺。</p>
        {event.evidence_detail&&<details className="reading-disclosure"><summary>核对字段与原件说明</summary><p>{event.evidence_detail}</p></details>}
      </details>
    </article>
  </section>
}
