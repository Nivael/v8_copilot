import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STFixedNov20} from './STFixedNov20'
import packet from './stFixedNov20.json'
afterEach(cleanup)
it('compares the fixed traded subset with the same-day market without calling it the current ST roster',()=>{
 render(<STFixedNov20 priceAsOf="2026-11-20" priceDigest={packet.benchmark_source_digest}/>);fireEvent.click(screen.getByText('11月20日，固定ST旧样本是否跟着大盘下跌？'))
 expect(screen.getByText(/固定7月3日的150只旧样本中/)).toHaveTextContent('24只上涨、115只下跌、7只平盘')
 expect(screen.getByRole('table',{name:'2026-11-19收盘至2026-11-20收盘；固定旧样本与大盘'})).toHaveTextContent('-2.38%')
 expect(screen.getByRole('table',{name:'2026-11-19收盘至2026-11-20收盘；固定旧样本与大盘'})).toHaveTextContent('-2.60%')
 expect(screen.getByRole('table',{name:'2026-11-19收盘至2026-11-20收盘；固定旧样本与大盘'})).toHaveTextContent('-2.71%')
 expect(screen.getByText(/不能用一天的相对少跌/)).toHaveTextContent('0.33个百分点')
 fireEvent.click(screen.getByText('四只缺口、配对规则与来源'))
 expect(screen.getByRole('table',{name:'150只都保留；以下不填零收益'})).toHaveTextContent('康佳000016.SZ')
 expect(screen.getByRole('table',{name:'150只都保留；以下不填零收益'})).toHaveTextContent('汇洲002122.SZ')
})
it('does not attach a frozen one-day comparison to another benchmark date or source',()=>{
 const {rerender}=render(<STFixedNov20 priceAsOf="2026-11-19" priceDigest={packet.benchmark_source_digest}/>)
 expect(screen.queryByText('11月20日，固定ST旧样本是否跟着大盘下跌？')).not.toBeInTheDocument()
 rerender(<STFixedNov20 priceAsOf="2026-11-20" priceDigest="changed"/>)
 expect(screen.queryByText('11月20日，固定ST旧样本是否跟着大盘下跌？')).not.toBeInTheDocument()
})
