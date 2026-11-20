import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STTwentyseventhPeriodFollowup,type TwentyseventhPeriodFollowup} from './STTwentyseventhPeriodFollowup'
import fixture from './__fixtures__/twentyseventh-period-followup.json'
afterEach(cleanup)
it('shows cross-company market context before individual evidence',()=>{
 render(<STTwentyseventhPeriodFollowup data={fixture as TwentyseventhPeriodFollowup}/>);
 const region=screen.getByRole('region',{name:'四家事项前后同窗对照'});
 expect(within(region).getByText('-18.53%')).toBeInTheDocument();expect(within(region).getByText('+2.35%')).toBeInTheDocument();
 expect(screen.getByText(/金鸿顺利润增长包含减值转回/)).toBeInTheDocument();
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603959'}});
 expect(screen.getByRole('heading',{name:'1.3亿元赠与，钱到了多少？'})).toBeInTheDocument();
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:'603959-更正以后，第三季度亏损该怎样比较？'}});
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'));
 expect(screen.getByText(/报告单季-128830967.14元；累计减半年-128830967.13元/)).toBeInTheDocument();
 expect(screen.getByText(/百利更正半年扣非缺直接披露值/)).toBeInTheDocument();
})
it('keeps unfinished observations explicit and preserves source links',()=>{
 render(<STTwentyseventhPeriodFollowup data={fixture as TwentyseventhPeriodFollowup}/>);
 fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'));
 fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'20'}});
 expect(screen.getByText(/未满20个市场日，目前/)).toBeInTheDocument();
 expect(screen.getByRole('link',{name:/金鸿顺关于全资子公司北京金鸿顺涉及诉讼的进展公告 · 第1页/})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-11-11/1225664823.PDF#page=1');
})
