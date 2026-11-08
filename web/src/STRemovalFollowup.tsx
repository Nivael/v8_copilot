import {useState} from 'react'
import type {RegimeRemovalFollowup,RegimeCompanyRiskCases} from './stRegimeTypes'
const wan=(n:string)=>(Number(n)/10000).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
const pct=(n:number|null)=>n==null?'缺成交端点':(n>0?'+':'')+n.toFixed(2)+'%'
export function STRemovalFollowup({data:d,comparison}:{data:RegimeRemovalFollowup|null|undefined;comparison?:RegimeCompanyRiskCases['comparison']}){
 const [period,setPeriod]=useState('20')
 if(!d)return null
 const q=d.reports[1],b=d.price_windows.before20,a=d.price_windows.after20
 return <section aria-label="京蓝摘帽后续复盘">
  <h4>摘帽了，经营和股价也一起改善了吗？</h4><p>{d.answer}</p>
  <p>京蓝摘帽前20个市场日为{pct(b.stock_pct)}，从停牌前最后成交收盘起算的后20个市场日为{pct(a.stock_pct)}；同期大盘分别{pct(b.market_pct)}、{pct(a.market_pct)}。改善事实和随后回撤都保留，不能把摘帽当作上涨保证。</p>
  <details><summary>先看摘帽依据，再核盈利、现金与履约</summary>
   <p>{d.what_changed}</p><p>证券代码000711：法定名称为{d.legal_name}，证券简称先为ST京蓝、后为京蓝科技；这是同一主体，不按两个名称拆成独立案例。</p>
   <p>原警示：{d.warning.cause}。{d.warning.application_published_on}公开申请时仍待核准，{d.warning.removal_published_on}公开获同意及停复牌安排，{d.warning.effective_on}生效；未补造同意日。摘帽后涨跌幅仍{d.warning.limit_after_pct}%，不是旧制度下的5%变10%。</p>
   <p>财报单位万元。半年、前三季分别为1—6月、1—9月累计，净资产为各期末；不能直接把两累计期间作同比。{d.audit_note}</p>
   <div className="regime-scroll"><table className="regime-table"><thead><tr><th>指标</th>{d.reports.map(r=><th key={r.period_end}>{r.period_end}<small>公开{r.published_on}</small></th>)}</tr></thead><tbody>{([['revenue','营业收入'],['parent_profit','归母净利润'],['deducted_profit','扣非归母净利润'],['operating_cash','经营现金流净额'],['parent_equity','归母净资产']] as const).map(([key,label])=><tr key={key}><th>{label}</th>{d.reports.map(r=><td key={r.period_end}>{wan(r[key])}</td>)}</tr>)}</tbody></table></div>
   <p>单看7—9月：收入{wan(d.single_quarter.revenue)}万元、归母利润{wan(d.single_quarter.parent_profit)}万元、扣非利润{wan(d.single_quarter.deducted_profit)}万元；由前三季减半年独立核对。经营现金净额{wan(d.single_quarter.operating_cash)}万元是同期间差额，不冒充原表直接列示单季字段。</p>
   <p>前三季归母利润与扣非之差为非经常性损益{wan(d.nonrecurring.year_to_date_yuan)}万元。现金等价物由期初{wan(d.cash_rollforward.opening_yuan)}万元减至{wan(d.cash_rollforward.closing_yuan)}万元；正利润不等于经营回款或现金余额增加。</p>
   {!!comparison?.length&&<><h5>同期间对照：利润、现金和警示条件各看什么？</h5><p>三家公司均看1—9月累计和9月末归母净资产，三季报均未经审计，公开日不同。高科、华鹏原对照与判断保留；新增京蓝只作第三家公司条件对照，不计算经验胜率。</p><div className="regime-scroll"><table className="regime-table"><thead><tr><th>公司</th><th>归母净利润</th><th>经营现金净额</th><th>归母净资产</th></tr></thead><tbody>{[...comparison.map(x=>({name:x.name,financial:x.financial})),{name:d.name,financial:q}].map(x=><tr key={x.name}><th>{x.name}</th><td>{wan(x.financial.parent_profit)}</td><td>{wan(x.financial.operating_cash)}</td><td>{wan(x.financial.parent_equity)}</td></tr>)}</tbody></table></div></>}
   <h5>三件“钱”的事，不能互相替代</h5>
   <p>① 已收款：{d.compensation.payer}2025年度补偿共{wan(d.compensation.total_received_yuan)}万元已收齐，最后一笔于{d.compensation.last_received_on}收到；本期相关坏账准备冲回{wan(d.nonrecurring.bad_debt_reversal_yuan)}万元，实收款不直接等于当期利润。2026年{wan(d.compensation.commitment_2026_yuan)}万元承诺的口径是{d.compensation.commitment_scope}，不能拿集团前三季扣非值判断全年达标。</p>
   <p>② 另案追偿：公司向{d.recovery.defendants_count}名历史补偿义务人诉请{wan(d.recovery.claim_total_yuan)}万元，其中现金{wan(d.recovery.claim_cash_yuan)}万元及{Number(d.recovery.claim_shares).toLocaleString('zh-CN')}股；不是全额现金，也不是已收到。该案{d.recovery.accepted_month}受理，使用{d.recovery.published_on}公开的更正后原件，不把公开日当受理日；亦不是云南佳骏已收齐的同一协议。</p>
   <p>③ 拍卖待完成：{d.auction.failed_auctions}次流拍后起拍价降至{wan(d.auction.new_start_yuan)}万元；若按该价成交，以{d.auction.estimate_base_on}数据测算处置损失{wan(d.auction.conditional_disposal_loss_yuan)}万元。起拍价不是成交回款，测算损失不是已确认损失；完成前不写成已剥离。</p>
   <details><summary>查看逐项公告与物理页码</summary>{d.facts.map((f,n)=><div key={f.source.sha256+'-'+n}><p>{f.published_on}：{f.text}</p><a href={f.source.url} target="_blank" rel="noreferrer">{f.source.title} · 第{f.source.page}页 ↗</a></div>)}</details>
  </details>
  <details><summary>核摘帽前后同窗、退出后的价格与报价覆盖</summary>
   <p>原固定样本已经保留京蓝摘帽后的44个成交日；本轮对照原缓存并增加报价核验，没有补入新价格。8月28日停牌没有成交报价，非交易日也不当缺价；原样本和旧事件窗口保留。已取腾讯原始/前复权两响应{d.quotes.quote_points}点，对应{d.quotes.unique_traded_security_days}个成交日期；东方财富两种口径有限重试仍断开，跨渠道核验尚缺。</p>
   <div className="regime-scroll"><table className="regime-table"><thead><tr><th>起算口径</th><th>同窗日期</th><th>市场日 / 个股成交日</th><th>个股</th><th>大盘 / ST参考</th></tr></thead><tbody>{([['before20','停牌前20市场日'],['after20','停牌前收盘起后20市场日'],['pre_halt_to_cutoff','停牌前收盘至截止'],['first_resume_close_to_cutoff','复牌首日收盘至截止'],['full','7月3日共同起点']] as const).map(([key,label])=>{const w=d.price_windows[key];return <tr key={key}><th>{label}</th><td>{w.anchor} → {w.through}</td><td>{w.market_days} / {w.stock_traded_days}</td><td>{pct(w.stock_pct)}</td><td>{pct(w.market_pct)} / {pct(w.st_pct)}</td></tr>})}</tbody></table></div>
   <p>后20市场日含8月28日停牌，共{a.stock_traded_days}个个股成交日；未把停牌补零或伪造成交。8月27日收盘和8月31日复牌首日收盘是不同起点，各自市场/ST重算，不能替换。摘帽前已上涨，后来回撤亦可能混合市场、估值及新事项，不分摊公告净贡献。</p>
   <label>新事项公开后看几天 <select aria-label="京蓝后续公告窗口" value={period} onChange={e=>setPeriod(e.target.value)}>{['1','5','20'].map(n=><option key={n} value={n}>{n}个交易日</option>)}</select></label><ul>{d.new_event_windows.map(e=>{const w=e.windows[period];return <li key={e.event_id}><strong>{e.published_on} · {e.title}</strong><p>{w?w.anchor+' → '+w.through+'：个股'+pct(w.stock_pct)+'，大盘'+pct(w.market_pct)+'，ST参考'+pct(w.st_pct)+'。':'后续交易日不足，保留空值。'}</p></li>})}</ul>
   <p>{d.quotes.rows[0].channels.map(c=><span key={c.key}><a href={c.source.url} target="_blank" rel="noreferrer">{c.key.endsWith('qfq')?'腾讯前复权':'腾讯原始价'} ↗</a>：{c.matched_points}/{c.points}点一致；</span>)}报价来源可能更新，实际核对以本轮冻结响应为准。</p>
  </details>
  <p><strong>下次保留什么：</strong>先确认解除的是哪条警示，再分别核利润质量、经营现金与履约状态。正利润、补偿实收、诉讼权利和拟剥离是四件事，同公司多份公告不增加独立验证次数。</p><p><strong>什么证据会改变判断：</strong>{d.what_would_change}</p><p className="reading-caption">{d.boundary}</p>
 </section>
}
