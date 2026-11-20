import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {RunAudit} from './RunAudit'
import {ResearchIdentitySummary,type ResearchIdentityNote} from './ResearchIdentityNotice'
const note:ResearchIdentityNote={run_id:'RUN-AAAAAAAAAAAAAAAAAAAAAAAA',corrected_question:'核四通与绝味的公告窗口',corrected_object_refs:['603838','603517'],corrected_research_as_of:'2026-11-19',original_question:'旧登记岭南',original_object_refs:['002717'],original_research_as_of:'2026-05-26',reviewed_at:'2026-11-20T10:00:00Z',experience_context:'inherited_unreviewed',topic_changed:true}
const run={run_id:note.run_id,request_id:'old',question_text:note.original_question,agent_surface:'codex_desktop',created_at:'2026-11-20T09:00:00Z',normalized_intent:'research',evidence_pack_ids:[],experience_candidate_ids:[],validation_report:{valid:true},source_freshness:{},final_answer:'原回答保留',decision_audit:{},research_draft:{}}
afterEach(()=>{cleanup();vi.restoreAllMocks()})
it('shows corrected reading identity while keeping original identity available and disabling legacy-context feedback',async()=>{
 vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{const url=String(input);return new Response(JSON.stringify(url.includes('identity-corrections')?{availability:'available',corrections:[note]}:url.includes('/corrections')?{availability:'available',corrections:[]}:[run]))})
 render(<MemoryRouter><RunAudit/></MemoryRouter>);expect(await screen.findByRole('heading',{name:note.corrected_question})).toBeVisible();expect(screen.getByText(/继承检索背景/)).toBeVisible();expect(screen.queryByRole('region',{name:'本次研究反馈'})).not.toBeInTheDocument();fireEvent.click(screen.getByText('查看原始登记身份'));expect(screen.getByText('原登记题目：旧登记岭南')).toBeVisible();expect(screen.getByText(/原证据包截止：2026-05-26/)).toBeVisible();expect(screen.getByLabelText('正文结构校验通过，身份登记已更正')).toBeVisible()
})
it('does not present missing or invalid corrections as a clean zero',async()=>{
 vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({availability:'invalid',corrections:[]})));render(<MemoryRouter><ResearchIdentitySummary/></MemoryRouter>);expect(await screen.findByText(/研究登记身份核对暂不可读/)).toBeVisible();expect(screen.getByRole('link',{name:'查看原运行记录'})).toHaveAttribute('href','/runs')
})
it('links each corrected study without counting notes as new experience evidence',async()=>{
 vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({availability:'available',corrections:[note]})));render(<MemoryRouter><ResearchIdentitySummary/></MemoryRouter>);expect(await screen.findByText(/1条近期复盘/)).toBeVisible();fireEvent.click(screen.getByText('哪些主题和日期经过校正？'));expect(screen.getByRole('link',{name:note.corrected_question})).toHaveAttribute('href','/runs#research-'+note.run_id);expect(screen.getByText(/这不是新增研究或经验验证/)).toBeVisible()
})
it('keeps raw runs readable but does not train from a failed identity lookup',async()=>{
 vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{const url=String(input);return new Response(JSON.stringify(url.includes('identity-corrections')?{availability:'invalid',corrections:[]}:url.includes('/corrections')?{availability:'available',corrections:[]}:[run]))});render(<MemoryRouter><RunAudit/></MemoryRouter>);expect(await screen.findByRole('heading',{name:note.original_question})).toBeVisible();expect(screen.getByText(/以下原始登记不视为已核身份/)).toBeVisible();expect(screen.queryByRole('region',{name:'本次研究反馈'})).not.toBeInTheDocument()
})
