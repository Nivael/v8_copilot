import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STNingkeComparativeFollowup} from './STNingkeComparativeFollowup'
import data from './__fixtures__/ningke-comparative-followup.json'
afterEach(cleanup)
it('shows both original bases and distinguishes corroboration from correction',()=>{
 render(<STNingkeComparativeFollowup data={data}/>);expect(screen.getByText(data.answer)).toHaveTextContent('未解释差异');
 fireEvent.click(screen.getByText('并列查看主要指标页、合并表与年度审计原数'));
 const table=screen.getByRole('table',{name:/均为人民币元/});expect(table).toHaveTextContent('-99,206,789.77元');expect(table).toHaveTextContent('1,207,946,343.83元');expect(table).toHaveTextContent('71,793,481.04元');
 fireEvent.click(screen.getByText('同一个半年末数，换比较基数后意味着什么？'));expect(screen.getByRole('table',{name:/本轮算术复算/})).toHaveTextContent('-132,468,807.22元');
})
it('links physical PDF pages and identifies visual transcription rather than extracted text',()=>{
 render(<STNingkeComparativeFollowup data={data}/>);fireEvent.click(screen.getByText('原页、扫描读数与核验限制'));
 expect(screen.getByText(data.annual_source_reading)).toHaveTextContent('自动文本提取为空');expect(screen.getByRole('link',{name:'PDF第7页'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-04-24/1225172303.PDF#page=7');expect(screen.getAllByRole('link')).toHaveLength(6);
})
