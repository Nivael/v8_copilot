import packet from './recoveredLimits.json'
import original from './stExitObservation.json'
const names:Record<string,string>={'603398':'沐邦','002514':'宝馨','600363':'联光','002667':'威领','688053':'思科瑞'}
export function STRecoveredLimits(){
 if(packet.ohlc_evidence_sha256!==original.evidence_sha256)return <p role="status">恢复的限价与旧日线来源不对应，暂不合并。</p>
 const r=packet.reading
 return <section aria-label="限价留档恢复与更正"><h4>补核更新：限价原件已有保存，先前缺口说明范围过宽</h4><p>先前只检查主库，得到近期限价为空；另一个历史采集目录保存了{r.start}至{r.through}的供应商限价。已恢复五家{r.limit_records}条证券日限价，与{r.trading_ohlc_pairs}个有成交日配对；思科瑞11月10日无成交，不把它记为零次跌停。</p><p>原日线有5日收在最低价；限价配对后，其中{r.close_at_down_limit_days}日收盘达到供应商下限价，也有{r.touch_down_limit_days}日盘中触及下限价；全天同价且处于下限价的为{r.one_price_at_down_limit_days}日。“收低”和“收盘跌停”不能混用，也不能据此判断你的委托能否成交。</p><details><summary>哪两日达到下限价，来源核到哪一步？</summary><div className="learning-table-wrap"><table className="market-pressure-table"><caption>所选五家中，收盘达到已保存供应商下限价的证券日</caption><thead><tr><th>公司</th><th>日期</th><th>下限价／收盘</th><th>日内最低／最高</th></tr></thead><tbody>{r.rows.filter(x=>x.close_at_down_limit).map(x=><tr key={x.symbol+x.date}><th>{names[x.symbol]}</th><td>{x.date}</td><td>{x.down_limit}／{x.close}</td><td>{x.low}／{x.high}</td></tr>)}</tbody></table></div><p>{r.scope} {r.boundary}</p><p>原始返回逐字节摘要、请求日期/字段与证券身份已核，日线全部处于对应上下限内。恢复原件不改变主库覆盖日期，也没有调用过期接口。</p>{packet.sources.map(s=><p key={s.date}>{s.date} · 取得于{s.fetched_at} · SHA256 <code>{s.response_sha256}</code></p>)}<p><a href={'/runs#research-'+packet.research_run_id}>查看限价恢复与更正研究 →</a></p></details></section>
}
