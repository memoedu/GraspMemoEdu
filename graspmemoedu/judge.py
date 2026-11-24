import importlib.util
import os
from pathlib import Path
import re
import sys
import threading


ROUNDING_INSTRUCTIONS = """Website precision policy. The following rules override the general output-form rule
above for decimal places. When finding a value is the task and the question specifies a number of decimal places,
accept the correct exact value or a correct approximation at the requested or higher precision. Derive the
underlying value from the question if the reference is rounded. For a longer decimal, count its decimal places
and compare it to the underlying value rounded to that same precision, ignoring redundant trailing zeros.
Do not accept extra incorrect digits just because rounding again matches the reference. Enforce precision when
rounding a given number or determining the appropriate measurement precision is itself what the question tests.
A specified number of decimal places by itself is not evidence that rounding is the skill being tested.
Require exact equality when approximation is not authorized. Keep other constraints and stated tolerances.
"""

# Use reasoning for explicit decimal-precision questions, where the judge must
# distinguish a formatting instruction from a skill being assessed.
DECIMAL_PRECISION = re.compile(r'位\s*小[数數]|小[数數]\s*[点點]\s*[后後]|\bdecimal[\s-]+places?\b|\bd\.\s*p\.',
                               re.IGNORECASE)


def independent_settings():
    """Only dedicated judge variables; live user settings override inherited values."""
    names = ('GRASPMEMOEDU_JUDGE_API_KEY', 'GRASPMEMOEDU_JUDGE_BASE_URL', 'GRASPMEMOEDU_JUDGE_MODEL')
    values = {name: os.environ.get(name, '') for name in names}
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                for name in names:
                    try:
                        value, _ = winreg.QueryValueEx(key, name)
                        values[name] = value if isinstance(value, str) else ''
                    except FileNotFoundError:
                        pass
        except FileNotFoundError:
            pass
    if any(not values[name].strip() for name in names):
        raise ValueError('Dedicated judge environment is incomplete')
    return dict(api_key=values[names[0]].strip(), base_url=values[names[1]].strip(), model=values[names[2]].strip())


class ExistingJudge:
    """Keep credentials and the existing judge's prompt entirely on the server."""

    def __init__(self, project: Path):
        self.project = Path(project)
        self._module = None
        self._lock = threading.Lock()

    def __call__(self, question, reference_answer, student_answer):
        try:
            with self._lock:
                if self._module is None:
                    path = self.project / 'math_answer_judge.py'
                    spec = importlib.util.spec_from_file_location('math_answer_judge', path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = module
                    spec.loader.exec_module(module)
                    self._module = module
                # Never use from_environment(): it falls back to Codex outsourcing.
                # Read each time so edits in Windows user variables need no restart.
                settings = independent_settings()
                if DECIMAL_PRECISION.search(question):
                    settings.update(thinking='enabled', max_tokens=4096)
                judge = self._module.AnswerJudge(self._module.JudgeConfig(**settings),
                                                 additional_instructions=ROUNDING_INSTRUCTIONS)
            result = judge.judge(question, reference_answer, student_answer)
            # Do not return raw output, configuration or API exception details.
            return {'status': result.status, 'correct': result.correct,
                    'reason': result.reason if result.status == 'judged' else '判题服务暂时不可用，请重试；本次未计入作答。'}
        except Exception:
            return {'status': 'error', 'correct': None,
                    'reason': '判题服务暂时不可用，请检查本机配置或稍后重试；本次未计入作答。'}
