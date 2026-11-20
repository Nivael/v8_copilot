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

it('keeps mirror limitations visible even when the selected title omits them',()=>{
 render(<STEvidenceInventory data={data}/>);fireEvent.click(screen.getByText('查找逐文件清单'));fireEvent.change(screen.getByRole('textbox'),{target:{value:'SINA-'}});const table=screen.getByRole('table',{name:'文件身份与保存范围'});expect(within(table).getAllByRole('row')).toHaveLength(9);expect(within(table).getAllByText('新浪镜像保存件；官方原件字节待补核。')).toHaveLength(8);expect(within(table).getAllByText('核对文件身份')).toHaveLength(8);
})
it('exposes the exact saved identity without inferring official verification from a hash',()=>{
 render(<STEvidenceInventory data={data}/>);fireEvent.click(screen.getByText('查找逐文件清单'));fireEvent.change(screen.getByRole('textbox'),{target:{value:'1225669888'}});fireEvent.click(screen.getByText('核对文件身份'));const entry=data.documents.find(d=>d.announcement_id==='1225669888')!;expect(screen.getByText('保存文件摘要（SHA-256）：'+entry.sha256)).toBeVisible();expect(screen.getByText('摘要用于区分保存文件，不单独证明来源官方、正文完整或已经人工核读。')).toBeVisible();expect(screen.queryByText('新浪镜像保存件；官方原件字节待补核。')).not.toBeInTheDocument();
})
