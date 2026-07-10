import { KeyboardEvent, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  CalendarDays,
  ExternalLink,
  LoaderCircle,
  MessageSquareText,
} from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { fetchDossier } from './api'
import { questionSearch } from './context'
import { humanize } from './display'
import type { EventNode, StockDossier } from './types'

const WIDTH = 1040
const HEIGHT = 320
const PAD = { left: 54, right: 18, top: 18, bottom: 30 }

function time(value: string): number {
  return new Date(`${value.slice(0, 10)}T00:00:00`).getTime()
}

function PriceChart({ dossier, selected, onSelect }: {
  dossier: StockDossier
  selected: EventNode | null
  onSelect: (node: EventNode) => void
}) {
  const geometry = useMemo(() => {
    const prices = dossier.price_series
    const xs = prices.map((point) => time(point.date))
    const ys = prices.map((point) => point.close)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const x = (value: number) => PAD.left + ((value - minX) / Math.max(1, maxX - minX)) * (WIDTH - PAD.left - PAD.right)
    const y = (value: number) => PAD.top + (1 - (value - minY) / Math.max(0.01, maxY - minY)) * (HEIGHT - PAD.top - PAD.bottom)
    const points = prices.map((point) => `${x(time(point.date)).toFixed(1)},${y(point.close).toFixed(1)}`).join(' ')
    const nodePoints = dossier.event_nodes.map((node) => {
      const target = time(node.date)
      let nearest = prices[0]
      let distance = Math.abs(time(nearest.date) - target)
      for (const point of prices) {
        const next = Math.abs(time(point.date) - target)
        if (next < distance) { nearest = point; distance = next }
      }
      return { node, cx: x(target), cy: y(nearest.close) }
    }).filter((item) => item.cx >= PAD.left && item.cx <= WIDTH - PAD.right)
    return { minY, maxY, points, nodePoints }
  }, [dossier])

  function keyboard(event: KeyboardEvent<SVGCircleElement>, node: EventNode) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(node)
    }
  }

  return (
    <div className="chart-scroll" tabIndex={0} aria-label="复权收盘价与公告节点图">
      <svg className="price-chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="股价与公告节点">
        {[0, 1, 2, 3, 4].map((step) => {
          const value = geometry.minY + ((geometry.maxY - geometry.minY) * step) / 4
          const y = HEIGHT - PAD.bottom - ((HEIGHT - PAD.top - PAD.bottom) * step) / 4
          return <g key={step}><line className="gridline" x1={PAD.left} x2={WIDTH - PAD.right} y1={y} y2={y} /><text className="axis-label" x={PAD.left - 9} y={y + 4} textAnchor="end">{value.toFixed(1)}</text></g>
        })}
        <polyline className="price-line" points={geometry.points} />
        {geometry.nodePoints.map(({ node, cx, cy }) => (
          <circle
            className={`chart-node ${selected?.event_id === node.event_id ? 'selected' : ''}`}
            key={node.event_id}
            cx={cx}
            cy={cy}
            r={selected?.event_id === node.event_id ? 5.5 : 3.2}
            fill={dossier.timeline_lanes.find((lane) => lane.lane_id === node.lane_id)?.color ?? '#475569'}
            tabIndex={0}
            role="button"
            aria-label={`${node.date} ${node.title}`}
            onClick={() => onSelect(node)}
            onKeyDown={(event) => keyboard(event, node)}
          />
        ))}
      </svg>
    </div>
  )
}

