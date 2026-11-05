from pathlib import Path
import pytest

from experience_verification import software_digest


@pytest.mark.parametrize('relative',[
    'rules.py','risk_parameters.json','source_profile.JSON','examples.jsonl','pyproject.toml','uv.lock','.python-version',
    'llm/provider.py','evals/scenarios.json','tests/fixtures/source.json','contracts/example.json',
    'benchmarks/fixtures/events.json','benchmarks/check_inputs.py','pilot_manifests/pilot.json',
])
def test_software_code_rule_configuration_and_declared_fixture_changes_invalidate_the_binding(tmp_path,relative):
    path=tmp_path/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('first')
    before=software_digest(tmp_path);path.write_text('second')
    assert software_digest(tmp_path)!=before


def test_rule_config_creation_removal_and_rename_are_changes_even_with_identical_content(tmp_path):
    first=software_digest(tmp_path);path=tmp_path/'rules.json';path.write_text('{}')
    second=software_digest(tmp_path);assert second!=first
    renamed=tmp_path/'rules_v2.json';path.rename(renamed)
    assert software_digest(tmp_path)!=second
    renamed.unlink();assert software_digest(tmp_path)==first


def test_binding_is_portable_and_independent_of_creation_order_and_file_mtime(tmp_path):
    a,b=tmp_path/'a',tmp_path/'b';a.mkdir();b.mkdir()
    for name in ('source.py','rules.json'):(a/name).write_text(name)
    for name in ('rules.json','source.py'):(b/name).write_text(name)
    assert software_digest(a)==software_digest(b)
    (a/'rules.json').touch();assert software_digest(a)==software_digest(b)


def test_local_data_audits_logs_browser_assets_and_prose_are_not_software_rule_inputs(tmp_path):
    (tmp_path/'rules.py').write_text('rule')
    before=software_digest(tmp_path)
    for relative in ('local_data/private.json','out/report.json','.venv/package.py','.git/config.json','web/src/page.tsx','web/package.json','README.md','local_secrets/credentials.json'):
        path=tmp_path/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('unrelated')
    assert software_digest(tmp_path)==before
