import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STLingnanBondFollowup} from './STLingnanBondFollowup'
import type {LingnanExitFollowup} from './STLingnanExitFollowup'
import fixture from './__fixtures__/lingnan-exit-followup.json'
afterEach(cleanup)
it('keeps the report-time judgment, later receipt and collateral stages distinct',()=>{
 render(<STLingnanBondFollowup data={fixture as LingnanExitFollowup}/>)
 const region=screen.getByRole('region',{name:'岭南债券判决与质押补核'})
 expect(region).toHaveTextContent('事实以2026年11月3日报告披露时为准')
 expect(region).toHaveTextContent('不能把10月判决倒填为9月末已知')
 expect(region).toHaveTextContent('股权价值实质主要来自应收账款')
 expect(region).toHaveTextContent('不是法院判决原件')
 fireEvent.click(within(region).getAllByText('核对这项原件依据')[0])
 expect(within(region).getByRole('link',{name:'PDF物理第15页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-11-03/1225653773.PDF#page=15')
})
it.each(['missing','url','date'])('withholds the new conclusions when the saved source binding differs: %s',change=>{
 const d=structuredClone(fixture) as LingnanExitFollowup
 if(change==='missing')d.source_refs=d.source_refs.filter(s=>s.announcement_id!=='1225653773')
 else d.source_refs=d.source_refs.map(s=>s.announcement_id==='1225653773'?{...s,...(change==='url'?{url:'https://example.com/wrong.pdf'}:{published_on:'2026-11-04'})}:s)
 render(<STLingnanBondFollowup data={d}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示结论')
 expect(screen.queryByRole('heading',{name:'有判决、有质押，就能当作已经兑付吗？'})).not.toBeInTheDocument()
})
