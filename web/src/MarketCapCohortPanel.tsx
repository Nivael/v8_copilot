import {useMemo} from 'react'
import {marketCapCohortData,type MarketCapCohortRow as Row} from './marketCapCohortData'

function Cohort({row}:{row:Row}) {
  return (
    <article className="market-cap-cohort-card">
      <header><h3>{String(row['分组'])}</h3><span>{String(row['成员数'])} 只</span></header>
      <dl>
        <div><dt>平均收益</dt><dd>{String(row['平均收益'])}</dd></div>
        <div><dt>中位收益</dt><dd>{String(row['中位收益'])}</dd></div>
        <div><dt>收益覆盖</dt><dd>{String(row['有效收益数'])}/{String(row['成员数'])} · {String(row['收益覆盖率'])}</dd></div>
        <div><dt>中位总市值</dt><dd>{String(row['中位总市值'])}</dd></div>
      </dl>
    </article>
  )
}

export function MarketCapCohortPanel({rows}:{rows:Row[]}) {
  const {definition,microcap,other,summary,gap}=useMemo(()=>marketCapCohortData(rows),[rows])

  if(gap)return (
    <section className="market-cap-cohorts market-cap-gap" aria-label="市值分层缺口">
      <p className="eyebrow">POINT-IN-TIME MARKET CAP</p>
      <h2>市值分层暂不可用</h2>
      <p>{String(gap['缺口'])}</p>
    </section>
  )
  if(!definition || !microcap || !other || !summary)return null

  return (
    <section className="market-cap-cohorts" aria-label="窗口起点市值分层">
      <header>
        <div><p className="eyebrow">POINT-IN-TIME MARKET CAP</p><h2>窗口起点市值分层</h2></div>
        <span>{String(definition['收益窗口起点'])} — {String(definition['收益窗口终点'])}</span>
      </header>
      <div className="market-cap-definition">
        <strong>微盘阈值 {String(definition['微盘阈值'])}</strong>
        <span>{String(definition['微盘口径'])}</span>
        <span>因子日期 {String(definition['因子日期'])} · 市值覆盖 {String(definition['有效市值数'])}/{String(definition['ST成员数'])}（{String(definition['市值覆盖率'])}）</span>
      </div>
      <div className="market-cap-cohort-grid">
        <Cohort row={microcap}/><Cohort row={other}/>
      </div>
      <div className="market-cap-relative" aria-label="市值分层相对收益">
        <div><span>微盘 − 普通 ST · 平均</span><strong>{String(summary['微盘减普通ST平均收益'])}</strong></div>
        <div><span>微盘 − 普通 ST · 中位</span><strong>{String(summary['微盘减普通ST中位收益'])}</strong></div>
      </div>
      <p className="market-cap-boundary">{String(summary['解释边界'])}</p>
    </section>
  )
}
