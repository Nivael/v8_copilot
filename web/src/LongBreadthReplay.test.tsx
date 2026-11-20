import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {LongBreadthReplay} from './LongBreadthReplay'
import data from './longBreadthReplay.json'
afterEach(cleanup)
it('steps through historical state and distinguishes first signal from continuing weakness',()=>{
 render(<LongBreadthReplay/>);
 const select=screen.getByRole('combobox',{name:'长窗广度观察日'})
 fireEvent.change(select,{target:{value:data.rows.findIndex(r=>r.date==='2026-11-16')}})
 expect(screen.getByRole('region')).toHaveTextContent('今天刚达到')
 expect(screen.getByRole('region')).toHaveTextContent('连续3日')
 fireEvent.click(screen.getByRole('button',{name:'后一交易日'}))
 expect(screen.getByRole('region')).toHaveTextContent('今天不是新的独立提示')
 expect(screen.getByRole('region')).toHaveTextContent('连续4日')
 fireEvent.change(select,{target:{value:0}})
 expect(screen.getByRole('button',{name:'前一交易日'})).toBeDisabled()
 expect(screen.getByRole('region')).toHaveTextContent('不等于实际跌停')
 expect(screen.getByRole('region')).toHaveTextContent('资料在事后取得')
})
it('keeps same-day price windows and early missing history distinct from zero',()=>{
 render(<LongBreadthReplay/>);
 expect(screen.getByRole('complementary',{name:'同日指数价格压力'})).toHaveTextContent('-6.19%')
 expect(screen.getByRole('complementary',{name:'同日指数价格压力'})).toHaveTextContent('-9.68%')
 fireEvent.change(screen.getByRole('combobox',{name:'长窗广度观察日'}),{target:{value:0}})
 const price=screen.getByRole('complementary',{name:'同日指数价格压力'})
 expect(price).toHaveTextContent('2026-07-01')
 expect(price).toHaveTextContent('前序收盘不足，未计算')
 expect(price).not.toHaveTextContent('-9.68%')
 expect(price).toHaveTextContent('不是危机概率')
})
