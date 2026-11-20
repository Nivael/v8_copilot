"""Bind new judicial disclosures to reconstructed existing company questions."""
from pathlib import Path
from hashlib import sha256
import gzip,json
from long_breadth_st_alignment import INPUT,INPUT_SHA
from st_twentysecond_period_followup import followup_view as twentysecond
from st_fourteenth_period_followup import followup_view as fourteenth


def build():
    raw=INPUT.read_bytes()
    if sha256(raw).hexdigest()!=INPUT_SHA:raise ValueError('original baseline changed')
    original=json.loads(gzip.decompress(raw));p=Path('NOV20_JUDICIAL_BODY_REVIEW_2026_11_21.json');new=json.loads(p.read_text());links=[]
    for code,phase,processor,identity in [('603008','twentysecond',twentysecond,'1225679623'),('600180','fourteenth',fourteenth,'1225679789')]:
        fp=Path('tests/fixtures/st-'+phase+'-period-followup.json.gz');inputs=json.loads(gzip.decompress(fp.read_bytes()));view=processor(inputs,inputs['test_prior'])
        expected_view=json.loads(Path('web/src/__fixtures__/'+phase+'-period-followup.json').read_text())
        if view!=expected_view:raise ValueError('original reading replay differs')
        sources=[s for s in view['sources']if s['symbol']==code];old={s['announcement_id']:s for s in original[phase+'_period_followup']['sources']}
        if any(any(s[k]!=old[s['announcement_id']][k]for k in ('sha256','url','published_on'))for s in sources):raise ValueError('source differs from frozen baseline')
        finding=next(f for f in new['findings']if f['announcement_id']==identity);source=next(s for s in new['sources']if s['announcement_id']==identity)
        if finding['code']!=code or sha256(Path(source['source_store']).read_bytes()).hexdigest()!=source['sha256']:raise ValueError('new body changed')
        reading=dict(title='11月20日更新：拍卖预告没有关闭占款与担保问题',meaning='新公告推进的是股东股份拟被执行的状态。原问题中的占款回收、担保责任、独立审计仍须各自证据；拍卖公示不能当作上市公司已经回款或风险解除。',watch='继续核拍卖实际结果、缴款与过户，股东预重整是否转为正式受理，以及占款实际回收和担保司法结果。公告关于后续受理的影响是条件说明，不是已观察到拍卖停止。')if code=='603008'else dict(title='11月20日更新：执行压力推进，投资协议与现金仍需另核',meaning='八项既有诉讼进入不同阶段，补强了原问题中的司法执行压力；它没有证明投资款到账、重整方案批准或经营恢复。公告涉案约10.44亿元不能直接加到原债权或亏损上，存在不同口径及事项重叠。',watch='继续核判决履行、拟处置股权的实际结果、负债与费用确认及投资协议条件。20日诉讼公告没有延长原低于1元的价格连续计数，新的收盘和名单须另核。')
        links.append(dict(code=code,expected_context=dict(through=view['through'],sources=sources,chains=[c for c in view['chains']if c['chain'].startswith(code+'-')]),finding=finding,source=source,reading=reading,prior_fixture_sha256=sha256(fp.read_bytes()).hexdigest()))
    return dict(original_input_sha256=INPUT_SHA,judicial_review_sha256=sha256(p.read_bytes()).hexdigest(),links=links)


if __name__=='__main__':
    p=Path('JUDICIAL_NOV20_CASE_LINKS_EVIDENCE_2026_11_21.json');p.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n');value=json.loads(p.read_text());value['evidence_sha256']=sha256(p.read_bytes()).hexdigest();Path('web/src/judicialNov20CaseLinks.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