function Timeline({ dossier, selected, onSelect }: {
  dossier: StockDossier
  selected: EventNode | null
  onSelect: (node: EventNode) => void
}) {
  const dates = dossier.event_nodes.map((node) => time(node.date))
  const min = Math.min(...dates)
  const max = Math.max(...dates)
  return (
    <div className="timeline-scroll" tabIndex={0} aria-label="事件时间线">
      <div className="timeline-canvas">
        {dossier.timeline_lanes.map((lane) => (
          <div className="timeline-row" key={lane.lane_id}>
            <div className="lane-name"><span style={{ background: lane.color }} />{lane.display_label}</div>
            <div className="lane-track">
              {dossier.event_nodes.filter((node) => node.lane_id === lane.lane_id).map((node) => (
                <button
                  className={`timeline-node ${selected?.event_id === node.event_id ? 'selected' : ''}`}
                  key={node.event_id}
                  type="button"
                  title={`${node.date} ${node.title}`}
                  aria-label={`${node.date} ${node.title}`}
                  style={{ left: `${((time(node.date) - min) / Math.max(1, max - min)) * 100}%`, borderColor: lane.color }}
                  onClick={() => onSelect(node)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function NodeDetail({ symbol, node }: { symbol: string; node: EventNode | null }) {
  if (!node) return <aside className="node-detail empty"><CalendarDays size={18} /><p>选择一个公告节点</p></aside>
  const question = `围绕 ${symbol} 在 ${node.date} 的“${node.title}”，前后发生了什么，相关证据和缺口是什么？`
  const href = questionSearch({
    symbol,
    event_id: node.event_id,
    event_date: node.date,
    event_title: node.title,
  }, question)
  return (
    <aside className="node-detail">
      <p className="eyebrow">{node.date}</p>
      <h2>{node.title}</h2>
      <dl>
        <div><dt>事件路径</dt><dd>{node.episode_label}</dd></div>
        <div><dt>节点类型</dt><dd>{node.subtype_label}</dd></div>
        <div><dt>来源</dt><dd>{node.source_material_label}</dd></div>
      </dl>
      <Link className="primary-action" to={href}><MessageSquareText size={16} />就此提问</Link>
    </aside>
  )
}

function DossierContent({ symbol }: { symbol: string }) {
  const location = useLocation()
  const navigate = useNavigate()
  const selectedId = new URLSearchParams(location.search).get('event')
  const [dossier, setDossier] = useState<StockDossier | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetchDossier(symbol, controller.signal)
      .then(setDossier)
      .catch((caught) => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : '个股证据服务不可用') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [symbol])

  const selected = dossier?.event_nodes.find((node) => node.event_id === selectedId) ?? null
  function select(node: EventNode) {
    const params = new URLSearchParams(location.search)
    params.set('event', node.event_id)
    navigate(`/stocks/${symbol}?${params.toString()}`, { replace: true })
  }

  if (loading) return <div className="page-state"><LoaderCircle className="spin" size={20} />正在读取证据</div>
  if (error || !dossier) return <div className="page-state error" role="alert"><AlertTriangle size={20} />{error || '当前没有个股证据'}</div>

  return (
    <div className="dossier-page">
      <header className="dossier-header">
        <div>
          <Link className="back-link" to="/"><ArrowLeft size={15} />返回研究问答</Link>
          <p className="eyebrow">个股证据 · 截至 {dossier.as_of}</p>
          <h1>{dossier.display_name}</h1>
          <div className="symbol-line"><strong>{dossier.symbol}</strong>{dossier.status_intervals.map((status) => <span key={`${status.start_date}-${status.display_name}`}>{humanize(status.display_name)}</span>)}</div>
        </div>
        <Link className="icon-text-button" to={questionSearch({ symbol }, `${symbol} 当前有哪些关键事件、历史路径、证据和数据缺口？`)}>
          提问 <ExternalLink size={15} />
        </Link>
      </header>

      <div className="dossier-grid">
        <section className="market-panel">
          <div className="section-title"><div><p className="eyebrow">前复权收盘价</p><h2>价格与公告节点</h2></div><span>{dossier.price_series.length.toLocaleString('zh-CN')} 个交易日</span></div>
          <PriceChart dossier={dossier} selected={selected} onSelect={select} />
          <Timeline dossier={dossier} selected={selected} onSelect={select} />
        </section>
        <NodeDetail symbol={symbol} node={selected} />
      </div>

      <section className="lens-band">
        <div className="section-title"><div><p className="eyebrow">Release library</p><h2>相关 Lens</h2></div></div>
        <div className="lens-list">
          {dossier.lens_invocations.map((lens) => (
            <article key={lens.release_id}>
              <strong>{lens.release_id}</strong>
              <span>{humanize(lens.lens_label)}</span>
              <p>{humanize(lens.contributed_section)}</p>
              {(lens.evidence_grade_label || lens.cohort_label) && <small>{humanize(lens.evidence_grade_label)} · {humanize(lens.cohort_label)}</small>}
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

export function DossierPage() {
  const { symbol = '603398' } = useParams()
  return <DossierContent key={symbol} symbol={symbol} />
}
