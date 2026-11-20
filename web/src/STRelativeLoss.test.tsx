import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STRelativeLoss,relativeLossRows} from './STRelativeLoss'
import data from './__fixtures__/market-stage-experience.json'
import type {MarketStageExperience} from './stRegimeTypes'
afterEach(cleanup)
it('keeps absolute loss distinct from relative outperformance in all five intervals',()=>{
 expect(relativeLossRows(data)?.map(r=>[r.losses,r.beats,r.beatButLoss])).toEqual([[118,89,68],[17,85,0],[83,91,35],[132,57,50],[110,33,4]])
 render(<STRelativeLoss data={data}/>);fireEvent.click(screen.getByText('跑赢大盘的股票，有多少仍在跌？'))
 expect(screen.getByRole('table')).toHaveTextContent('68／89家')
 expect(screen.getByText(/不算五次独立验证/)).toBeVisible()
})
it('refuses to turn missing certified prices or duplicate members into zero returns',()=>{
 const missing:MarketStageExperience=structuredClone(data);missing.stages[0].rows.find(r=>missing.stages[0].common_sample.symbols.includes(r.symbol))!.certified_return_pct=null
 expect(relativeLossRows(missing)).toBeNull()
 const duplicate:MarketStageExperience=structuredClone(data);duplicate.stages[0].rows.push(duplicate.stages[0].rows.find(r=>duplicate.stages[0].common_sample.symbols.includes(r.symbol))!)
 expect(relativeLossRows(duplicate)).toBeNull()
})
it('counts ties and flat returns separately from strict wins and losses',()=>{
 const example:MarketStageExperience=structuredClone(data);example.stages=[example.stages[0]];example.common_verified_members=3
 const stage=example.stages[0];stage.market_pct='-1';stage.common_sample.symbols=['a','b','c'];stage.rows=stage.rows.slice(0,3).map((r,i)=>({...r,symbol:['a','b','c'][i],certified_return_pct:['-1','0','-0.5'][i]}))
 expect(relativeLossRows(example)?.map(r=>[r.losses,r.beats,r.beatButLoss])).toEqual([[2,2,1]])
})

it('rejects different membership across intervals even when counts match',()=>{
 const changed:MarketStageExperience=structuredClone(data)
 const stage=changed.stages[1];const outside=stage.rows.find(r=>!stage.common_sample.symbols.includes(r.symbol))!
 stage.common_sample.symbols[0]=outside.symbol
 expect(relativeLossRows(changed)).toBeNull()
})
