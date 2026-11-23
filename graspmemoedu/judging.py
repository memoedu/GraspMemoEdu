"""The existing judge contract shared by Lesson and review submissions."""
from .question_types import (demo_answer, deterministic_verdict, display_answer, is_reproduction,
                             parse_submission_answer, semantic_arguments, whiteboard_answer)


def instant_question(question, answer=None):
    """Classify the server's pinned question without grading or exposing its key."""
    return not whiteboard_answer(answer) and not is_reproduction(question)


def local_verdict(question, target, payload, con, require_judge):
    """Resolve a validated answer locally or request admission before enqueuing it."""
    if require_judge is None:
        return None
    from .self_assessment import verdict
    assessed = verdict(target, payload['request_id'])
    if assessed is not None:
        return assessed
    if instant_question(question, payload['answer']):
        return judge_answer(None, question, payload['answer'])
    require_judge(con, 1)
    return None


def judge_answer(judge, question, answer):
    # Call this outside any database transaction.
    try:
        if judge is None:
            if not whiteboard_answer(answer):
                deterministic = deterministic_verdict(question, answer)
                if deterministic is not None:
                    return deterministic
            raise RuntimeError('Judge not configured')
        if whiteboard_answer(answer):
            text = parse_submission_answer(question, answer)
            reference = question['reference_answer']
            spec = question.get('interaction')
            if spec and spec.get('grading', 'exact') != 'semantic':
                expected = display_answer(question, demo_answer(question))
                if expected and expected not in reference:
                    reference += '\n\n各项标准答案：\n' + expected
            constraints = question['constraints']
            stem = question['question'] + '\n作答约束：' + constraints
            verdict = judge(stem, reference, text)
        else:
            deterministic = deterministic_verdict(question, answer)
            if deterministic is not None:
                return deterministic
            verdict = judge(*semantic_arguments(question, answer))
        if not isinstance(verdict, dict):
            verdict = {'status': verdict.status, 'correct': verdict.correct, 'reason': verdict.reason}
        if (verdict.get('status') == 'judged' and type(verdict.get('correct')) is bool
                and isinstance(verdict.get('reason'), str)):
            return verdict['correct'], verdict['reason'][:2000]
    except Exception:
        pass
    return None, '判题服务暂时不可用，请重试；本次未计入作答。'
