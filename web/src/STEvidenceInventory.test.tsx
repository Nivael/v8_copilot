import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STEvidenceInventory} from './STEvidenceInventory'
import data from './__fixtures__/evidence-inventory.json'
afterEach(cleanup)
it('distinguishes retained material from reading and links actual outstanding questions',()=>{
 render(<STEvidenceInventory data={data}/>);const table=screen.getByRole('table',{name:'保存范围，不是已读或已验证事实数量'});expect(table).toHaveTextContent('1139');expect(table).toHaveTextContent('157');expect(table).toHaveTextContent('1296');expect(screen.getAllByRole('link',{name:'查看具体问题 →'})).toHaveLength(4);
})
it('searches the deduplicated inventory with bounded pagination',()=>{
 render(<STEvidenceInventory data={data}/>);fireEvent.click(screen.getByText('查找逐文件清单'));const table=screen.getByRole('table',{name:'文件身份与保存范围'});expect(within(table).getAllByRole('row')).toHaveLength(26);fireEvent.click(screen.getByRole('button',{name:'下一页'}));expect(screen.getByText('第2页')).toBeVisible();fireEvent.change(screen.getByRole('textbox'),{target:{value:'1225669888'}});expect(within(table).getAllByRole('row')).toHaveLength(2);expect(screen.getByRole('button',{name:'上一页'})).toBeDisabled();expect(table).toHaveTextContent('非已读页数');
})
