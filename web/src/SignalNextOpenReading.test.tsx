import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {SignalNextOpenReading} from './SignalNextOpenReading'
import data from './signalNextOpenReading.json'
const original=data.signal_evidence_sha256
afterEach(()=>{cleanup();data.signal_evidence_sha256=original})
it('keeps the five quoted cases separate from ST groups and order execution',()=>{
 render(<SignalNextOpenReading/>);fireEvent.click(screen.getByText('11月16日提示后，五只跟踪比较股次日开盘怎样？'))
 const r=screen.getByRole('region',{name:'提示后下一开盘核对'})
 expect(within(r).getAllByRole('row')).toHaveLength(6)
 expect(r).toHaveTextContent('600363.SH')
 expect(r).toHaveTextContent('141/142只成交报价配对，开盘在下限1只，收盘在下限10只')
 expect(r).toHaveTextContent('147/150只成交报价配对')
 expect(r).toHaveTextContent('其余五次的下一开盘未核')
 expect(r).toHaveTextContent('思科瑞为科创板')
 expect(r).toHaveTextContent('相对当日行情给出的前收参考')
 expect(r).toHaveTextContent('开盘和实际限价仍为供应商记录')
 expect(r).toHaveTextContent('不能证明你的委托一定能成交')
})
it('rejects another signal-source binding',()=>{
 data.signal_evidence_sha256='changed';render(<SignalNextOpenReading/>);
 expect(screen.getByRole('status')).toHaveTextContent('暂不展示')
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
