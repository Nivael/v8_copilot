"""Bind a new auction phase to retained original company evidence."""
from pathlib import Path
from hashlib import sha256
import gzip,json
from long_breadth_st_alignment import INPUT,INPUT_SHA


def build():
    raw=INPUT.read_bytes()
    if sha256(raw).hexdigest()!=INPUT_SHA:raise ValueError('original company input changed')
    original=json.loads(gzip.decompress(raw))['baoxin_holding_bridge']
    p=Path('NOV20_JUDICIAL_BODY_REVIEW_2026_11_21.json');review=json.loads(p.read_text());finding=next(f for f in review['findings']if f['announcement_id']=='1225679913');source=next(s for s in review['sources']if s['announcement_id']==finding['announcement_id'])
    if finding['code']!='002514' or sha256(Path(source['source_store']).read_bytes()).hexdigest()!=source['sha256']:raise ValueError('new auction source changed')
    return dict(original_input_sha256=INPUT_SHA,expected_context={k:original[k]for k in ['through','prior_digest','sources','rows','partial','debt']},judicial_review_sha256=sha256(p.read_bytes()).hexdigest(),finding=finding,source=source,reading=dict(title='11月20日更新：另一笔200万股流拍，旧过户记录分别保留',meaning='先前几组股份已有登记凭据；这次公告新增的是11月18—19日一拍流拍的200万股。不能因股数同为200万，就把它与此前已过户的两笔200万股配成同一标的。',watch='接下来追这笔流拍是否重拍、后续四笔预告的实际结果及过户文件。12月2—3日10万股预告与叶铭康悔拍10万股的关系仍未核清；本公告没有证明此前抵债股份登记完成。'))


if __name__=='__main__':
    Path('BAOXIN_NOV20_CASE_LINK_EVIDENCE_2026_11_21.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
