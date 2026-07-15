import {fireEvent,render,screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {App} from './App'

describe('App',()=>{
  afterEach(()=>vi.restoreAllMocks())

  it('opens on reusable experience instead of raw question history',async()=>{
    const experiences=[{
      contract_version:'v8_research_experience_contract_v0',experience_id:'EXP-AAAAAAAAAAAAAAAAAAAA',
      experience_version:1,status:'candidate',experience_type:'presentation_rule',title:'主回答先给判断',
      value_summary:'总览先回答实质差异。',trigger_conditions:['比较问题'],scope:['comparison'],
      required_inputs:['evidence_pack'],query_plan:['识别实质差异'],definitions:[],
      answer_rubric:['首段直接回答'],anti_patterns:['字段清单开头'],coverage_boundaries:['不改变证据强度'],
      validation_refs:['regression:readability'],source_run_refs:['migration:p2.4'],supersedes:[],
      created_at:'2026-07-14T00:00:00Z',reviewed_at:null,reviewed_by:null,not_evidence:true,
    }]
    vi.spyOn(globalThis,'fetch').mockImplementation(async input=>new Response(JSON.stringify(
      String(input).includes('experience-governance')
        ? {accepted_count:0,candidate_count:1,blocked_count:0,conflicts:[],latest_regression:null,ordinary_success_auto_capture:false,not_evidence:true}
        : experiences,
    ),{status:200,headers:{'Content-Type':'application/json'}}))
    render(<MemoryRouter initialEntries={['/']}><App/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'经验中心'})).toBeInTheDocument()
    expect(await screen.findByRole('heading',{name:'主回答先给判断'})).toBeInTheDocument()
    expect(screen.queryByRole('textbox',{name:'研究问题'})).not.toBeInTheDocument()
    expect(screen.getByRole('link',{name:/研究问答（兼容）/})).toHaveAttribute('href','/legacy')
  })

  it('resolves a non-episode announcement deep link into a dossier detail focus',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({
      symbol:'603398',display_name:'沐邦高科',as_of:'2026-01-02',
      price_series:[{date:'2026-01-02',close:13.5}],status_intervals:[],events:[{
        event_id:'announcement:1',date:'2026-01-01',title:'正式公告',
        episode_type:'other_event_path',episode_label:'公开公告（未纳入事件段）',
        subtype_label:'其他公开公告',timeline_lane:'financial',timeline_label:'财报与公告',
        provenance_refs:['announcement:1'],related_lens_ids:[],
      }],
      timeline_lanes:[{lane_id:'financial',label:'财报与公告',event_ids:[]}],
      lens_summaries:[],data_gaps:[],display_labels:{},provenance:[],
    }),{status:200,headers:{'Content-Type':'application/json'}}))
    render(<MemoryRouter initialEntries={[
      '/stocks/603398?event=announcement%3A1&date=2026-01-01&title=虚构公告',
    ]}><App/></MemoryRouter>)

    expect(await screen.findByRole('heading',{name:'正式公告'})).toBeInTheDocument()
    expect(screen.queryByText('虚构公告')).not.toBeInTheDocument()
    expect(screen.getByText('公开公告（未纳入事件段）')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'就此提问'}).getAttribute('href')).toContain('object_kind=stock_event')
    expect(screen.getByRole('button',{name:'1年'})).toHaveAttribute('aria-pressed','true')
    expect(screen.getByRole('checkbox',{name:'仅重点节点'})).toBeChecked()
    fireEvent.click(screen.getByRole('button',{name:'3月'}))
    expect(screen.getByRole('button',{name:'3月'})).toHaveAttribute('aria-pressed','true')
    expect(screen.getByRole('button',{name:'财报与公告'})).toHaveAttribute('aria-pressed','false')
    fireEvent.click(screen.getByRole('button',{name:'财报与公告'}))
    expect(screen.getByRole('button',{name:'财报与公告'})).toHaveAttribute('aria-pressed','true')
  })

  it('keeps announcements newer than the price snapshot visible and separated',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({
      symbol:'300123',display_name:'ST亚光',as_of:'2026-06-26',
      price_series:[{date:'2026-06-26',close:6.2}],status_intervals:[],events:[{
        event_id:'announcement:1225415538',date:'2026-07-08',title:'关于公开招募和遴选重整投资人的公告',
        episode_type:'other_event_path',episode_label:'正式公告（尚未纳入 M6 事件段）',
        subtype:'announcement_unclassified',subtype_label:'正式公告，尚未分类',timeline_lane:'restructuring',
        timeline_label:'重整与预重整（公告标题辅助分组）',provenance_refs:['announcement:1225415538'],related_lens_ids:[],
      }],
      timeline_lanes:[{lane_id:'restructuring',label:'重整与预重整',event_ids:['announcement:1225415538']}],
      lens_summaries:[],data_gaps:[],display_labels:{
        event_count:'1 条正式公告 · 0 个 M6 已分类节点',price_data_as_of:'2026-06-26',
        announcement_data_as_of:'2026-07-08',announcement_refresh_checked_at:'2026-07-12',episode_index_as_of:'2026-07-07',
      },provenance:[],
    }),{status:200,headers:{'Content-Type':'application/json'}}))
    render(<MemoryRouter initialEntries={['/stocks/300123']}><App/></MemoryRouter>)

    expect(await screen.findByRole('region',{name:'价格截止后公告'})).toBeInTheDocument()
    expect(screen.getByText('晚于 2026-06-26，不能与同期价格联读')).toBeInTheDocument()
    expect(screen.getByRole('button',{name:/2026-07-08.*公开招募和遴选重整投资人/})).toBeInTheDocument()
  })
})
