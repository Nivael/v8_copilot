import {useState} from 'react'
import type {RegimeShenwuExecution,LabelSource} from './stRegimeTypes'
const pct=(n:number|null)=>n==null?'窗口未满或缺成交端点':(n>0?'+':'')+n.toFixed(2)+'%'
const wan=(n:string)=>(Number(n)/10000).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
function Source({source:s}:{source:LabelSource}){return <a href={s.url+'#page='+s.page} target="_blank" rel="noreferrer">{s.title} · 第{s.page}页 ↗</a>}
export function STShenwuExecution({data:d}:{data:RegimeShenwuExecution|null|undefined}){
 const [days,setDays]=useState('5')
 if(!d)return null
 const t=d.transfer,c=d.contract,r=d.receivable
 const contractEvent=d.observations.find(e=>e.id==='shenwu_execution_1225631489'),post5=contractEvent?.observation.windows['5']
 return <section id="st-shenwu-execution" style={{scrollMarginTop:80}} className="regime-removal-cohort" aria-label="神雾股份过户与合同履约">
 <h4>过户、签约，距离现金到账还有多远？</h4><p>{d.answer}</p><p><strong>判断更新：</strong>{d.judgment_update}</p>
 <div className="regime-scroll"><table className="regime-table"><caption>先分清钱属于哪个主体，再问哪一步已经完成</caption><thead><tr><th>事项</th><th>已有凭据支持</th><th>还不能据此确认</th></tr></thead><tbody>
 <tr><th scope="row">股东3300万股</th><td>两方列{t.reported_change_on}权益变动；发行人{t.published_on}已确认过户完成</td><td>上市公司收到新增现金、补偿义务已履行</td></tr>
 <tr><th scope="row">喀什储能联合体合同</th><td>{c.published_on}披露正式签约，含税暂定总价7.17亿元</td><td>联合立本独享全部合同额、当年收入、归母利润或实收现金</td></tr>
 <tr><th scope="row">江苏院旧项目结算款</th><td>应结算{wan(r.due_yuan)}万元，截至{r.as_of}报告称未收到</td><td>此后是否到账尚未核实；不填零，也不由新合同抵消旧款</td></tr>
 </tbody></table></div>
 {post5&&<p>签约公告公开日收盘至后5市场日（{contractEvent?.observation.anchor} → {post5.through??'窗口未满'}），个股{pct(post5.stock_pct)}，同窗大盘{pct(post5.market_pct)}、ST{pct(post5.st_pct)}。新合同不等于短线上涨，随后回撤也不能证明合同失败。</p>}
 <details><summary>股东股份：两次流拍怎样推进到过户？</summary>
 <ol>{d.auctions.map(a=><li key={a.round}>{a.start}至{a.end}，同一3300万股第{a.round}次拍卖流拍；{a.published_on}公开。{a.round===2&&'第二次流拍当时仍只提示可能司法划转。'} <Source source={a.source}/></li>)}<li>两方权益变动报告列{t.reported_change_on}变动，长城资管附表列“法院裁定抵债”；发行人{t.published_on}确认截至披露已完成过户。三个文件旁证同一件事，不算三个独立案例。{t.report_date_sources.map((s,n)=><span key={n}> <Source source={s}/></span>)}</li></ol>
 <p>股数勾稽：神雾集团7260万−3300万＝3960万股；长城资管0＋3300万＝3300万股。分别占总股本{d.ratios.old_holder_before_pct}%→{d.ratios.old_holder_after_pct}%、0→{d.ratios.transfer_pct}%。第一大股东与控制权未因此变化。 <Source source={t.source}/></p>
 <p>公告称持有人应按持股比例承接相应业绩补偿义务；“应承接”不是“已补偿”。两方报告未给成交均价，不拿股票市价乘股数充当公司收到的现金。登记机构回执与法院原裁定尚未纳入，10月8日按披露的权益变动日标示，不认证精确登记办理时刻。</p>
 <details><summary>核累计股数分母，以及8月公告的一处年份冲突</summary><p>此前累计已过户276,810,462股，不包含本次3300万股；加当时仍持72,600,000股，等于2016年重组取得349,410,462股。累计比例{d.ratios.historical_pct_of_original}%以这批原取得股份为分母，不是当前持股数量；本次占当时持股{d.ratios.auction_pct_of_then_holdings}%。</p><p>8月公告一处回指写{d.date_conflict.quoted_cross_reference_date}，但7月原件与目录为{d.date_conflict.first_primary_publication}。{d.date_conflict.basis} <Source source={d.date_conflict.source}/></p></details>
 </details>
 <details><summary>7.17亿元合同：已经签了什么，哪些仍待兑现？</summary>
 <p>联合立本与河南同力组成联合体，为喀什储能项目签EPC总承包；它与江苏院、中清石河子的旧项目是不同主体、不同合同。签约是业务承接进展，联合体总价不直接等于联合立本的结算份额，更不等于上市公司归母利润。</p>
 <p>合同{c.signed_on}订立，公告{c.issuer_signed_on}签署、{c.published_on}公开。三种日期分别保留；公告同窗行情从公开日收盘起算，不用合同签订日充当市场已知时点。 <Source source={c.source}/></p>
 <p>含税暂定总价{wan(c.total_yuan)}万元＝设计{wan(c.components_yuan.design)}＋设备建安{wan(c.components_yuan.equipment_and_construction)}＋其他{wan(c.components_yuan.other)}万元。单价0.8964元/Wh与80万kWh容量换算相符；此前孟津项目320万元设计费不混入本项目265万元。</p>
 <p>合同工期{c.calendar_days}日，计划竣工{c.planned_finish_on}；开工以开工令为准，未核实际开工日，不从竣工日倒算。各方签字或盖章生效的条款不当精确生效日回执。公告明确当年能否确认收入及金额仍不确定，需看施工、设备到货、调试验收。实际回款、收入确认与归母利润均未据此认证。</p>
 </details>
 <details><summary>旧项目回款，证据截止在哪里？</summary><p>{r.entity}向{r.counterparty}催收{wan(r.due_yuan)}万元，要求{r.due_on}前支付；截至{r.as_of}三季报称尚未收到。此后状态没有被本轮原件认证。不能把协议生效、已开展结算、追款权利或另一笔新合同当作这笔款已收到。 <Source source={r.source}/></p></details>
 <details><summary>公告之后，个股与大盘/ST怎样走？</summary>
 <label>看公开日收盘之后 <select aria-label="神雾执行公告窗口" value={days} onChange={e=>setDays(e.target.value)}><option value="5">5个市场交易日</option><option value="20">20个市场交易日</option></select></label>
 <div className="regime-scroll"><table className="regime-table"><thead><tr><th>公开节点与观察区间</th><th>个股</th><th>同窗大盘</th><th>同窗ST</th></tr></thead><tbody>{d.observations.map(e=>{const w=e.observation.windows[days];return <tr key={e.id}><th scope="row">{e.title}<small>{e.observation.anchor} → {w.through??'窗口未满'}</small></th><td>{pct(w.stock_pct)}</td><td>{pct(w.market_pct)}</td><td>{pct(w.st_pct)}</td></tr>})}</tbody></table></div>
 <p>沿用原行情与成交端点；未满窗不填零。日期只到日，不认证最早反应。这些阶段属于同一公司的相关链条，不把重叠窗口、重复文件或公告后的涨跌当成多个独立因果验证。</p>
 </details>
 <p><strong>什么证据会改变判断：</strong>{d.what_would_change}</p><p><strong>反证怎样处理：</strong>若后续合同解除或撤销，需下调其后续业务贡献判断，不抹去已签约的历史事实。若登记回执与披露的日期、股数不一致，保留冲突并修正当前认证。实际收款凭证更新报告之后的状态，不倒改“截至报告未收”。</p><details><summary>这次更新保留了哪些边界？</summary><p>{d.boundary}</p>{d.judgment_history.map(h=><p key={h.snapshot}>此前依据{h.basis}：{h.text}</p>)}</details>
 </section>
}
