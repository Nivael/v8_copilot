import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {DailyMarketLimitPressure} from './DailyMarketLimitPressure'
afterEach(cleanup)
it('uses all traded ordinary A shares and keeps overlapping states separate',()=>{
 render(<DailyMarketLimitPressure day="2026-11-17" trading={5217}/>);
 expect(screen.getByRole('table')).toHaveTextContent('84只')
 expect(screen.getByRole('table')).toHaveTextContent('1.61%')
 expect(screen.getByRole('table')).toHaveTextContent('109只')
 expect(screen.getByRole('complementary')).toHaveTextContent('ST样本与市场重叠')
})
it('uses separately replayed Nov20 counts and explains source change',()=>{
 render(<DailyMarketLimitPressure day="2026-11-20" trading={5216}/>);
 expect(screen.getByRole('table')).toHaveTextContent('68只')
 expect(screen.getByRole('table')).toHaveTextContent('107只')
 expect(screen.getByRole('table')).toHaveTextContent('3只')
 expect(screen.getByRole('complementary')).toHaveTextContent('不足以认定整体风险缓和')
 expect(screen.getByRole('complementary')).toHaveTextContent('腾讯公开报价')
})
it('withholds combined counts on a different breadth denominator',()=>{
 render(<DailyMarketLimitPressure day="2026-11-17" trading={1}/>);
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
 expect(screen.getByRole('status')).toHaveTextContent('暂不合并展示')
})

it('keeps an earlier uncovered date unknown',()=>{
 render(<DailyMarketLimitPressure day="2026-07-13" trading={5197}/>);
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
 expect(screen.getByRole('complementary')).toHaveTextContent('保留未知')
})
it('withholds Nov20 counts on mismatched denominator',()=>{
 render(<DailyMarketLimitPressure day="2026-11-20" trading={5217}/>);
 expect(screen.getByRole('status')).toHaveTextContent('暂不合并展示')
})
