import recent from './recentMarketBreadth.json'
import alignment from './stBreadthAlignment.json'
import type {BreadthReading} from './readingTypes'
import {percent} from './readingFormat'
type Purpose='today'|'recent'|'st'
export function MarketRiskQuestions({data,onRead}:{data:BreadthReading;onRead:(purpose:Purpose)=>void}){
 const last=recent.rows[recent.rows.length-1]
 const group=data.groups[0]
 const bound=data.as_of===recent.as_of&&group?.observed_trading_stocks===last.trading&&group.advancing===last.advancing&&group.declining_5pct_or_more===last.declining_5pct_or_more&&alignment.breadth_evidence_sha256===recent.evidence_sha256
 if(!bound)return <section className="reading-section" aria-label="风险线索总览"><h2>先分清风险来自哪里</h2><p>连续复盘与当前收盘截面尚未对应，暂不合并成一份总览。可分别查看当天广度和注明日期的历史复盘。</p></section>
 const weakStart=recent.sequence.days[recent.sequence.days.length-last.streak]?.date
 const signal=alignment.reading.signals[alignment.reading.signals.length-1]
 return <section className="reading-section" aria-label="风险线索总览"><header><h2>先分清风险来自哪里</h2><p>大盘参与面截至{data.as_of}；ST共同窗口截至{alignment.reading.common_through}。这是证据总览，尚未校准成危机等级。</p></header><p className="reading-lead">这次既有持续偏弱，也有单日大跌扩散；最近共同窗口中，ST跌得更深。退出能力仍缺直接证据。</p><div className="learning-table-wrap"><table className="market-pressure-table"><caption>四个问题，各看一组证据</caption><thead><tr><th>要判断什么</th><th>已有证据</th><th>接着看什么</th></tr></thead><tbody>
 <tr><th>是一天冲击，还是持续走弱？</th><td>{weakStart}至{last.date}，上涨股票连续{last.streak}个交易日不足一半。</td><td><button type="button" onClick={()=>onRead('recent')}>看转弱过程</button></td></tr>
 <tr><th>当天压力扩散到多广？</th><td>{last.date}，有成交的{last.trading}只股票中，上涨{last.advancing_pct.toFixed(1)}%；跌幅至少5%的占{last.declining_5pct_or_more_pct.toFixed(1)}%。后者不是跌停率。</td><td><button type="button" onClick={()=>onRead('today')}>看当天分布</button></td></tr>
 <tr><th>ST是否比大盘更弱？</th><td>{signal.date}收盘至{signal.through}，ST参考{percent(signal.st_pct)}，大盘{percent(signal.market_pct)}；仅{signal.observed_following_sessions}日，未满5日。</td><td><button type="button" onClick={()=>onRead('st')}>看ST同窗对照</button></td></tr>
 <tr><th>需要退出时能否成交？</th><td>尚不能确认。实际限价、连续跌停、盘口队列与执行成本仍缺；日线有成交不等于能按收盘价退出。</td><td>待补实际限价与盘口资料</td></tr>
 </tbody></table></div><p>接下来检验：参与面改善能否持续、大跌比例是否收敛、ST是否同步修复。单日上涨或一次压力缓和，不直接改判为全面修复；这些条件还不是已经验证的仓位规则。</p></section>
}
