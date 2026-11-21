import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {SignalNextOpenReading} from './SignalNextOpenReading'
import data from './signalNextOpenReading.json'
const original=data.signal_evidence_sha256
afterEach(()=>{cleanup();data.signal_evidence_sha256=original})
it('keeps the five quoted cases separate from ST groups and order execution',()=>{
 render(<SignalNextOpenReading/>);fireEvent.click(screen.getByText('六次提示后，五只跟踪比较股的开盘怎样？'))
 const r=screen.getByRole('region',{name:'提示后下一开盘核对'})
 expect(within(r).getAllByRole('row')).toHaveLength(6)
 expect(r).toHaveTextContent('600363.SH')
 expect(r).toHaveTextContent('141/142只成交报价配对，开盘在下限1只，收盘在下限10只')
 expect(r).toHaveTextContent('147/150只成交报价配对')
 expect(r).toHaveTextContent('早期五次共25个报价位置经两渠道核同')
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

it('switches to the earlier raw quote day without inheriting Nov17 group counts',()=>{
 render(<SignalNextOpenReading/>);fireEvent.click(screen.getByText('六次提示后，五只跟踪比较股的开盘怎样？'));
 fireEvent.change(screen.getByRole('combobox',{name:'提示后开盘观察日'}),{target:{value:'2026-07-09'}});
 const r=screen.getByRole('region',{name:'提示后下一开盘核对'});
 expect(within(r).getAllByRole('row')).toHaveLength(6);
 expect(r).toHaveTextContent('14.7');expect(r).toHaveTextContent('1.93');
 expect(r).toHaveTextContent('13.19');expect(r).not.toHaveTextContent('141/142');
 expect(r).toHaveTextContent('当前简称不回填当时ST身份');
 expect(r).toHaveTextContent('并与保存的逐股实际限价配对');
});

it('separates July21 intraday touch, closing limit and opening loss',()=>{
 render(<SignalNextOpenReading/>);fireEvent.click(screen.getByText('六次提示后，五只跟踪比较股的开盘怎样？'));
 fireEvent.change(screen.getByRole('combobox',{name:'提示后开盘观察日'}),{target:{value:'2026-07-21'}});
 const r=screen.getByRole('region',{name:'提示后下一开盘核对'});
 expect(r).toHaveTextContent('7.96%');
 expect(r).toHaveTextContent('触及且收盘仍在下限');
 expect(r).toHaveTextContent('盘中触及，收盘离开');
 expect(r).toHaveTextContent('未取得独立交易所限价原件');
 expect(r).not.toHaveTextContent('本次未核');
});
