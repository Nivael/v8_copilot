import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {STIndexCrosscheck} from './STIndexCrosscheck'
import type {RegimeIndexCrosscheck} from './stRegimeTypes'
const data:RegimeIndexCrosscheck={start:'2026-05-06',through:'2026-11-06',index_count:2,unique_index_dates:252,quote_points:378,precision_difference_count:1,all_window_directions_unchanged:true,max_window_difference_pp:.000239,boundary:'不同渠道不证明底层独立。',identity_sources:[],rows:[{symbol:'932000',name:'中证2000',vendor:'eastmoney',observations:126,exact_points:3,rounding_agree_points:125,precision_difference_count:1,max_close_difference_points:.0055,max_daily_difference_pp:.000302,max_window_difference_pp:.000239,precision_differences:[{date:'2026-07-21',original_close:2821.8145,checked_close:2821.82,difference_points:.0055}],environment_boundary_changes:[],windows:[{key:'all',phase:'after',anchor:'2026-07-03',through:'2026-11-06',days:84,original_pct:-20,checked_pct:-20.000239,difference_pp:-.000239}],source:{url:'https://push2his.eastmoney.com/example',sha256:'a'.repeat(64),observed_at:'2026-11-09T00:00:00Z'}}]}
afterEach(cleanup)
it('先说明解释是否改变，精确差异和原渠道证据按需展开',()=>{
 render(<STIndexCrosscheck data={data}/>);
 expect(screen.getByRole('heading',{name:'换一条报价渠道，所核涨跌与强弱方向未变'})).toBeVisible()
 expect(screen.getByText('2821.8145')).not.toBeVisible()
 fireEvent.click(screen.getByText('看核对范围、窗口与保留的差异'))
 expect(screen.getByText('2821.8145')).toBeVisible()
 expect(screen.getByText('2821.82')).toBeVisible()
 expect(screen.getByRole('link',{name:'查看东方财富日线响应 ↗'})).toHaveAttribute('href',data.rows[0].source.url)
})
it('日期分类出现变化时不能仍然给出未改变结论',()=>{
 render(<STIndexCrosscheck data={{...data,rows:[{...data.rows[0],environment_boundary_changes:[{date:'2026-07-21',original_pct:-1.00001,checked_pct:-.9999}]}]}}/>);
 expect(screen.getByRole('heading',{name:'报价核对出现差异，市场解释需要复核'})).toBeVisible()
})
it('未采集时不显示已核实',()=>{render(<STIndexCrosscheck data={null}/>);expect(screen.queryByRole('region',{name:'指数行情交叉核对'})).not.toBeInTheDocument()})
