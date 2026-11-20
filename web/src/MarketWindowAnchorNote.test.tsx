import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,expect,it,vi} from 'vitest'
import {MarketWindowAnchorNote} from './MarketWindowAnchorNote'
afterEach(()=>{cleanup();vi.restoreAllMocks();window.history.replaceState(null,'',window.location.pathname)})

it('opens an old direct link and waits for the main reading layout before locating it',async()=>{
 window.history.replaceState(null,'','#market-window-anchor-audit')
 const scroll=vi.fn();Object.defineProperty(HTMLElement.prototype,'scrollIntoView',{configurable:true,value:scroll})
 const view=render(<MemoryRouter><MarketWindowAnchorNote readingReady={false}/></MemoryRouter>)
 const disclosure=screen.getByText('旧复盘的起点：9月4日与7日能互换吗？').closest('details')!
 expect(disclosure.open).toBe(true);expect(scroll).not.toHaveBeenCalled()
 view.rerender(<MemoryRouter><MarketWindowAnchorNote readingReady/></MemoryRouter>)
 await waitFor(()=>expect(scroll).toHaveBeenCalledTimes(1))
 expect(screen.getByRole('table',{name:'同一终点的两种收盘起点'})).toBeVisible()
})

it('reveals only the exact window link when navigating within the loaded page',async()=>{
 const scroll=vi.fn();Object.defineProperty(HTMLElement.prototype,'scrollIntoView',{configurable:true,value:scroll})
 render(<MemoryRouter><MarketWindowAnchorNote/></MemoryRouter>)
 const disclosure=screen.getByText('旧复盘的起点：9月4日与7日能互换吗？').closest('details')!
 expect(disclosure.open).toBe(false)
 window.history.replaceState(null,'','#market-window-anchor-audit-extra');fireEvent(window,new HashChangeEvent('hashchange'))
 expect(disclosure.open).toBe(false)
 window.history.replaceState(null,'','#market-window-anchor-audit');fireEvent(window,new HashChangeEvent('hashchange'))
 await waitFor(()=>expect(disclosure.open).toBe(true));expect(scroll).toHaveBeenCalledTimes(1)
})
