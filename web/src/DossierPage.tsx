import {KeyboardEvent, useEffect, useMemo, useState} from 'react'
import {
  AlertTriangle, ArrowLeft, CalendarDays, Database, ExternalLink,
  LoaderCircle, MessageSquareText,
} from 'lucide-react'
import {Link, useLocation, useNavigate, useParams} from 'react-router-dom'
import {getDossier} from './api'
import {questionLink} from './context'
import {show} from './display'
import type {Dossier, EventNode} from './types'

const W = 1040
const H = 320
const P = {l: 54, r: 18, t: 18, b: 30}
const tm = (value: string) => new Date(`${value.slice(0, 10)}T00:00:00`).getTime()

function PriceChart({data, selected, onSelect}: {
  data: Dossier
  selected: EventNode | null
  onSelect: (node: EventNode) => void
}) {
  const geometry = useMemo(() => {
    const xs = data.price_series.map(point => tm(point.date))
    const ys = data.price_series.map(point => point.close)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const x = (value: number) => P.l + (value - minX) / Math.max(1, maxX - minX) * (W - P.l - P.r)
    const y = (value: number) => P.t + (1 - (value - minY) / Math.max(.01, maxY - minY)) * (H - P.t - P.b)
    const points = data.price_series
      .map(point => `${x(tm(point.date)).toFixed(1)},${y(point.close).toFixed(1)}`)
      .join(' ')
    const nodes = data.events.map(node => {
      let nearest = data.price_series[0]
      let distance = Math.abs(tm(nearest.date) - tm(node.date))
      for (const point of data.price_series) {
        const candidate = Math.abs(tm(point.date) - tm(node.date))
        if (candidate < distance) {
          nearest = point
          distance = candidate
        }
      }
      return {node, cx: x(tm(node.date)), cy: y(nearest.close)}
    }).filter(placed => placed.cx >= P.l && placed.cx <= W - P.r)
    return {minY, maxY, points, nodes}
  }, [data])

  const onKey = (event: KeyboardEvent<SVGCircleElement>, node: EventNode) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(node)
    }
  }

  return (
    <div className="chart-scroll" tabIndex={0}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="group" aria-label="股价与公告节点">
        {[0, 1, 2, 3, 4].map(index => {
          const value = geometry.minY + (geometry.maxY - geometry.minY) * index / 4
          const y = H - P.b - (H - P.t - P.b) * index / 4
          return (
            <g key={index}>
              <line x1={P.l} x2={W - P.r} y1={y} y2={y}/>
              <text x={P.l - 8} y={y + 4} textAnchor="end">{value.toFixed(1)}</text>
            </g>
          )
        })}
        <polyline points={geometry.points}/>
        {geometry.nodes.map(({node, cx, cy}) => (
          <circle
            key={node.event_id}
            cx={cx}
            cy={cy}
            r={selected?.event_id === node.event_id ? 5.5 : 3.2}
            className={selected?.event_id === node.event_id ? 'selected' : ''}
            tabIndex={0}
            role="button"
            aria-label={`${node.date} ${node.title}`}
            onClick={() => onSelect(node)}
            onKeyDown={event => onKey(event, node)}
          />
        ))}
      </svg>
    </div>
  )
}

