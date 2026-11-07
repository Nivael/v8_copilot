import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFIssuerHistory} from './ETFIssuerHistory'
import type {ETFIssuerHistory as History} from './types'

const latest={record_on:'2026-01-16',cash_paid_on:'2026-01-27',ex_dividend_on:null,off_exchange_record_on:null,off_exchange_cash_paid_on:null,evaluation_reference_on:null,
  source_amount_text:'1.230',source_unit_shares:10,amount_yuan_per_share:'0.123'}
const source={issuer:'华泰柏瑞',availability:'observed',source_url:'https://www.huatai-pb.com/products/zhishu/510300/index.html',observed_at:'2026-11-05T02:15:26Z',table_records:14,latest_listed_distribution:latest,
  window_record_date_count:0,window_cash_paid_date_count:0,window_split_count:null,split_table_status:'not_checked',splits:[],responses:[{method:'GET',url:'https://www.huatai-pb.com/products/zhishu/510300/index.html',params:null,observed_at:'2026-11-05T02:15:26Z'}]}
const fixture:History={version:'issuer_etf_action_tables_v1',availability:'partial',declared_etfs:8,history_tables_observed:5,empty_tables_unconfirmed:1,query_failed_etfs:2,
  window_start:'2026-08-04',through:'2026-11-04',query_cutoff:'2026-11-05',completed_at:'2026-11-05T02:15:27Z',market_target:'2026-11-04',note:'原表未列事项不证明全窗无事件，未用于净申赎校正。',corporate_actions_checked:false,estimated_net_subscription_yuan:null,
  funds:[{...source,code:'510300.SH'},{...source,code:'159919.SZ',issuer:'嘉实',availability:'query_failed',table_records:null,latest_listed_distribution:null,window_record_date_count:null,window_cash_paid_date_count:null},
    {...source,code:'159845.SZ',issuer:'华夏',availability:'empty_table_unconfirmed',table_records:null,latest_listed_distribution:null,window_record_date_count:null,window_cash_paid_date_count:null}]}

function open(){fireEvent.click(screen.getByText('发行人分红历史：有效记录表 5/8；空表待核 1；查询失败 2'))}

describe('ETFIssuerHistory',()=>{
  afterEach(cleanup)
  it('distinguishes source errors and empty tables without displaying zero events for them',()=>{
    render(<ETFIssuerHistory data={fixture}/>);open()
    expect(screen.getByText('查询失败，记录数量未知')).toBeVisible()
    expect(screen.getByText('返回空表，尚不能确认无分红')).toBeVisible()
    expect(screen.getAllByText('窗口内次数保持未知，未填零')).toHaveLength(2)
    expect(screen.getAllByText('分红窗口次数未知')).toHaveLength(2)
    expect(screen.getAllByText('登记日在窗内 0 条')).toHaveLength(1)
  })
  it('preserves the original per-ten-share amount and the distinct registration/payment dates',()=>{
    render(<ETFIssuerHistory data={fixture}/>);open()
    expect(screen.getByText('登记日 2026-01-16')).toBeVisible()
    expect(screen.getByText('现金发放日 2026-01-27')).toBeVisible()
    expect(screen.getByText('原表每10份 1.230 元；折每份 0.123 元')).toBeVisible()
    expect(screen.getByText('除息日未在本项核实')).toBeVisible()
    expect(screen.getByText(/本项核对窗 2026-08-04 至 2026-11-04；本次查询日期 2026-11-05/)).toBeVisible()
    expect(screen.getAllByText('本次取得 2026/11/5 10:15:26（北京时间）')).toHaveLength(3)
  })
  it('keeps off-exchange and evaluation dates separate from an unknown ex-dividend date',()=>{
    const fund={...fixture.funds[0],latest_listed_distribution:{...latest,source_unit_shares:1,source_amount_text:'0.123',off_exchange_record_on:'2026-01-20',off_exchange_cash_paid_on:'2026-01-21',evaluation_reference_on:'2026-01-08'}}
    render(<ETFIssuerHistory data={{...fixture,funds:[fund]}}/>);open()
    expect(screen.getByText('场外登记 2026-01-20；场外发放 2026-01-21')).toBeVisible()
    expect(screen.getByText('收益评价基准日 2026-01-08，不当作除息日')).toBeVisible()
    expect(screen.queryByText('除息日 2026-01-08')).not.toBeInTheDocument()
  })
  it('shows historical split-table ratios without applying them to the current window',()=>{
    const fund={...fixture.funds[0],split_table_status:'observed',window_split_count:0,splits:[{effective_on:'2022-09-02',ratio:'0.36555'}]}
    render(<ETFIssuerHistory data={{...fixture,funds:[fund]}}/>);open();fireEvent.click(screen.getByText('原表所列拆分记录'))
    expect(screen.getByText('拆分表已返回 1 条，其中本窗 0 条')).toBeVisible()
    expect(screen.getByText('2022-09-02 · 比例 0.36555')).toBeVisible()
    expect(screen.getByText(/不用于当前曲线校正/)).toBeVisible()
    expect(screen.getByRole('region',{name:'可滚动的发行人分红核对表'})).toHaveAttribute('tabindex','0')
  })
  it('discloses a market-target mismatch and the original query rather than moving source dates',()=>{
    render(<ETFIssuerHistory data={{...fixture,market_target:'2026-11-05'}}/>);open()
    expect(screen.getByText('当前市场目标为 2026-11-05，此历史表尚未覆盖新目标，不能沿用为新目标核验。')).toBeVisible()
    fireEvent.click(screen.getByText('原响应、查询与字段依据'))
    expect(screen.getByText(/净申赎金额继续未发布/)).toBeVisible()
    const table=screen.getByRole('table')
    expect(within(table).getAllByRole('link')[0]).toHaveAttribute('href',source.source_url)
  })
  it('removes all source facts and zero-count language for an unavailable snapshot',()=>{
    render(<ETFIssuerHistory data={{...fixture,availability:'invalid',history_tables_observed:0,empty_tables_unconfirmed:0,query_failed_etfs:0,funds:[]}}/>)
    fireEvent.click(screen.getByText('发行人分红历史：尚无通过核验的快照'))
    expect(screen.getByText('尚无通过当前原响应、字段及单位校验的历史表，未将缺失记录填零。')).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByText(/查询失败 0/)).not.toBeInTheDocument()
  })
})
