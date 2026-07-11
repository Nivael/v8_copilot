import {useEffect, useMemo, useRef, useState} from 'react'
import {
  ColorType,
  CrosshairMode,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts'
import {CalendarRange, RotateCcw} from 'lucide-react'
import type {Dossier, EventNode} from './types'

type RangeKey = '3M'|'6M'|'1Y'|'3Y'|'ALL'
type VisibleRange = {from: string; to: string}

const RANGE_LABELS: Array<{key: RangeKey; label: string}> = [
  {key: '3M', label: '3月'},
  {key: '6M', label: '6月'},
  {key: '1Y', label: '1年'},
  {key: '3Y', label: '3年'},
  {key: 'ALL', label: '全部'},
]

const LANE_COLORS: Record<string, string> = {
  restructuring: '#b45309',
  st_risk: '#c2413b',
  control: '#2563a8',
  regulatory: '#6d5d8f',
  financial: '#53606f',
}

const IMPORTANT_EVENT_TERMS = [
  '预重整', '重整进展', '退市风险警示', '终止上市', '撤销风险警示',
  '行政处罚', '立案', '司法拍卖', '控制权', '权益变动', '资金占用',
  '审计意见', '审计报告否定意见',
]

function isImportantEvent(event: EventNode): boolean {
  return IMPORTANT_EVENT_TERMS.some(term => event.title.includes(term))
}

function timeText(value: Time): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number') return new Date(value * 1000).toISOString().slice(0, 10)
  return `${value.year}-${String(value.month).padStart(2, '0')}-${String(value.day).padStart(2, '0')}`
}

function rangeStart(lastDate: string, key: RangeKey): string {
  if (key === 'ALL') return ''
  const date = new Date(`${lastDate}T00:00:00`)
  const months = key === '3M' ? 3 : key === '6M' ? 6 : key === '1Y' ? 12 : 36
  date.setMonth(date.getMonth() - months)
  return date.toISOString().slice(0, 10)
}

function nearestTradingDate(date: string, tradingDates: string[]): string {
  let low = 0
  let high = tradingDates.length - 1
  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    if (tradingDates[mid] === date) return date
    if (tradingDates[mid] < date) low = mid + 1
    else high = mid - 1
  }
  if (low >= tradingDates.length) return tradingDates[tradingDates.length - 1]
  if (high < 0) return tradingDates[0]
  const before = Math.abs(new Date(tradingDates[high]).getTime() - new Date(date).getTime())
  const after = Math.abs(new Date(tradingDates[low]).getTime() - new Date(date).getTime())
  return before <= after ? tradingDates[high] : tradingDates[low]
}

function markersFor(
  events: EventNode[],
  tradingDates: string[],
  enabledLanes: Set<string>,
  importantOnly: boolean,
  visible: VisibleRange,
  selectedId?: string,
): SeriesMarker<Time>[] {
  const inWindow = events.filter(event => (
    enabledLanes.has(event.timeline_lane)
      && (!importantOnly || isImportantEvent(event))
      && event.date >= visible.from
      && event.date <= visible.to
  ))
  const maxMarkers = 24
  const stride = Math.max(1, Math.ceil(inWindow.length / maxMarkers))
  const sampled = inWindow.filter((event, index) => (
    index % stride === 0 || event.event_id === selectedId
  ))
  return sampled.map(event => ({
    id: event.event_id,
    time: nearestTradingDate(event.date, tradingDates) as Time,
    position: 'aboveBar',
    color: event.event_id === selectedId ? '#111827' : (LANE_COLORS[event.timeline_lane] ?? '#53606f'),
    shape: event.event_id === selectedId ? 'arrowDown' : 'circle',
    size: event.event_id === selectedId ? 1.35 : 0.7,
  }))
}

function EventNavigator({
  data, visible, enabledLanes, importantOnly, selected, onToggleLane, onToggleImportant, onSelect,
}: {
  data: Dossier
  visible: VisibleRange
  enabledLanes: Set<string>
  importantOnly: boolean
  selected: EventNode | null
  onToggleLane: (laneId: string) => void
  onToggleImportant: () => void
  onSelect: (node: EventNode) => void
}) {
  const visibleEvents = useMemo(() => data.events
    .filter(event => enabledLanes.has(event.timeline_lane))
    .filter(event => !importantOnly || isImportantEvent(event))
    .filter(event => event.date >= visible.from && event.date <= visible.to)
    .sort((a, b) => b.date.localeCompare(a.date)), [data.events, enabledLanes, importantOnly, visible])

  return (
    <section className="event-navigator" aria-label="当前时间窗公告节点">
      <header>
        <div>
          <h3>当前时间窗事件</h3>
          <p>{visible.from} 至 {visible.to} · {visibleEvents.length} 个节点</p>
        </div>
        <div className="event-filters" aria-label="事件类型筛选">
          <label className="important-toggle">
            <input type="checkbox" checked={importantOnly} onChange={onToggleImportant}/>
            仅重点节点
          </label>
          {data.timeline_lanes.map(lane => (
            <button
              type="button"
              className={enabledLanes.has(lane.lane_id) ? 'active' : ''}
              style={{'--lane-color': LANE_COLORS[lane.lane_id] ?? '#53606f'} as React.CSSProperties}
              aria-pressed={enabledLanes.has(lane.lane_id)}
              onClick={() => onToggleLane(lane.lane_id)}
              key={lane.lane_id}
            >
              <span/>{lane.label}
            </button>
          ))}
        </div>
      </header>
      <div className="event-list">
        {visibleEvents.slice(0, 24).map(event => (
          <button
            type="button"
            className={selected?.event_id === event.event_id ? 'selected' : ''}
            onClick={() => onSelect(event)}
            key={event.event_id}
          >
            <time>{event.date}</time>
            <span className="event-kind" style={{'--lane-color': LANE_COLORS[event.timeline_lane] ?? '#53606f'} as React.CSSProperties}>
              {event.timeline_label}
            </span>
            <strong>{event.title}</strong>
          </button>
        ))}
        {visibleEvents.length === 0 && <p className="event-empty">当前时间窗没有已分类节点。拖动图表或切换事件类型继续查看。</p>}
        {visibleEvents.length > 24 && <p className="event-overflow">另有 {visibleEvents.length - 24} 个节点；缩小时间范围可逐条查看。</p>}
      </div>
    </section>
  )
}

