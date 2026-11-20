import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STCaseOHLCCrosscheck} from './STCaseOHLCCrosscheck'
afterEach(cleanup)
it('separates three diverging close observations from official OHLC or whole-cohort advancement',()=>{
 render(<STCaseOHLCCrosscheck/>);fireEvent.click(screen.getByText('瑞茂、华幸、东珠：跨渠道核价后，20日有什么不同？'))
 const t=screen.getByRole('table')
 expect(t).toHaveTextContent('*ST瑞茂600180.SH0.610／0.550元')
 expect(t).toHaveTextContent('*ST华幸600340.SH0.770／0.850元')
 expect(t).toHaveTextContent('*ST东珠603359.SH0.890／0.860元')
 expect(screen.getByText(/三家九日共108个/)).toHaveTextContent('30个收盘价')
 expect(screen.getByText(/不是复权收益或公告净影响/)).toBeVisible()
 fireEvent.click(screen.getByText('三家分别核了哪些字段与来源？'))
 expect(screen.getAllByText(/20日实际下限价未补入/)).toHaveLength(3)
 expect(screen.getAllByRole('link',{name:/上交所收盘控制/})).toHaveLength(3)
})
