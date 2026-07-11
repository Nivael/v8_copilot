import {useCallback, useEffect, useRef, useState} from 'react'
import {
  AlertTriangle, ArrowLeft, CalendarDays, Database, ExternalLink,
  LoaderCircle, MessageSquareText,
} from 'lucide-react'
import {Link, useLocation, useNavigate, useParams} from 'react-router-dom'
import {getDossier} from './api'
import {questionLink} from './context'
import {show} from './display'
import {InteractivePriceChart} from './InteractivePriceChart'
import type {Dossier, EventNode} from './types'

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
  const initialFocus = useRef(selectedId)
  const [data, setData] = useState<Dossier | null>(null)
  const [error, setError] = useState('')
  const select = useCallback((node: EventNode) => {
    const params = new URLSearchParams()
    params.set('event', node.event_id)
    params.set('date', node.date)
    params.set('title', node.title)
    navigate(`/stocks/${symbol}?${params}`, {replace: true})
  }, [navigate, symbol])

  useEffect(() => {
    const controller = new AbortController()
    getDossier(symbol, initialFocus.current, controller.signal)
      .then(setData)
      .catch(cause => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : '个股证据服务不可用')
        }
      })
    return () => controller.abort()
  }, [symbol])

  if (error) return <div className="page-state error"><AlertTriangle size={20}/>{error}</div>
  if (!data) return <div className="page-state"><LoaderCircle className="spin" size={20}/>正在读取证据</div>

  const selected = data.events.find(node => node.event_id === selectedId) ?? null
  const statusLabels = Array.from(new Set(data.status_intervals.map(interval => (
    show(interval.status_type ?? interval.status_name ?? '风险警示')
  ))))
  return (
    <div className="dossier">
      <header className="dossier-head">
        <div>
          <Link className="back" to="/"><ArrowLeft size={15}/>返回研究问答</Link>
          <p className="eyebrow">个股证据 · 截至 {data.as_of}</p>
          <h1>{data.display_name}</h1>
          <div className="status">
            <b>{data.symbol}</b>
            {statusLabels.map(label => <span key={label}>{label}</span>)}
          </div>
        </div>
        <Link
          className="small-button"
          to={questionLink({symbol}, `${symbol} 当前有哪些关键事件、历史路径、证据和数据缺口？`)}
        >
          提问<ExternalLink size={14}/>
        </Link>
      </header>
      <section className="freshness-strip" aria-label="数据新鲜度">
        <div><span>价格截至</span><strong>{data.display_labels.price_data_as_of ?? data.as_of}</strong></div>
        <div><span>公告截至</span><strong>{data.display_labels.announcement_data_as_of ?? '无记录'}</strong></div>
        <div><span>公告刷新检查</span><strong>{data.display_labels.announcement_refresh_checked_at ?? '未接入'}</strong></div>
        <div><span>M6 索引截至</span><strong>{data.display_labels.episode_index_as_of ?? '未记录'}</strong></div>
      </section>
      <div className="dossier-grid">
        <section className="market">
          <header>
            <div>
              <p className="eyebrow">前复权收盘价</p>
              <h2>价格与公告节点</h2>
            </div>
            <span>{data.display_labels.event_count ?? `${data.events.length} 个节点`} · {data.price_series.length.toLocaleString('zh-CN')} 个交易日</span>
          </header>
          <InteractivePriceChart data={data} selected={selected} onSelect={select}/>
        </section>
        <Detail symbol={symbol} node={selected}/>
      </div>
      <section className="lens-band">
        <p className="eyebrow">冻结 Lens 库</p>
        <header className="lens-band-head">
          <div>
            <h2>与当前事件路径匹配的 Lens</h2>
            <p>只显示实际命中的冻结 Lens，不用无关 Lens 填充页面。</p>
          </div>
          <span>{data.lens_summaries.length} 条命中 · {data.display_labels.lens_library_size ?? '冻结库'}</span>
        </header>
        <div>
          {data.lens_summaries.map(summary => (
            <article key={String(summary.release_id)}>
              <strong>{show(summary.release_id)}</strong>
              <span>{show(summary.display_label)}</span>
              <p>{show(summary.contributed_section)}</p>
              <small>{show(summary.evidence_grade || summary.lens_kind)}</small>
            </article>
          ))}
          {data.lens_summaries.length === 0 && (
            <p className="lens-empty">当前事件路径没有匹配到可用的冻结 Lens。价格和公告数据仍可查，但不会被包装成已验证历史先验。</p>
          )}
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