export function InteractivePriceChart({data, selected, onSelect}: {
  data: Dossier
  selected: EventNode | null
  onSelect: (node: EventNode) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const [range, setRange] = useState<RangeKey>('1Y')
  const [enabledLanes, setEnabledLanes] = useState<Set<string>>(() => new Set(
    data.timeline_lanes
      .map(lane => lane.lane_id)
      .filter(laneId => laneId === 'restructuring' || laneId === 'st_risk'),
  ))
  const [importantOnly, setImportantOnly] = useState(true)
  const lastDate = data.price_series[data.price_series.length - 1].date
  const firstDate = data.price_series[0].date
  const [visible, setVisible] = useState<VisibleRange>({from: rangeStart(lastDate, '1Y'), to: lastDate})
  const tradingDates = useMemo(() => data.price_series.map(point => point.date), [data.price_series])
  const eventById = useMemo(() => new Map(data.events.map(event => [event.event_id, event])), [data.events])

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 390,
      layout: {
        background: {type: ColorType.Solid, color: '#ffffff'},
        textColor: '#68707d',
        fontFamily: 'Geist, -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif',
        fontSize: 12,
      },
      grid: {
        vertLines: {color: '#f2f3f5'},
        horzLines: {color: '#eceef1'},
      },
      crosshair: {mode: CrosshairMode.Normal},
      rightPriceScale: {borderColor: '#dfe3e8', scaleMargins: {top: 0.12, bottom: 0.12}},
      timeScale: {
        borderColor: '#dfe3e8',
        rightOffset: 4,
        barSpacing: 7,
        minBarSpacing: 2,
        timeVisible: false,
      },
      handleScroll: {mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false},
      handleScale: {axisPressedMouseMove: true, mouseWheel: true, pinch: true},
      kineticScroll: {mouse: true, touch: true},
    })
    const series = chart.addSeries(LineSeries, {
      color: '#1f2937',
      lineWidth: 2,
      crosshairMarkerRadius: 4,
      priceLineVisible: true,
      lastValueVisible: true,
    })
    series.setData(data.price_series.map(point => ({time: point.date as Time, value: point.close})))
    const markerPlugin = createSeriesMarkers(series, [])
    const onRange = (next: {from: Time; to: Time} | null) => {
      if (next) setVisible({from: timeText(next.from), to: timeText(next.to)})
    }
    const onClick = (param: {hoveredObjectId?: unknown}) => {
      if (typeof param.hoveredObjectId !== 'string') return
      const event = eventById.get(param.hoveredObjectId)
      if (event) onSelect(event)
    }
    chart.timeScale().subscribeVisibleTimeRangeChange(onRange)
    chart.subscribeClick(onClick)
    chartRef.current = chart
    seriesRef.current = series
    markersRef.current = markerPlugin
    chart.timeScale().setVisibleRange({from: rangeStart(lastDate, '1Y') as Time, to: lastDate as Time})
    return () => {
      chart.timeScale().unsubscribeVisibleTimeRangeChange(onRange)
      chart.unsubscribeClick(onClick)
      markerPlugin.detach()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      markersRef.current = null
    }
  }, [data.price_series, eventById, lastDate, onSelect])

  useEffect(() => {
    markersRef.current?.setMarkers(markersFor(
      data.events, tradingDates, enabledLanes, importantOnly, visible, selected?.event_id,
    ))
  }, [data.events, enabledLanes, importantOnly, selected?.event_id, tradingDates, visible])

  function selectRange(key: RangeKey) {
    setRange(key)
    if (key === 'ALL') {
      chartRef.current?.timeScale().fitContent()
      return
    }
    chartRef.current?.timeScale().setVisibleRange({
      from: rangeStart(lastDate, key) as Time,
      to: lastDate as Time,
    })
  }

  function toggleLane(laneId: string) {
    setEnabledLanes(current => {
      const next = new Set(current)
      if (next.has(laneId) && next.size > 1) next.delete(laneId)
      else next.add(laneId)
      return next
    })
  }

  return (
    <>
      <div className="chart-toolbar">
        <div className="range-switcher" aria-label="价格图时间范围">
          {RANGE_LABELS.map(item => (
            <button
              type="button"
              className={range === item.key ? 'active' : ''}
              aria-pressed={range === item.key}
              onClick={() => selectRange(item.key)}
              key={item.key}
            >{item.label}</button>
          ))}
        </div>
        <div className="chart-instruction"><CalendarRange size={14}/>滚轮缩放 · 拖动平移</div>
        <button className="icon-button" type="button" title="恢复一年视图" aria-label="恢复一年视图" onClick={() => selectRange('1Y')}>
          <RotateCcw size={15}/>
        </button>
      </div>
      <div className="interactive-chart" ref={containerRef}/>
      <EventNavigator
        data={data}
        visible={{from: visible.from || firstDate, to: visible.to || lastDate}}
        enabledLanes={enabledLanes}
        importantOnly={importantOnly}
        selected={selected}
        onToggleLane={toggleLane}
        onToggleImportant={() => setImportantOnly(value => !value)}
        onSelect={onSelect}
      />
    </>
  )
}
