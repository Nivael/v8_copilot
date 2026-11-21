import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STCatalogResolutionAudit} from './STCatalogResolutionAudit'
import type {STRegimeData} from './stRegimeTypes'
import packet from './catalogResolutionAudit.json'
afterEach(cleanup)
const data={content_digest:packet.baseline_snapshot_digest} as STRegimeData
it('does not turn an exhausted title queue into a no-omission or independent-case claim',()=>{
 render(<STCatalogResolutionAudit data={data}/>);fireEvent.click(screen.getByText('补上“占款解决完毕”规则后，还有新漏选标题吗？'))
 expect(screen.getByText(/不等于所有公告已读或零遗漏/)).toBeVisible()
 expect(screen.getByText(/150家253页/)).toBeVisible()
 fireEvent.click(screen.getByText('查看新旧规则差集、范围与来源'))
 expect(screen.getByText(/已选源身份只是文件身份/)).toBeVisible()
 expect(screen.getByText(/5593条去重ID为混合起点/)).toBeVisible()
 expect(screen.getByRole('link',{name:/关于资金占用事项解决完毕/})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-08-26/1225504694.PDF')
})
it('does not display the old audit on changed input',()=>{
 render(<STCatalogResolutionAudit data={{...data,content_digest:'changed'}}/>);expect(screen.queryByText(/补上“占款/)).not.toBeInTheDocument()
})
