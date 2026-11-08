import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STSampleIntegrity} from './STSampleIntegrity'
import type {RegimeSampleIntegrity} from './stRegimeTypes'
const source={title:'终止上市决定公告',page:2,url:'https://example.com/primary.pdf#page=2',sha256:'a'.repeat(64)}
const data:RegimeSampleIntegrity={through:'2026-11-06',boundary:'仅核两家公司，不代表全部样本。',cases:[{symbol:'002731',classification:'anchor_suspended',title:'萃华：缺的是比较起点',explanation:'期末有0.22元报价，但起点处于停牌，不能改用复牌价。',as_of:'2026-11-06',boundary:'仍在整理期，不能写成已摘牌。',anchor:{date:'2026-07-03',close:null},endpoint:{date:'2026-11-06',close:.22},last_trade:{date:'2026-11-06',close:.22},matched_trade_dates:51,facts:[{published_on:'2026-10-16',occurred_on:'2026-10-15',text:'7月3日仍在停牌。',source}]}]}
afterEach(cleanup)
describe('固定样本缺口解释',()=>{
 it('区分缺起点与有期末报价，保留原样本和统计范围',()=>{
  render(<STSampleIntegrity data={data} total={150} covered={148}/>)
  expect(screen.getByText(/统计仍是148只有可用端点/)).toBeVisible()
  expect(screen.getByText('没有交易收盘价')).toBeVisible()
  expect(screen.getByText('期末有0.22元报价，但起点处于停牌，不能改用复牌价。')).toBeVisible()
  expect(screen.queryByText('-100.00%')).not.toBeInTheDocument()
  fireEvent.click(screen.getByText('沿公告核对状态与原件'))
  expect(screen.getByRole('link',{name:/终止上市决定公告/})).toHaveAttribute('href',source.url)
 })
 it('没有核实资料时不显示确定性退出解释',()=>{
  render(<STSampleIntegrity data={null} total={150} covered={148}/>)
  expect(screen.queryByRole('region',{name:'固定样本缺口原因'})).not.toBeInTheDocument()
 })
})
