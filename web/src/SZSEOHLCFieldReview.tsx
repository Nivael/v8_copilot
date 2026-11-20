import packet from './szseOHLCFieldReview.json'
import risk from './riskListNov20.json'
export function SZSEOHLCFieldReview({priceAsOf}:{priceAsOf:string}){
 if(priceAsOf!==packet.reading.date)return null
 if(packet.risk_evidence_sha256!==risk.evidence_sha256)return <p role="status">同价观察与20日官方名单来源不对应，待重新核对。</p>
 const r=packet.reading
 return <details className="reading-disclosure"><summary>20日深市，同价K线一定是跌停吗？</summary><p>这次有明确日期依据的深市主板风险警示{r.official_dated_mainboard_members}只中，{r.trading}只有成交，{r.nontrading}只无成交。唯一的全天同价成交是上涨的“发展”，不能把同价K线直接叫作跌停。</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>只看20日深市主板风险警示组，先区分有无成交</caption><thead><tr><th>原表观察</th><th>对应记录</th><th>能说明什么</th></tr></thead><tbody><tr><th>有成交且全天同价</th><td>{r.one_price_trading}只{r.one_price_rows.map(x=><small key={x.symbol}>{x.name} · {x.symbol}：{x.close}元，参考前收{x.reference}元</small>)}</td><td>本次为上涨同价；实际涨停价字段未提供，不据此补“涨停”标签</td></tr><tr><th>无成交但显示相同参考价</th><td>{r.nontrading}只{r.nontrading_rows.map(x=><small key={x.symbol}>{x.name} · {x.symbol}</small>)}</td><td>不计入全天同价成交，也不记作没有退出压力</td></tr><tr><th>有成交且收在当日最低</th><td>{r.close_at_daily_low}只</td><td>含上述上涨同价记录；不能直接叫作收盘跌停</td></tr></tbody></table></div>
 <p>这份原始报表有{packet.reported_columns.length}列，能核开高低收，却没有实际涨跌停价字段。“涨跌幅”列也不是实际限价。上述类别存在重叠，不相加；更不能据此推委托能否成交。</p>
 <details><summary>原始列、收低记录与来源</summary><p>原表列：{packet.reported_columns.join('、')}。完整导出表与首尾JSON控制页重放，新增使用的开高低收也核边界字段；市盈率在两种格式中分别名为syl/syl1，明确映射但不参与计算。</p><p>收盘等于当日最低的记录：{r.close_at_low_rows.map(x=>x.name+' '+x.symbol).join('、')}。</p><p>{r.boundary}</p><p><a href={packet.export_url} target="_blank" rel="noreferrer">深交所20日原始行情导出 ↗</a> · 原件SHA256 <code>{packet.export_source.response_sha256}</code>。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看逐字段核验及74只完整观察 →</a></p></details></details>
}
