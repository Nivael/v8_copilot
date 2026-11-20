import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STCashReceiptMeaning,cashReceiptMeaningBound} from './STCashReceiptMeaning'
import {STCashDirectionComparison} from './STCashDirectionComparison'
import fixture from './__fixtures__/cash-receipt-meaning.json'
import stage from './__fixtures__/cash-direction-comparison.json'
import market from './__fixtures__/cash-market-comparison.json'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
it('keeps developer sales, capital support and compensation distinct without claiming every sale is nonoperating',()=>{
 render(<STCashReceiptMeaning data={fixture as unknown as STRegimeData}/>)
 const region=screen.getByRole('region',{name:'到账以后怎样判断经营修复'})
 expect(region).toHaveTextContent('全资子公司海泰方圆')
 expect(region).toHaveTextContent('不能把“卖房”一律当成非经营现金')
 expect(region).toHaveTextContent('558,045,315.92元')
 expect(region).toHaveTextContent('售价也不是净利润')
 expect(region).toHaveTextContent('经营现金仍净流出26,215,410.77元')
 expect(region).toHaveTextContent('不认证精确履行比例')
 expect(region).toHaveTextContent('不把差额写成已确认逾期应收')
 expect(screen.getByRole('link',{name:'1225612213 · PDF物理第11页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-10-21/1225612213.PDF#page=11')
})
it.each(['source','chain','missing','compensation','cutoff'])('withholds receipt interpretation when evidence changes: %s',kind=>{
 const d=structuredClone(fixture)
 if(kind==='source')d.themes.thirteenth_period_followup.sources[0].sha256='different'
 if(kind==='chain')d.themes.twentyseventh_period_followup.chains[0].changed='not confirmed'
 if(kind==='missing')d.themes.thirteenth_period_followup.sources=[]
 if(kind==='compensation')d.themes.removal_followup.compensation.total_received_yuan='0'
 if(kind==='cutoff')d.through='2026-11-19'
 expect(cashReceiptMeaningBound(d as unknown as STRegimeData)).toBe(false)
 render(<STCashReceiptMeaning data={d as unknown as STRegimeData}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示旧解释')
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
it('shows only the selected research question and keeps existing market controls reachable',()=>{
 const themes:Record<string,unknown>={}
 for(const source of [stage,fixture,market])for(const [key,value] of Object.entries(source.themes))themes[key]={...(themes[key] as object??{}),...value}
 render(<STCashDirectionComparison data={{through:stage.through,themes} as unknown as STRegimeData}/>)
 expect(screen.getByRole('table',{name:'逐项比较：流向、阶段与证据时点'})).toBeVisible()
 expect(screen.queryByRole('region',{name:'到账以后怎样判断经营修复'})).not.toBeInTheDocument()
 expect(screen.queryByRole('region',{name:'兑现事项与同期行情对照'})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'到账后改变了什么'}))
 expect(screen.getByRole('region',{name:'到账以后怎样判断经营修复'})).toBeVisible()
 expect(screen.queryByRole('table',{name:'逐项比较：流向、阶段与证据时点'})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'随后行情怎样'}))
 expect(screen.getByRole('region',{name:'兑现事项与同期行情对照'})).toBeVisible()
 expect(screen.queryByRole('region',{name:'到账以后怎样判断经营修复'})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'公告日收盘后1个市场交易日'}))
 expect(screen.getByRole('table',{name:'各事项公告日收盘后1个市场交易日的表现'})).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'兑现到了哪一步'}))
 expect(screen.getByRole('table',{name:'逐项比较：流向、阶段与证据时点'})).toBeVisible()
 expect(screen.queryByRole('region',{name:'兑现事项与同期行情对照'})).not.toBeInTheDocument()
})
