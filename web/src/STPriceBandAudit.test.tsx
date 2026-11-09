import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {STPriceBandAudit} from './STPriceBandAudit'
import type {PriceBandAudit} from './STPriceBandAudit'
import raw from './__fixtures__/price-band-audit.json'
const data=raw as unknown as PriceBandAudit
afterEach(cleanup)
it('默认直答，分开旧边界与现行涨跌停且说明时长',()=>{render(<STPriceBandAudit data={data}/>);expect(screen.getByRole('heading',{name:'涨过5%，就突破旧涨停了吗？'})).toBeVisible();expect(screen.getByText(/1240\/12099.*10.25%.*346.*2.86%/)).toBeVisible();expect(screen.getByText(/完整覆盖前后时长不同/)).toBeVisible()})
it('20和40日使用各自同窗分母',()=>{render(<STPriceBandAudit data={data}/>);fireEvent.change(screen.getByLabelText('价格边界核对窗口'),{target:{value:'20'}});expect(screen.getByText(/544\/2958/)).toBeVisible();fireEvent.change(screen.getByLabelText('价格边界核对窗口'),{target:{value:'40'}});expect(screen.getByText(/780\/5878/)).toBeVisible()})
it('案例按需展开，保留京机冲突和发行人镜像层级',()=>{render(<STPriceBandAudit data={data}/>);fireEvent.click(screen.getByText('用具体案例理解：取整、除权参考价与摘帽'));expect(screen.getByText(/完整前段共 821/)).toBeVisible();fireEvent.change(screen.getByLabelText('价格边界案例类型'),{target:{value:'reference'}});expect(screen.getByText('原件算式冲突仍未解决')).toBeVisible();expect(screen.getByText('发行人PDF镜像；官方原字节待补')).toBeVisible();fireEvent.click(screen.getByText('同名接口字段也不能直接互换：8处数值差异、6处空值'));expect(screen.getAllByText(/空值/).length).toBeGreaterThan(2)})
it('摘帽后复牌不混入当日ST池',()=>{render(<STPriceBandAudit data={data}/>);fireEvent.click(screen.getByText('用具体案例理解：取整、除权参考价与摘帽'));fireEvent.change(screen.getByLabelText('价格边界案例类型'),{target:{value:'former'}});expect(screen.getByText(/37次摘帽复牌中，16次.*全部不在当天ST分母/)).toBeVisible()})
it('旧快照不显示新认证',()=>{const {container}=render(<STPriceBandAudit/>);expect(container).toBeEmptyDOMElement()})
