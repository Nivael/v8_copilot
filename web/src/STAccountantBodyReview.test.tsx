import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STAccountantBodyReview} from './STAccountantBodyReview'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
const data={content_digest:'e0ed59aa8cc346fc45349f5daac23d091211c82c145b91c38d031e47579e612f'} as STRegimeData
it('keeps repayment nature and internal contradictions visible in the answer',()=>{
 render(<STAccountantBodyReview data={data}/>);fireEvent.click(screen.getByText('会计师材料怎样更新清偿判断？'))
 expect(screen.getByText(/历史累计含债权抵偿/)).toBeVisible()
 expect(screen.getByLabelText('原文冲突仍待解释')).toBeVisible()
 expect(screen.getByText(/签章日期8月25日早于/)).toBeVisible()
 expect(screen.getByText(/第2页称截至报告日/)).toBeVisible()
})
it('filters company sources and hides a changed baseline',()=>{
 const {rerender}=render(<STAccountantBodyReview data={data} symbol="000752"/>);
 expect(screen.queryByText(/启环：报告称/)).not.toBeInTheDocument()
 fireEvent.click(screen.getByText('会计师材料怎样更新清偿判断？ · 000752'))
 fireEvent.click(screen.getByText('日期、核验范围与原件 · 000752'))
 expect(screen.getAllByRole('link',{name:/物理第/})).toHaveLength(4)
 rerender(<STAccountantBodyReview data={{...data,content_digest:'changed'}}/>);
 expect(screen.queryByText(/西发：清偿/)).not.toBeInTheDocument()
})
