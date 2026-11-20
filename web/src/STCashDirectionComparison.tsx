import audit from './cashDirectionComparison.json'
import terms from './lingnanJudgmentTerms.json'
import type {STRegimeData} from './stRegimeTypes'

export function cashComparisonBound(data:STRegimeData){
 if(data.through!==audit.through)return false
 return audit.rows.every(row=>{
  if(row.theme==='lingnan')return row.source.announcement_id===terms.source.announcement_id&&row.source.url===terms.source.url&&row.source.sha256===terms.source.sha256&&row.source.published_on===terms.source.announcement_date&&Object.entries(row.expected).every(([k,v])=>(terms.award as Record<string,unknown>)[k]===v)
  const theme=(data.themes as unknown as Record<string,Record<string,unknown>>|undefined)?.[row.theme]
  const fact=theme?.[row.field] as Record<string,unknown>|undefined
  const source=fact?.source as Record<string,unknown>|undefined
  return Boolean(fact&&source&&Object.entries(row.expected).every(([k,v])=>fact[k]===v)&&Object.entries(row.source).every(([k,v])=>source[k]===v))
 })
}
export function STCashDirectionComparison({data}:{data:STRegimeData}){
 if(!cashComparisonBound(data))return <p role="status">现金流向比较尚未与当前证据对应，暂不显示结论。</p>
 return <section id="st-cash-direction-comparison" className="regime-topic-body" aria-label="现金流向与兑现阶段比较">
  <p className="reading-kicker">三家公司 · 四件事项 · 各自披露时点</p>
  <h3>同样说“有进展”，钱究竟流向谁、到了哪一步？</h3>
  <p><strong>先分清谁得到什么，再判断进展改变了哪一项风险。</strong>京蓝一笔补偿已到账，另一笔还在追偿；神雾完成的是股东股份抵债；岭南一审判项指向对债券持有人的支付义务。这些进展不能放在同一个“公司拿到钱”的刻度上。</p>
  <div className="table-scroll"><table><caption>逐项比较：流向、阶段与证据时点</caption><thead><tr><th scope="col">事项</th><th scope="col">谁向谁交付</th><th scope="col">已确认阶段</th><th scope="col">依据披露日</th></tr></thead><tbody>{audit.rows.map(row=><tr key={row.name}><th scope="row">{row.name}</th><td>{row.direction}</td><td>{row.stage}</td><td>{row.date}</td></tr>)}</tbody></table></div>
  <h4>怎样据此更新判断？</h4>
  {audit.rows.map(row=><article key={row.name}><h5>{row.name}</h5><p>{row.meaning}</p><details><summary>下一步要看什么，以及原件依据</summary><p>{row.next}</p><a href={`${row.source.url}#page=${row.page}`} target="_blank" rel="noreferrer">{row.source.title} · {row.date} · 物理第{row.page}页 ↗</a><p>保存文件SHA256：<code>{row.source.sha256}</code></p></details></article>)}
  <h4>可以保留的一条阅读经验</h4>
  <p>看到“完成”“和解”“判决”时，先写清交付方、接收方、交付的是现金还是股份，以及仍需满足的条件。某一笔已履行，只更新这一笔的判断；同家公司其他案件和经营现金仍要分别检查。</p>
  <p>如果随后出现对应案件的实际收付款或交付凭证，就应把该事项从程序进展更新为实际履行；不能靠另一笔到账、相同标题或汇总利润替代。实际履行也不自动证明经营修复或股价会上涨。</p>
  <details><summary>比较范围与仍未解决的问题</summary><p>复用已有原件与已保存研究，比较三家公司四件事项；京蓝两件不算两家独立案例。这是公告阅读方法的案例对照，尚未检验它能否预测收益，也不构成独立市场时段验证。</p><p>研究资料截止{audit.through}，各事实只确认到表列公告时点；未核到的后续状态仍保留。岭南依据是公司转述一审判项，另有11月3日受托报告说明当时未生效，并非法院判决原件。金额不跨公司相加，未核实实付不写成零。</p><p>来源绑定版本：{audit.version}；原研究快照：<code>{audit.snapshot_digest}</code>。本轮不更新旧行情或方法验证次数。</p></details>
 </section>
}
