import packet from './stLimitCohorts.json'
import alignment from './stBreadthAlignment.json'
import partial from './szseNov20Limits.json'
import complete from './nov20SzseLimitComplete.json'
import market from './tencentMarketDailyLimits.json'
export function DailySTExitPressure({day}:{day:string}){
 if(packet.alignment_evidence_sha256!==alignment.evidence_sha256)return <p role="status">ST限价与既有来源未对应，暂不展示退出压力。</p>
 if(day===complete.date&&(complete.market_audit_sha256!==market.evidence_sha256||complete.prior_partial_sha256!==partial.evidence_sha256||complete.matched.length+complete.official_no_trade.length!==complete.members))return <p role="status">20日ST样本与市场限价来源未对应，暂不合并展示。</p>
 const groups=packet.reading.groups.map(g=>({key:g.key,row:g.days.find(d=>d.date===day)}))
 const available=groups.every(g=>g.row)
 return <aside aria-label="同日ST样本退出压力"><h4>同一天，ST样本出现了多少退出压力？</h4>
  <p>范围是注明的ST样本，不能当作沪深全市场跌停统计。逐股限价来自保存供应商，不用统一跌幅倒推。</p>
  {available?<><p className="reading-table-scroll-hint">这张表可左右滑动，查看全部样本和缺口。</p><div className="learning-table-wrap"><table className="market-pressure-table"><caption>{day} · 不同样本分别读，不相加</caption><thead><tr><th>样本范围</th><th>成交已配对／成员</th><th>收盘在下限</th><th>日内触下限</th><th>全天同价在下限</th><th>未配对情况</th></tr></thead><tbody>{groups.map(g=>{const r=g.row!;return <tr key={g.key}><th>{g.key==='daily_members'?'供应商当日ST主板名单':'固定历史150只'}</th><td>{r.paired}／{r.members}</td><td>{r.close_at_down}只</td><td>{r.touch_down}只</td><td>{r.one_price_down}只</td><td>无日线{r.missing_daily}；零量{r.nontrading_daily}；成交未核配{r.unresolved_trading}</td></tr>})}</tbody></table></div><p>日内触下限包含收盘仍在下限的股票，各列不能相加。全天同价在下限提示需要关注成交约束，但日线不能证明某笔委托可以或无法成交；仍缺盘口排队、委托时点与实际成本。</p></>:day===complete.date?<><p>深市官方明确注明20日的主板风险警示样本共{complete.members}只，其中{complete.matched.length}只有成交股票已全部核对实际限价，另{complete.official_no_trade.length}只官方无成交。这里只覆盖这一注明日期的样本；此前两组同范围的完整20日统计仍待核。</p><p>在这{complete.matched.length}只有成交样本中，日内触下限{complete.hits.touch_lower.length}只、收盘在下限{complete.hits.close_lower.length}只、全天同价在下限{complete.hits.one_price_lower.length}只。收盘无人封下限不代表容易退出，也不代表完整沪深ST没有跌停。</p><details><summary>这次补齐了什么？查看旧阶段与交叉核对</summary><p>腾讯报价补齐此前缺失的*ST美丽（000010），它当日未触下限；原已核对{complete.cross_channel_agreement.length}只的开高低收、参考价和上下限在两个报价渠道间逐项一致。两渠道一致不证明底层数据源独立。所有成交样本的开高低收及参考价另与官方逐项核同。</p><p>旧阶段保留：74只中71只成交报价已配对、2只无成交、1只有成交但报价缺失；旧71只中触下限{partial.reading.hits.touch_lower.length}只、收盘下限{partial.reading.hits.close_lower.length}只。补齐改变了覆盖完整性，未改变触限计数。</p><a href={'/runs#research-'+partial.research_run_id}>查看此前71只阶段与原缺口 →</a><p>新增核验摘要：<code style={{overflowWrap:'anywhere'}}>{complete.evidence_sha256}</code></p></details></>:<p>{day}尚无本回放已绑定的逐股实际限价配对统计。状态未知，不等于没有跌停；上方跌幅至少5%的数量不能替代。</p>}
  <details><summary>退出压力的样本与证据边界</summary><p>每日组按保存供应商ST名单筛主板，尚未认证完整官方法定名单；固定组保留后来离开ST的公司。无日线不能单凭缺失判定停牌、退市或无风险。两组高度重叠，不能相加为独立案例。</p><p>原九日证据摘要：<code style={{overflowWrap:'anywhere'}}>{packet.evidence_sha256}</code>；20日另有深市74只明确日期样本的72只成交全配对，范围与来源口径不同，不连接成同口径趋势。</p><a href={'/runs#research-'+packet.research_run_id}>查看逐股限价与原件核对 →</a></details>
 </aside>
}