function Timeline({data, selected, onSelect}: {
  data: Dossier
  selected: EventNode | null
  onSelect: (node: EventNode) => void
}) {
  const dates = data.events.map(node => tm(node.date))
  const first = Math.min(...dates)
  const last = Math.max(...dates)
  return (
    <div className="timeline-scroll" tabIndex={0}>
      <div className="timeline">
        {data.timeline_lanes.map(lane => (
          <div className="lane" key={lane.lane_id}>
            <strong>{lane.label}</strong>
            <div>
              {data.events.filter(node => node.timeline_lane === lane.lane_id).map(node => (
                <button
                  key={node.event_id}
                  className={selected?.event_id === node.event_id ? 'selected' : ''}
                  style={{left: `${(tm(node.date) - first) / Math.max(1, last - first) * 100}%`}}
                  title={`${node.date} ${node.title}`}
                  aria-label={`${node.date} ${node.title}`}
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

function Detail({symbol, node}: {symbol: string; node: EventNode | null}) {
  if (!node) {
    return <aside className="detail empty"><CalendarDays size={18}/>选择一个公告节点</aside>
  }
  const question = `围绕 ${symbol} 在 ${node.date} 的“${node.title}”，前后发生了什么，相关证据和缺口是什么？`
  return (
    <aside className="detail">
      <p className="eyebrow">{node.date}</p>
      <h2>{node.title}</h2>
      <dl>
        <div><dt>事件路径</dt><dd>{node.episode_label}</dd></div>
        <div><dt>节点类型</dt><dd>{node.subtype_label}</dd></div>
        <div><dt>来源</dt><dd>{node.provenance_refs.map(show).join(' · ')}</dd></div>
      </dl>
      <Link
        className="primary"
        to={questionLink({
          symbol,
          selected_event: {event_id: node.event_id, date: node.date, title: node.title},
          selected_episode: node.episode_type,
          selected_lenses: node.related_lens_ids,
          date_range: {start: node.date, end: node.date},
          object_scope: {kind: 'stock_event', ref: node.event_id},
        }, question)}
      >
        <MessageSquareText size={16}/>就此提问
      </Link>
    </aside>
  )
}

function Content({symbol}: {symbol: string}) {
  const location = useLocation()
  const navigate = useNavigate()
  const search = new URLSearchParams(location.search)
  const selectedId = search.get('event')
  const [data, setData] = useState<Dossier | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    getDossier(symbol, selectedId, controller.signal)
      .then(setData)
      .catch(cause => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : '个股证据服务不可用')
        }
      })
    return () => controller.abort()
  }, [symbol, selectedId])

  if (error) return <div className="page-state error"><AlertTriangle size={20}/>{error}</div>
  if (!data) return <div className="page-state"><LoaderCircle className="spin" size={20}/>正在读取证据</div>

  const selected = data.events.find(node => node.event_id === selectedId) ?? null
  const select = (node: EventNode) => {
    const params = new URLSearchParams(location.search)
    params.set('event', node.event_id)
    params.set('date', node.date)
    params.set('title', node.title)
    navigate(`/stocks/${symbol}?${params}`, {replace: true})
  }

  return (
    <div className="dossier">
      <header className="dossier-head">
        <div>
          <Link className="back" to="/"><ArrowLeft size={15}/>返回研究问答</Link>
          <p className="eyebrow">个股证据 · 截至 {data.as_of}</p>
          <h1>{data.display_name}</h1>
          <div className="status">
            <b>{data.symbol}</b>
            {data.status_intervals.map((interval, index) => (
              <span key={index}>{show(interval.status_name)}</span>
            ))}
          </div>
        </div>
        <Link
          className="small-button"
          to={questionLink({symbol}, `${symbol} 当前有哪些关键事件、历史路径、证据和数据缺口？`)}
        >
          提问<ExternalLink size={14}/>
        </Link>
      </header>
      <div className="dossier-grid">
        <section className="market">
          <header>
            <div>
              <p className="eyebrow">前复权收盘价</p>
              <h2>价格与公告节点</h2>
            </div>
            <span>{data.price_series.length.toLocaleString('zh-CN')} 个交易日</span>
          </header>
          <PriceChart data={data} selected={selected} onSelect={select}/>
          <Timeline data={data} selected={selected} onSelect={select}/>
        </section>
        <Detail symbol={symbol} node={selected}/>
      </div>
      <section className="lens-band">
        <p className="eyebrow">冻结 Lens 库</p>
        <h2>相关 Lens</h2>
        <div>
          {data.lens_summaries.map(summary => (
            <article key={String(summary.release_id)}>
              <strong>{show(summary.release_id)}</strong>
              <span>{show(summary.display_label)}</span>
              <p>{show(summary.contributed_section)}</p>
              <small>{show(summary.evidence_grade)}</small>
            </article>
          ))}
        </div>
        {data.data_gaps.length > 0 && (
          <aside className="dossier-gaps">
            <Database size={17}/>
            <div>
              {data.data_gaps.map(gap => (
                <p key={String(gap.gap_id)}>
                  {show(gap.display_label)}{gap.debt_ref ? ` · ${show(gap.debt_ref)}` : ''}
                </p>
              ))}
            </div>
          </aside>
        )}
      </section>
    </div>
  )
}

export function DossierPage() {
  const {symbol = '603398'} = useParams()
  return <Content key={symbol} symbol={symbol}/>
}
