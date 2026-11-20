import type {MarketStageExperience} from './stRegimeTypes'

export function relativeLossRows(data:MarketStageExperience){
 const baseline=new Set(data.stages[0]?.common_sample.symbols??[])
 const stages=data.stages.map(stage=>{
  const members=new Set(stage.common_sample.symbols)
  const rows=stage.rows.filter(row=>members.has(row.symbol))
  if(members.size!==data.common_verified_members||[...members].some(symbol=>!baseline.has(symbol))||rows.length!==members.size||new Set(rows.map(r=>r.symbol)).size!==members.size)return null
  const values=rows.map(row=>row.certified_return_pct===null||row.certified_return_pct.trim()===''?NaN:Number(row.certified_return_pct))
  const market=stage.market_pct.trim()===''?NaN:Number(stage.market_pct)
  if(!Number.isFinite(market)||values.some(v=>!Number.isFinite(v)))return null
  return {anchor:stage.anchor,through:stage.through,members:members.size,
   losses:values.filter(v=>v<0).length,
   beats:values.filter(v=>v>market).length,
   beatButLoss:values.filter(v=>v>market&&v<0).length}
 })
 return stages.every(row=>row!==null)?stages:null
}

export function STRelativeLoss({data}:{data:MarketStageExperience}){
 const rows=relativeLossRows(data)
 if(!rows)return <p>共同样本的核价资料不足，暂不计算“跑赢却下跌”的数量。</p>
 return <details><summary>跑赢大盘的股票，有多少仍在跌？</summary>
  <p>跑赢只说明相对表现。以下始终比较同一{data.common_verified_members}家核价通过公司；“跑赢却下跌”是跑赢公司的子集，不能与前两列相加。</p>
  <div className="learning-table-wrap"><table className="regime-table"><caption>同一共同样本：绝对下跌与相对跑赢分别计数</caption><thead><tr><th>区间</th><th>下跌／共同样本</th><th>跑赢大盘</th><th>其中仍下跌</th></tr></thead><tbody>{rows.map(r=><tr key={r.anchor}><th>{r.anchor} → {r.through}</th><td>{r.losses}／{r.members}</td><td>{r.beats}家</td><td>{r.beatButLoss}／{r.beats}家</td></tr>)}</tbody></table></div>
  <p>保留的经验：评价抗跌时，同时核对绝对损失；相对优势本身不能证明资金安全。这里没有检验减仓规则、成交约束或未来收益。</p>
  <p>共同样本是事后完整记录交集，未代表全部150家或当时可交易名单。五段来自同一股票池和连续市场时期，不算五次独立验证；7月从3日收盘起，11月只到19日。逐股价格与来源在分段明细中保留。</p>
 </details>
}
