import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STExitQuoteReplay} from './STExitQuoteReplay'
import {STFixedQuoteAudit} from './STFixedQuoteAudit'
import {STRemainingBasis} from './STRemainingBasis'
import type {RegimeExitQuoteReplay,RegimeFixedQuoteAudit,RegimeRemainingBasis} from './stRegimeTypes'
import raw from './__fixtures__/exit-quote-replay.json'
import audit from './__fixtures__/exit-quote-audit.json'
import basis from './__fixtures__/remaining-basis.json'
const data=raw as RegimeExitQuoteReplay
const quote=audit as RegimeFixedQuoteAudit
afterEach(cleanup)
describe('退出报价原字节重放',()=>{
 it('先解释完整区间仍缺端点，退出不等收益零',()=>{render(<STExitQuoteReplay data={data}/>);expect(screen.getByRole('heading',{name:'退出样本核回来了，哪些比较要更新？'})).toBeVisible();expect(screen.getByText(/退出不等于收益为零/)).toBeVisible();expect(screen.getByText(/仍只有146只/)).toBeVisible();expect(screen.getByText('摘牌后无成交')).toBeVisible();expect(screen.getAllByText('缺实际成交端点')).toHaveLength(2)})
 it('短窗变化按需展开，前后同组',()=>{render(<STExitQuoteReplay data={data}/>);expect(screen.getByText('147→148')).not.toBeVisible();fireEvent.click(screen.getByText('看哪些短窗口变化，以及为什么'));expect(screen.getByText('147→148')).toBeVisible();expect(screen.getAllByText('146→147')).toHaveLength(2);expect(screen.getByText(/变化来自覆盖范围补全/)).toBeVisible()})
 it('八个旧请求地址保留取得时间，不说重新请求',()=>{render(<STExitQuoteReplay data={data}/>);fireEvent.click(screen.getByText('核对旧响应、退出原因与剩余限制'));expect(screen.getAllByRole('link')).toHaveLength(8);expect(screen.getByText(/8份旧响应、532个报价口径点/)).toBeVisible();expect(screen.getAllByText(/原取得时间/)).toHaveLength(8)})
 it('固定核价两退出样本显示缺端点而非未重放',()=>{render(<STFixedQuoteAudit data={quote}/>);fireEvent.change(screen.getByLabelText('固定样本核价范围'),{target:{value:'prior'}});expect(screen.getAllByText('无共同成交端点')).toHaveLength(4);expect(screen.queryByRole('cell',{name:'本轮未重放'})).not.toBeInTheDocument();expect(screen.getByText(/原字节已重放/)).toBeVisible();fireEvent.change(screen.getByLabelText('固定样本核价窗口'),{target:{value:'5'}});expect(screen.getAllByText('117/148')).toHaveLength(2);expect(screen.getAllByText('-12.00%')).toHaveLength(2)})
 it('旧复权页不继续把退出重放列作待办',()=>{render(<STRemainingBasis data={basis as RegimeRemainingBasis} exitReplayed/>);fireEvent.click(screen.getByText('这轮新增、复用与剩余范围'));expect(screen.getByText(/两只退出样本原字节已在后续一轮重放/)).toBeVisible()})
 it('旧快照不虚构重放',()=>{expect(render(<STExitQuoteReplay data={null}/>).container).toBeEmptyDOMElement()})
})
