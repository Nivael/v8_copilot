import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STQihuanRepaymentCompanion} from './STQihuanRepaymentCompanion'
import type {STRegimeData} from './stRegimeTypes'
import packet from './qihuanRepaymentCompanion.json'
afterEach(cleanup)
const data={content_digest:packet.baseline_snapshot_digest} as STRegimeData
it('separates half-year balances from the later receipt and retains account conflicts',()=>{
 render(<STQihuanRepaymentCompanion data={data}/>);fireEvent.click(screen.getByText('配套公告补强了什么？半年余额为何不等于8月新增欠款？'))
 expect(screen.getByRole('table')).toHaveTextContent('2026年上半年期末')
 expect(screen.getByRole('table')).toHaveTextContent('不是8月28日新增欠款或代偿失败')
 expect(screen.getByText(/没有解释原会计师报告的两处内部冲突/)).toBeVisible()
 expect(screen.getByText(/不能把“本笔占款解决”扩成/)).toBeVisible()
 expect(screen.getByText(/新增科目差异/)).toBeVisible()
 fireEvent.click(screen.getByText('新增原件、核验范围与剩余问题'))
 expect(screen.getAllByRole('link',{name:/物理第/})).toHaveLength(4)
})
it('hides stale baseline evidence',()=>{
 render(<STQihuanRepaymentCompanion data={{...data,content_digest:'changed'}}/>);expect(screen.queryByText(/配套公告补强了什么/)).not.toBeInTheDocument()
})
