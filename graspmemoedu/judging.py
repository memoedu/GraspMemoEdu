"""The existing judge contract shared by Lesson and review submissions."""
from .question_types import deterministic_verdict, semantic_arguments, is_reproduction


def instant_question(question):
    """Classify the server's pinned question without grading or exposing its key."""
    return not is_reproduction(question)


def local_verdict(question, target, payload, con, require_judge):
    """Resolve a validated answer locally or request admission before enqueuing it."""
    if require_judge is None:
        return None
    from .self_assessment import verdict
    assessed = verdict(target, payload['request_id'])
    if assessed is not None:
        return assessed
    if instant_question(question):
        return judge_answer(None, question, payload['answer'])
    require_judge(con, 1)
    return None


def judge_answer(judge, question, answer):
    # Call this outside any database transaction.
    try:
        deterministic = deterministic_verdict(question, answer)
        if deterministic is not None:
            return deterministic
        if judge is None:
            raise RuntimeError('Judge not configured')
        verdict = judge(*semantic_arguments(question, answer))
        if not isinstance(verdict, dict):
            verdict = {'status': verdict.status, 'correct': verdict.correct, 'reason': verdict.reason}
        if (verdict.get('status') == 'judged' and type(verdict.get('correct')) is bool
                and isinstance(verdict.get('reason'), str)):
            return verdict['correct'], verdict['reason'][:2000]
    except Exception:
        pass
    return None, '判题服务暂时不可用，请重试；本次未计入作答。'
