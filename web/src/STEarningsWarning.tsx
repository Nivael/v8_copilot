import {useState} from 'react'
import type {RegimeEarningsWarning,LabelSource} from './stRegimeTypes'
const pct=(n:number|null)=>n==null?'无实际成交端点':(n>0?'+':'')+n.toFixed(2)+'%'
const wan=(n:string)=>(Number(n)/10000).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
function Source({source:s}:{source:LabelSource}){return <a href={s.url.split('#')[0]+'#page='+s.page} target="_blank" rel="noreferrer">{s.title} · 第{s.page}页 ↗</a>}
const combination=(s:string)=>{const [profit,cash]=s.split('_cash_');const labels:Record<string,string>={profit_positive:'盈利',profit_negative:'亏损',profit_zero:'利润为零',cash_positive:'现金净流入',cash_negative:'现金净流出',cash_zero:'现金净额为零'};return (labels[profit]??'利润方向待核')+' · '+(labels['cash_'+cash]??'现金方向待核')}
export function STEarningsWarning({data:d}:{data:RegimeEarningsWarning|null|undefined}){
 const [period,setPeriod]=useState('full')
 if(!d)return null
 const [h,q]=d.reports,w=d.warning,market=d.comparison[0].windows[period]
 return <section id="st-earnings-warning" style={{scrollMarginTop:80}} className="regime-removal-cohort" aria-label="盈利现金与警示条件对照">
 <h4>盈利和现金都转好，为什么还在ST？</h4><p>{d.answer}</p>
 <h5>同一报告期，五家公司的利润与现金有什么不同？</h5><p>下表均为2026年前三季归母利润与经营现金净额，单位万元，均未经审计；只在11月6日复盘时并列，不将后来报数倒填7月。股价使用每行相同日期，与当时财报公开日分别记录。</p>
 <label>共同价格窗口 <select aria-label="盈利现金案例价格窗口" value={period} onChange={e=>setPeriod(e.target.value)}><option value="full">7月3日至11月6日</option><option value="20">截至11月6日前20个市场日</option><option value="5">截至11月6日前5个市场日</option></select></label>
 <div className="regime-scroll"><table className="regime-table"><thead><tr><th>公司与财务组合</th><th>归母净利润</th><th>经营现金净额</th><th>同窗股价</th></tr></thead><tbody>{d.comparison.map(r=><tr key={r.symbol}><th scope="row">{r.name}<small>{combination(r.combination)}</small></th><td>{wan(r.financial.parent_profit)}</td><td>{wan(r.financial.operating_cash)}</td><td>{pct(r.windows[period].stock_pct)}</td></tr>)}</tbody></table></div>
 <p>价格共同区间{market.anchor} → {market.through}，{market.market_days}个市场交易日；同窗大盘{pct(market.market_pct)}、ST参考{pct(market.st_pct)}。天际7月15日才入ST，完整窗含此前非ST阶段；不加入原固定150或12只摘帽组。</p>
 {d.comparison.every(r=>(r.windows.full.stock_pct??0)<0&&(r.windows['5'].stock_pct??0)>0)&&<p>五家近5日都上涨，但完整区间都下跌，财务组合却各不相同。短线修复不能抹去较长回撤，也不能用股价一个方向替代所有公司的经营与监管判断。</p>}
 <details><summary>沿时间线看：预告、正式处罚、中报、三季报</summary>
 <ol><li>7月14日：已预告半年归母、扣非各盈利2.2亿至2.6亿元，未经预审计；同日提示7月15日起实施其他风险警示。预告没有给经营现金流，不能说当时完全没有盈利信息，也不能填入后来的现金实际数。 <Source source={d.forecast.source}/></li><li>8月8日：披露前一天收到正式处罚，认定历史年报虚假记载，调查办理终结。正式处罚阶段已核，精确作出日仍空。 <Source source={w.decision_source}/></li><li>8月21日：半年归母{wan(h.parent_profit)}万元、扣非{wan(h.deducted_profit)}万元，落在预告范围内；经营现金仍为{wan(h.operating_cash)}万元。</li><li>10月27日：前三季归母{wan(q.parent_profit)}万元、扣非{wan(q.deducted_profit)}万元，经营现金变为{wan(q.operating_cash)}万元。第三季单季现金（累计相减）{wan(d.single_quarter.operating_cash)}万元；改善得到支持，但不自动替代撤销警示条件。</li></ol>
 <div className="regime-scroll"><table className="regime-table"><caption>原数与物理页：单位万元；净资产为期末存量</caption><thead><tr><th>指标</th><th>半年</th><th>前三季</th></tr></thead><tbody>{([['revenue','收入'],['parent_profit','归母利润'],['deducted_profit','扣非利润'],['operating_cash','经营现金'],['parent_equity','归母净资产']] as const).map(([key,label])=><tr key={key}><th scope="row">{label}</th><td>{wan(h[key])} <Source source={h.metric_sources[key]}/></td><td>{wan(q[key])} <Source source={q.metric_sources[key]}/></td></tr>)}</tbody></table></div><p>半年本轮仅核摘要，不从非标提示“不适用”推断审计状态；三季报明确未经审计。预告、正式报表、累计相减和审计状态分开。</p>
 </details>
 <details><summary>为什么“调查办理终结”也不等于可以立刻撤销？</summary><p>天际这类虚假记载事项的普通撤销申请，要核相应重述、处罚决定作出起满12个月及申请程序。公司{w.decision_received_on}收到正式处罚、{w.decision_published_on}公开；精确作出日本轮未独立核实，不显示自动摘帽倒计时。</p><p>普通路径适用于历史财报虚假记载这一项：相应年度报表追溯重述、从处罚决定书作出之日起满12个月，然后申请、交易所决定及实施。发行人称此前已做差错更正；本轮未逐项重审历史全套报表。 <Source source={w.restatement_source}/> <Source source={w.conditions_source}/></p><p>规则另有一条路径：后续处罚决定或结案通知显示未触及该虚假记载项时，可以按规定披露停复牌后撤销。本案正式决定仍认定虚假记载，不能把“本案办理终结”当成“未触及该项”的结案。例外条件与一般时钟都保留，不把12个月套给所有ST。若已有证券虚假陈述索赔诉讼，规则还要求充分计提预计负债并披露；本轮未认证该项是否适用或准备是否充分。 <Source source={w.conditions_source}/></p><p>收到日、公开日、作出日和ST生效日分别记录；没有独立核实的作出日，不从8月7日、8月8日或7月15日机械加一年。满足条件、提交申请、获同意、生效也不是同一天。 <Source source={w.application_source}/></p></details>
 <details><summary>现金转正之后，还要看什么？</summary><p>归母低于扣非不必然是抄反：前三季非经常性损益{wan(d.nonrecurring_ytd)}万元，与归母减扣非相符，原表包括处置和碳酸锂期货等损失。</p><p>现金及等价物由期初{wan(d.cash.opening)}万元，经经营{wan(d.cash.operating)}、投资{wan(d.cash.investing)}、筹资{wan(d.cash.financing)}、汇率{wan(d.cash.fx)}万元，增加{wan(d.cash.change)}万元至{wan(d.cash.closing)}万元。正经营现金不等于全部现金增加都来自经营，也不同于货币资金余额。 <Source source={d.cash.operating_source}/> <Source source={d.cash.source}/></p>{d.facts.filter(f=>f.source.page===4&&f.source.sha256===q.metric_sources.revenue.sha256).map((f,n)=><p key={n}>{f.text} <Source source={f.source}/></p>)}</details>
 <details><summary>核五家公司各自警示、财报原件与报价范围</summary>
 {d.comparison.map(r=><details key={r.symbol}><summary>{r.name}：条件与来源</summary><p>{r.warning_scope}。财报公开{r.financial.published_on}，同为1月1日至9月30日累计。<Source source={r.financial.metric_sources.parent_profit}/> <Source source={r.financial.metric_sources.operating_cash}/></p><p>所选价格窗含{r.windows[period].market_days}市场日、{r.windows[period].stock_traded_days}个该股成交日；停牌不补成交，端点须实际成交。</p></details>)}
 <p>天际本轮2份腾讯核对响应、{d.quote_check.quote_points}个收盘点，对应{d.quote_check.unique_traded_security_days}个实际成交日，所获原价/前复权与原缓存{d.obtained_quotes_agree?'一致':'存在差异，待核'}。两份响应来自同一腾讯核对渠道，不能称两家独立来源；原提供商缓存另行逐日勾稽，未新增提供商查询。</p>{d.quote_check.rows[0].channels.map(c=><p key={c.key}><a href={c.source.url} target="_blank" rel="noreferrer">{c.key} ↗</a>：{c.matched_points}/{c.points}点相符，差异{c.price_differences.length}日；冻结{c.source.observed_at}，链接可能更新。其他公司复用既有核价及已记录的渠道缺口。</p>)}<p>{d.selection}</p>
 </details>
 <p><strong>保留的条件性经验：</strong>先问触发哪一条警示，再分别核盈利、现金与程序；同样盈利或同样上涨，不代表同样的解除条件。</p><p><strong>什么会改变判断：</strong>{d.what_would_change}</p><details><summary>判断更新与剩余限制</summary><p>{d.what_changed}</p>{d.judgment_history.map(h=><p key={h.snapshot}>此前：{h.text}</p>)}<p>{d.boundary}</p></details>
 </section>
}
