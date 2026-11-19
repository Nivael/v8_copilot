import {cleanup,render,screen,fireEvent} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STWeilingStageCheck} from './STWeilingStageCheck'
import type {WeilingStageCheck} from './STWeilingStageCheck'
import raw from './__fixtures__/weiling-stage-check.json'
import current from './__fixtures__/current-extension.json'
import type {CurrentExtension} from './STCurrentExtension'
import {STCurrentCompanyReading} from './STCurrentCompanyReading'
afterEach(cleanup)
const data=raw as WeilingStageCheck
it('separates completed control change from a future meeting and payment',()=>{
 render(<STWeilingStageCheck data={data}/> )
 expect(screen.getByRole('heading',{name:'控制权已经变更，赠款仍待审议和履约'})).toBeVisible()
 expect(screen.getByText(/下一次具体核对点/)).toHaveTextContent('2026-11-23 14:00')
 fireEvent.click(screen.getByText('沿四个阶段查看原件与当时状态'))
 expect(screen.getByText(/已登记3189.739万股/)).toBeVisible()
 expect(screen.getByText(/文件落款2026-11-05/)).toHaveTextContent('2026-11-04')
 expect(screen.getByRole('link',{name:/公司控股股东及实际控制人变更.*第3页/})).toHaveAttribute('href',expect.stringContaining('#page=3'))
})
it('keeps the report period and blank signature date separate from November publication',()=>{
 render(<STWeilingStageCheck data={data}/>);fireEvent.click(screen.getByText('督导报告能证明到哪一步？'))
 expect(screen.getByText(/报告期2026-08-28/)).toHaveTextContent('2026-09-30')
 expect(screen.getByText(/报告期2026-08-28/)).toHaveTextContent('签署页确切日期未核得')
})
it('keeps shared event-window anchors visible rather than counting two validations',()=>{
 render(<STWeilingStageCheck data={data}/>);fireEvent.click(screen.getByText('披露之后，股价与市场是否同向？'))
 expect(screen.getByRole('table',{name:'威领阶段披露后五交易日对照'})).toBeVisible()
 expect(screen.getByText(/行情观察起点相同/)).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'公告后观察窗口'}),{target:{value:'20'}})
 const table=screen.getByRole('table',{name:'威领阶段披露后二十交易日对照'})
 expect(table).toHaveTextContent('窗口未满或缺价')
 expect(table).toHaveTextContent('2026-11-09')
})
it('places the supplement only inside the matching tracked company',()=>{
 const d={...current,stage_followup:data}as CurrentExtension
 const {rerender}=render(<STCurrentCompanyReading data={d} symbol="002667.SZ" historicalThrough="2026-11-06"/> )
 expect(screen.getByRole('region',{name:'威领控制权与赠款阶段核对'})).toBeVisible()
 rerender(<STCurrentCompanyReading data={d} symbol="603398.SH" historicalThrough="2026-11-06"/> )
 expect(screen.queryByRole('region',{name:'威领控制权与赠款阶段核对'})).not.toBeInTheDocument()
})
