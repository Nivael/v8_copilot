import audit from './bailiPaymentTerms.json'
import type {STRegimeData} from './stRegimeTypes'
export function bailiPaymentTermsBound(data:STRegimeData){
 const theme=(data.themes as unknown as Record<string,{sources?:Record<string,unknown>[]}>)?.[audit.source_theme]
 return audit.sources.every(expected=>{
  const source=theme?.sources?.find(s=>s.announcement_id===expected.announcement_id)
  return source&&Object.entries(expected).every(([k,v])=>source[k]===v)
 })
}
export function STBailiPaymentTerms({data}:{data:STRegimeData}){
 if(!bailiPaymentTermsBound(data))return <p role="status">百利付款条款补核尚未与当前来源对应，暂不显示旧解释。</p>
 const source=(id:string)=>audit.sources.find(s=>s.announcement_id===id)!
 return <details aria-label="百利三类款项付款与返还条件"><summary>百利：赠与、保证金、投资款的付款条件一样吗？</summary>
  <p><strong>不一样。同一投资人可以承担不同付款义务，不能共用一套到账或退款条件。</strong>“法院批准后30个工作日”是受让转增股份的投资款安排，不能拿来推定1.3亿元赠与的付款期限。</p>
  <div className="table-scroll"><table><caption>同一七名投资人的三类款项，分别看条款</caption><thead><tr><th scope="col">款项</th><th scope="col">付款条件与时点</th><th scope="col">怎样理解履行</th><th scope="col">返还安排</th></tr></thead><tbody>{audit.rows.map(r=><tr key={r.kind}><th scope="row">{r.kind}</th><td>{r.trigger}</td><td>{r.clock}</td><td>{r.return}</td></tr>)}</tbody></table></div>
  <p>赠与协议另披露：织箜咨询签约时已持有4.99%股权。因此不能假设所有赠与人都必须等重整转增股交割后才可能具备股东身份；也不能反过来认定3900万元就是织箜支付的。投资协议则要求资本公积创设满足条件、能够产生新增股份后，才可按约认购并过户。</p>
  <p>已有款项转用途也不是再收到一次现金：公告举例，织箜已支付报名保证金1550万元，其中6,406,277.72元转作履约保证金，超出部分另行协商。这既不是赠与实收凭证，也不能当成新增640.63万元到账。</p>
  <p>投资协议对资本公积创设支出同样列明，不能因退市、未进入正式重整、计划未获批准、重整不成功或协议解除要求返还。它与符合约定情形可退的投资款、保证金分开；特定违约下后两者也可能被没收。条款差异不代表目前已退款或已没收。</p>
  <p><strong>3900万元的对应缺口仍在：</strong>3900万÷1.3亿虽等于30%，已披露赠与付款条款未列“首期30%”安排，不能仅靠整除就认证某期已付清。还需逐赠与人、逐期付款和后续补充约定。</p>
  <details><summary>条款页码、时间起点与仍未认证事项</summary>
   <p>{audit.scope_note}</p>
   <p>这是两份公司公告转述的协议条款，不是另行取得各方签章原合同。赠与协议写双方签章后成立生效；投资协议写各方签署日期不一致时取较晚日。未逐方核生效日，也未核法院批准、协议解除或实际退款发生，不能拿8月26日披露日直接加5、20或30个工作日。</p>
   <p>对应投资协议还列“2028年11月30日前未获法院裁定受理重整”为约定解除情形之一。该日期按原件保留，不能改成2026年，也不是承诺法院会在该日受理；解除后的退还安排仍受条款前提约束。</p>
   {Object.entries(audit.reviewed_pages).map(([id,pages])=><article key={id}><h6>{source(id).title} · {source(id).published_on}</h6>{pages.map(n=><p key={n}><a href={`${source(id).url}#page=${n}`} target="_blank" rel="noreferrer">{id} · PDF物理第{n}页 ↗</a></p>)}<p>保存SHA256：<code>{source(id).sha256}</code></p></article>)}
   <p>两份旧公告共68页，重提保存全文文本并核8个关键图像页，不称68页全阅；0下载。这里只补强对付款机制的理解，不增加独立案例或收益预测验证次数。</p>
  </details>
 </details>
}
