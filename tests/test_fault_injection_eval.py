from evals.run_fault_injection_eval import run_fault_injections


def test_fixed_fault_injection_matrix_passes_all_ten_cases() -> None:
    results = run_fault_injections()

    assert len(results) == 10
    assert {result["status"] for result in results} == {"passed"}
