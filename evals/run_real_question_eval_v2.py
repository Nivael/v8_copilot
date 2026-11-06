"""Current real-question gate: preserve missing-year ambiguity and test explicit dates separately."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from evals.run_real_question_eval_v1 import evaluate as evaluate_cases


SET_PATH=Path(__file__).with_name('real_question_answerability_set_v2.jsonl')


def evaluate():
    return evaluate_cases(set_path=SET_PATH)


if __name__=='__main__':
    passed,total=evaluate()
    print(f'[OK] real-question answerability v2 {passed}/{total}')
