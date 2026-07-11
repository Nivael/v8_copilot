import '@testing-library/jest-dom/vitest'
import {vi} from 'vitest'

vi.mock('lightweight-charts', () => ({
  ColorType: {Solid: 'solid'},
  CrosshairMode: {Normal: 0},
  LineSeries: 'LineSeries',
  createSeriesMarkers: () => ({setMarkers: vi.fn(), detach: vi.fn(), markers: () => []}),
  createChart: () => {
    const scale = {
      setVisibleRange: vi.fn(),
      fitContent: vi.fn(),
      subscribeVisibleTimeRangeChange: vi.fn(),
      unsubscribeVisibleTimeRangeChange: vi.fn(),
    }
    return {
      addSeries: () => ({setData: vi.fn()}),
      timeScale: () => scale,
      subscribeClick: vi.fn(),
      unsubscribeClick: vi.fn(),
      remove: vi.fn(),
    }
  },
}))

// Node 22+ 的实验性 webstorage 会以残缺对象遮蔽 jsdom 的 localStorage
// （--localstorage-file 无有效路径时连 setItem 都没有），统一替换为内存实现，
// 让组件的历史记录逻辑与测试的 clear() 都有真实 Storage 语义可依赖。
if (typeof window.localStorage?.setItem !== 'function') {
  const store = new Map<string, string>()
  const memoryStorage: Storage = {
    getItem: key => store.get(key) ?? null,
    setItem: (key, value) => { store.set(key, String(value)) },
    removeItem: key => { store.delete(key) },
    clear: () => { store.clear() },
    key: index => Array.from(store.keys())[index] ?? null,
    get length() { return store.size },
  }
  Object.defineProperty(window, 'localStorage', {value: memoryStorage, configurable: true})
  Object.defineProperty(globalThis, 'localStorage', {value: memoryStorage, configurable: true})
}
