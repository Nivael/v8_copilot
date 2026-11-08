import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STRemovalCohort} from './STRemovalCohort'
import fixture from './__fixtures__/removal-cohort.json'
afterEach(cleanup)
it('answers the cohort question with a paired denominator and retains the unfinished rows',()=>{
 render(<STRemovalCohort data={fixture}/>)
 expect(screen.getByRole('img',{name:'前20日：5涨、5跌、0平'})).toBeVisible()
 expect(screen.getByRole('img',{name:'后20日：6涨、4跌、0平'})).toBeVisible()
 expect(screen.getByText(/不是全部ST的摘帽成功率/)).toBeVisible()
 fireEvent.click(screen.getByText('展开12只对照、缺窗与日期依据'))
 expect(screen.getByRole('rowheader',{name:/四通股份/})).toBeVisible()
 expect(screen.getByRole('rowheader',{name:/绝味食品/})).toBeVisible()
 expect(screen.getAllByRole('cell',{name:/后窗未满/})).toHaveLength(2)
 expect(screen.getByText(/10家公司只对应7组日期窗口/)).toBeVisible()
 expect(screen.getByText(/45对公司中27对/)).toBeVisible()
})
it('changes horizon without inventing zero outcomes or certifying conflicting adjusted data',()=>{
 render(<STRemovalCohort data={fixture}/>)
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'5'}})
 expect(screen.getByRole('img',{name:'后5日：4涨、7跌、0平'})).toBeVisible()
 fireEvent.click(screen.getByText('展开12只对照、缺窗与日期依据'))
 expect(screen.getByRole('cell',{name:'复权端点差异待核'})).toBeVisible()
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'40'}})
 expect(screen.getByRole('img',{name:'后40日：4涨、6跌、0平'})).toBeVisible()
 fireEvent.click(screen.getByText('核报价覆盖、绝味复权差异与其他退出样本'))
 expect(screen.getByText(/绝味食品有100个历史日期/)).toBeVisible()
 expect(screen.getByText(/只取得腾讯一个报价渠道/)).toBeVisible()
 expect(screen.getByText(/另外2个并非摘帽/)).toBeVisible()
})
it('does not invent a cohort comparison in an old snapshot',()=>{const {container}=render(<STRemovalCohort data={null}/>);expect(container).toBeEmptyDOMElement()})
