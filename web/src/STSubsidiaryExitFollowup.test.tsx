import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STSubsidiaryExitFollowup} from './STSubsidiaryExitFollowup'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
const data={content_digest:'e0ed59aa8cc346fc45349f5daac23d091211c82c145b91c38d031e47579e612f'} as STRegimeData
it('separates the two legal entities, dates and unpaid investment from receipts',()=>{
 render(<STSubsidiaryExitFollowup data={data}/>);
 fireEvent.click(screen.getByText('子公司、退出与投资终止：7份正文分别说明什么？'))
 expect(screen.getByText(/都不能替代上市公司自身的程序状态/)).toBeVisible()
 expect(screen.getByText(/6365.49万元占用余额为2025年末/)).toBeVisible()
 expect(screen.getByText(/三份倒计时不增加三次退出案例/)).toBeVisible()
 expect(screen.getByText(/没有因此形成已付款或退款/)).toBeVisible()
})
it('limits the reading to the selected company and hides stale bindings',()=>{
 const {rerender}=render(<STSubsidiaryExitFollowup data={data} symbol="002175"/>);
 expect(screen.queryByText(/参股公司宣告破产/)).not.toBeInTheDocument()
 expect(screen.getByText(/终止500万元拟投资/)).toBeInTheDocument()
 rerender(<STSubsidiaryExitFollowup data={{...data,content_digest:'changed'}}/>);
 expect(screen.queryByText(/终止500万元拟投资/)).not.toBeInTheDocument()
})
