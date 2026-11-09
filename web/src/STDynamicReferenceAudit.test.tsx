import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STDynamicReferenceAudit} from './STDynamicReferenceAudit'
import type {RegimeDynamicReferenceAudit} from './stRegimeTypes'
import raw from './__fixtures__/dynamic-reference-audit.json'
const data=raw as RegimeDynamicReferenceAudit
afterEach(cleanup)
describe('动态ST线平行核验',()=>{
 it('先解释动态203和固定150不同，不声称名单独立认证',()=>{render(<STDynamicReferenceAudit data={data}/>);expect(screen.getByRole('heading',{name:'这条ST参考线，按当时哪些股票核过？'})).toBeVisible();expect(screen.getByText(/还需核47只前窗成员.*203家公司/)).toBeVisible();expect(screen.getByText(/19,009次实际成交贡献/)).toBeVisible();expect(screen.getByText(/不等于官方全名单已获逐日独立认证/)).toBeVisible()})
 it('原线与平行线同窗对照按需展开',()=>{render(<STDynamicReferenceAudit data={data}/>);fireEvent.click(screen.getByText('看制度前后与大盘的同窗对照'));expect(screen.getAllByText('-10.93%')).toHaveLength(2);expect(screen.getByText(/这是联动程度，不是大盘/)).toBeVisible();expect(screen.getByText(/原线0.549，平行线0.549/)).toBeVisible()})
 it('万方空序列与萃华复牌参考额分开，不补造前成交日期',()=>{render(<STDynamicReferenceAudit data={data}/>);fireEvent.click(screen.getByText('核六只新增成员与两种特殊边界'));expect(screen.getByText(/名单内20日均停牌/)).toBeVisible();expect(screen.getByText(/参考价4.35元.*没有因此认证前次实际成交的日期/)).toBeVisible();expect(screen.getByText(/向前补查两次/)).toBeVisible();expect(screen.getByText(/不称作历史第一次ST/)).toBeVisible()})
 it('来源与676次微小差异不冒充案例数',()=>{render(<STDynamicReferenceAudit data={data}/>);fireEvent.click(screen.getByText('看报价来源、细小差异和未完成范围'));expect(screen.getByText(/676次.*不是独立案例数/)).toBeVisible();fireEvent.change(screen.getByLabelText('动态核价公司'),{target:{value:'002592'}});expect(screen.getAllByRole('link',{name:/原请求地址/})).toHaveLength(2);expect(screen.getByText(/原日参考口径\+8.46%，直接复权比值\+8.60%/)).toBeVisible()})
 it('旧快照没有虚构核验',()=>{expect(render(<STDynamicReferenceAudit data={null}/>).container).toBeEmptyDOMElement()})
})
