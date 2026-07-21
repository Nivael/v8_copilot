export type ComparisonRow = Record<string, unknown>

export type ComparisonPoint = {
  date:string
  stock:number|null
  st:number
  csi2000:number
  market:number
}

function finiteNumber(value: unknown): number|null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function comparisonData(rows: ComparisonRow[]): {
  summary:ComparisonRow|null
  points:ComparisonPoint[]
} {
  const summary=rows.find(row=>row.row_id==='market_comparison_summary') ?? null
  const points=rows
    .filter(row=>row['记录类型']==='市场对比序列')
    .map(row=>({
      date:String(row.date ?? row['日期'] ?? ''),
      stock:finiteNumber(row.stock_normalized),
      st:finiteNumber(row.st_normalized),
      csi2000:finiteNumber(row.csi2000_normalized),
      market:finiteNumber(row.market_normalized),
    }))
    .filter((point):point is ComparisonPoint=>(
      Boolean(point.date) && point.st!==null && point.csi2000!==null && point.market!==null
    ))
  return {summary,points}
}
