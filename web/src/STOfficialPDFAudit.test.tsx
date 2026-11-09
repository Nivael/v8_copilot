import {originalSourceTitle} from './officialSourceTitle'
import {afterEach,describe,it,expect} from 'vitest'
import {render,screen,cleanup,fireEvent} from '@testing-library/react'
import {STOfficialPDFAudit,OfficialCopyLink} from './STOfficialPDFAudit'
import type {OfficialPDFAudit} from './STOfficialPDFAudit'
import fixture from './__fixtures__/official-pdf-audit.json'
const data=fixture as OfficialPDFAudit
afterEach(cleanup)
describe('Official PDF copies',()=>{
 it('distinguishes official copy from failed exchange direct URLs and keeps provenance',()=>{
  render(<STOfficialPDFAudit data={data}/>);expect(screen.getByText(/8份巨潮正式PDF与原镜像逐字节相同/)).toBeVisible()
  fireEvent.click(screen.getByText('展开8份文件、官方链接与原镜像'))
  expect(screen.getAllByRole('link',{name:'巨潮正式PDF · 3页 ↗'})).toHaveLength(8)
  expect(screen.getAllByText('本轮返回非PDF内容')).toHaveLength(7)
  expect(screen.getByText('本轮连接未取得文件')).toBeVisible()
 })
 it('adds a page-specific official copy without renaming a mirror as official',()=>{
  const row=data.rows[0];render(<OfficialCopyLink audit={data} sha256={row.mirror_sha256} page={2}/> )
  expect(screen.getByRole('link')).toHaveAttribute('href',row.official_url+'#page=2')
  expect(originalSourceTitle('旧标题（发行人PDF镜像，官方原字节待补）',data,row.mirror_sha256)).toBe('原记录镜像：旧标题')
  expect(originalSourceTitle('未核标题',data,'unknown')).toBe('未核标题')
 })
 it('does not manufacture missing audits',()=>{const {container}=render(<STOfficialPDFAudit/>);expect(container).toBeEmptyDOMElement()})
})
