export type MarketCapCohortRow = Record<string, unknown>

export type MarketCapCohortData = {
  definition:MarketCapCohortRow|null
  microcap:MarketCapCohortRow|null
  other:MarketCapCohortRow|null
  summary:MarketCapCohortRow|null
  gap:MarketCapCohortRow|null
}

export function marketCapCohortData(rows:MarketCapCohortRow[]):MarketCapCohortData {
  const byId=(id:string)=>rows.find(row=>row.row_id===id) ?? null
  return {
    definition:byId('microcap_definition'),
    microcap:byId('microcap_distribution'),
    other:byId('other_st_distribution'),
    summary:byId('microcap_comparison_summary'),
    gap:byId('microcap_comparison_gap'),
  }
}
