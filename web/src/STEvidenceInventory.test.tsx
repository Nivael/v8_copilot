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
 render(<STEvidenceInventory data={data}/>);fireEvent.click(screen.getByText('查找逐文件清单'));fireEvent.change(screen.getByRole('textbox'),{target:{value:'SINA-'}});const table=screen.getByRole('table',{name:'文件身份与保存范围'});expect(within(table).getAllByRole('row')).toHaveLength(9);expect(within(table).getAllByText('新浪镜像保存件；官方原件字节待补核。')).toHaveLength(7);expect(within(table).getAllByText('核对文件身份')).toHaveLength(8);
})
it('exposes the exact saved identity without inferring official verification from a hash',()=>{
 render(<STEvidenceInventory data={data}/>);fireEvent.click(screen.getByText('查找逐文件清单'));fireEvent.change(screen.getByRole('textbox'),{target:{value:'1225669888'}});fireEvent.click(screen.getByText('核对文件身份'));const entry=data.documents.find(d=>d.announcement_id==='1225669888')!;expect(screen.getByText('保存文件摘要（SHA-256）：'+entry.sha256)).toBeVisible();expect(screen.getByText('摘要用于区分保存文件，不单独证明来源官方、正文完整或已经人工核读。')).toBeVisible();expect(screen.queryByText('新浪镜像保存件；官方原件字节待补核。')).not.toBeInTheDocument();
})
it('adds later official confirmation only to the exact mirror while keeping the original debt',()=>{
 render(<STEvidenceInventory data={data}/>);
 fireEvent.click(screen.getByText('查找逐文件清单'));
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'SINA-12361633'}});
 fireEvent.click(screen.getByText('后来官方报告是否确认了实施日期？'));
 expect(screen.getByText(/2026-08-27披露/)).toHaveTextContent('2026-06-02');
 expect(screen.getByText('新浪镜像保存件；官方原件字节待补核。')).toBeVisible();
 expect(screen.getByRole('link',{name:'官方半年报第19页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-08-27/1225508648.PDF#page=19');
})
it('does not attach a later report to a replaced mirror identity',()=>{
 const changed={...data,documents:data.documents.map(d=>d.announcement_id==='SINA-12361633'?{...d,sha256:'changed'}:d)};
 render(<STEvidenceInventory data={changed}/>);
 fireEvent.click(screen.getByText('查找逐文件清单'));
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'SINA-12361633'}});
 expect(screen.queryByText('后来官方报告是否确认了实施日期？')).not.toBeInTheDocument();
})

it('recovers only the exact Huawei mirror identity and leaves other debts intact',()=>{
 render(<STEvidenceInventory data={data}/>);fireEvent.click(screen.getByText('查找逐文件清单'));
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'SINA-12649852'}});
 expect(screen.getByText(/原新浪镜像保留；已补官方原件/)).toBeVisible();
 expect(screen.queryByText('新浪镜像保存件；官方原件字节待补核。')).not.toBeInTheDocument();
 expect(screen.getByRole('link',{name:'官方实施公告 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-10-21/1225611990.PDF');
})
