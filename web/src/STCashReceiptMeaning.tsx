import {STBailiReceiptUpdate} from './STBailiReceiptUpdate'
import receiptUpdate from './bailiReceiptUpdate.json'
import {STBailiPaymentTerms} from './STBailiPaymentTerms'
import audit from './cashReceiptMeaning.json'
import type {STRegimeData} from './stRegimeTypes'
export function cashReceiptMeaningBound(data:STRegimeData){
 const themes=data.themes as unknown as Record<string,Record<string,unknown>>|undefined
 if(data.through!==audit.through||JSON.stringify(themes?.removal_followup?.compensation)!==JSON.stringify(audit.jinglan_compensation))return false
 return audit.bindings.every(b=>{
  const theme=themes?.[b.theme]
  const chains=(theme?.chains??[]) as Record<string,unknown>[]
  const sources=(theme?.sources??[]) as Record<string,unknown>[]
  const chain=chains.find(c=>c.chain===b.chain.chain)
  const source=sources.find(s=>s.announcement_id===b.source.announcement_id)
  return chain&&source&&Object.entries(b.chain).every(([k,v])=>JSON.stringify(chain[k])===JSON.stringify(v))&&Object.entries(b.source).every(([k,v])=>source[k]===v)
 })
}
export function STCashReceiptMeaning({data}:{data:STRegimeData}){
 if(!cashReceiptMeaningBound(data))return <p role="status">到账性质比较尚未与当前证据对应，暂不显示旧解释。</p>
 return <section aria-label="到账以后怎样判断经营修复">
  <h4>钱到了，就能说经营好转了吗？</h4>
  <p><strong>到账先解决这一笔是否履行的问题；经营判断还要看钱从哪里来、能否持续。</strong>京蓝收的是业绩补偿，海泰全资子公司收的是开发项目销售款，百利获得的是投资人资本支持。把这三种实收都叫“回款”，容易漏掉关键差别。</p>
  <STBailiReceiptUpdate/>
  <div className="table-scroll"><table><caption>三种实收：补偿、项目销售与资本支持</caption><thead><tr><th scope="col">案例与流向</th><th scope="col">确认到哪一步</th><th scope="col">怎样理解这笔钱</th></tr></thead><tbody>{audit.rows.map(old=>{const r=old.name==='百利：投资人赠与'?receiptUpdate.display_row:old;return <tr key={r.name}><th scope="row">{r.name}<br/>{r.delivery}</th><td>{r.receipt}<br/>依据披露：{r.date}</td><td>{r.cash_kind}</td></tr>})}</tbody></table></div>
  <h5>海泰：不能把“卖房”一律当成非经营现金</h5>
  <p>10月1日公告确认，海泰方圆已收到55,006.89万元全部交易款，并完成实际交付，房产登记随后办理。卖的是其开发项目全部可售房产和地下车位使用权，三季报也将房产销售收入、毛利增长列为利润变化原因。</p>
  <p>三季报列前三季经营现金净流入558,045,315.92元，但它是整个合并范围、整个期间的净额，不能直接等同于单笔550,068,900元售价。售价也不是净利润。集中卖出一个项目能带来真实收入和现金，能否持续仍需后续销售、成本和经营证据。</p>
  <h5>百利：筹资支持不等于经营收入，也不等于赠与全额到款</h5>
  <p>8月协议总额1.3亿元，协议写明经济实质为资本投入、拟计入资本公积，最终会计处理以审计认定为准；付款安排另要求赠与人在各期付款前具备股东身份，不能只截取“不附条件”几个字忽略安排。</p>
  <p>11月3日专门公告进一步确认，截至10月30日两笔赠与累计7500万元，首期付款义务已按期履行。资本支持的履行判断应据此更新；仍不能把它当主营回款或经营利润，前三季经营现金净流出26,215,410.77元的报表事实也不被改写。</p>
  <STBailiPaymentTerms data={data}/>
  <details><summary>回看旧稿3900万元与9100万元差额：为什么不能继续沿用？</summary><p>旧稿依据10月28日三季报的吸收投资现金3900万元及捐赠解释，只说明部分落实，并把协议额与该项目的差额列为9100万元。这是漏选11月3日后续收款公告之前的阅读，现不再作为最新累计或最新余款。更新为公司确认的协议两笔累计7500万元、剩余算术差额5500万元；季度项目仍保留，不与累计相加。逐赠与人及每笔金额的对应仍缺，剩余差额仍不当逾期应收。</p></details>
  <h5>京蓝：已收齐的是2025年度补偿，不是下一年度经营承诺</h5>
  <p>{audit.rows[0].interpretation}本轮没有为它补造现金流量表项目分类；2026年度须按协议约定范围核验全年扣非归母利润。</p>
  <details><summary>原件页码、报表勾稽与核实范围</summary>
   <p>海泰现金流勾稽：经营流入618,751,277.93元−经营流出60,705,962.01元＝经营净流入558,045,315.92元。这里只核该表算术，未完成单笔房产售价与每一项现金流的全部对应，也未从披露日倒推精确收款日。</p>
   {audit.bindings.map(b=><article key={b.source.announcement_id}><h6>{b.source.title} · {b.source.published_on}</h6>{b.pages.map(n=><p key={n}><a href={`${b.source.url}#page=${n}`} target="_blank" rel="noreferrer">{b.source.announcement_id} · PDF物理第{n}页 ↗</a></p>)}<p>保存SHA256：<code>{b.source.sha256}</code></p></article>)}
   <p><a href={`${audit.jinglan_compensation.source.url}#page=1`} target="_blank" rel="noreferrer">京蓝2025年度补偿支付完毕公告 · 2026-08-21 · 第1页 ↗</a></p>
   <p>前轮实收性质比较复用4份已存原件，核对6个图像页；其后付款条款补核另列，本次新增11月3日收款公告4页并全部看图。共享原件不重复算独立案例，京蓝沿用前轮已核来源。三家是不同收款性质的案例，不是三个独立市场时段实验；没有新增收益预测或方法采用次数。基准资料截止{audit.through}，各公告只确认其披露时点，后续状态另核。</p>
  </details>
 </section>
}
