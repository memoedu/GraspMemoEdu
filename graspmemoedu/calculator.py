"""Resolve the calculation tools allowed by published material."""
from html import unescape
import re


LEVELS = ('none', 'basic', 'scientific', 'advanced', 'cas')
MA_LEVELS = {'None': 'none', 'Standard': 'basic', 'Scientific': 'scientific', 'Graphing': 'scientific'}
MA_CALLOUT_LABELS = {**{name.casefold(): name for name in MA_LEVELS}, '无': 'None', '标准': 'Standard',
                     '科学': 'Scientific', '图形': 'Graphing', '绘图': 'Graphing'}
MODULES = frozenset(('expression', 'constants', 'graph', 'integral', 'matrix', 'probability',
                     'statistics', 'modular', 'symbolic', 'machine_learning', 'physics', 'chemistry',
                     'signal', 'programmer', 'astronomy', 'geography', 'finance', 'optimization', 'ecology'))
ENABLABLE_MODULES = MODULES - {'expression', 'symbolic'}
OPTIONS = ('enable_modules', 'disable_modules', 'disable_keys')
MA_OVERRIDE = 'override_ma_minimum'
MA_BELOW_MINIMUM = ('none', 'basic')
IDENTIFIER = re.compile(r'[a-z][a-z0-9_]{0,47}\Z')
MA_LABEL = r'(?:Calculator|计算器)\s*[:：]\s*(?P<mode>None|Standard|Scientific|Graphing|无|标准|科学|图形|绘图)(?:计算器)?'
MA_LABEL_LINE = re.compile(r'^[^\S\r\n]*' + MA_LABEL.replace(r'\s*', r'[^\S\r\n]*') + r'[^\S\r\n]*\r?$', re.I | re.M)
MA_LABEL_HINT = re.compile(r'Calculator|计算器', re.I)
PARAGRAPH = re.compile(r'<p(?:\s[^>]*)?>(.*?)</p>', re.I | re.S)
INLINE_FORMAT = re.compile(r'</?(?:strong|em|b|i|span)\b[^>]*>|\*\*|__', re.I)
LEGACY_CALLOUT = re.compile(
    r'<aside\b(?=[^>]*\bclass="inline-document-callout callout")'
    r'(?=[^>]*\bdata-callout="requirement")[^>]*>\s*<strong>[^<]*</strong>\s*'
    r'<p>\s*' + MA_LABEL + r'\s*</p>\s*</aside>', re.I)


def strip_mathacademy_labels(value):
    """Remove source metadata paragraphs and standalone labels from a display field."""
    if not MA_LABEL_HINT.search(value):
        return value

    def metadata(text):
        return MA_LABEL_LINE.fullmatch(INLINE_FORMAT.sub('', unescape(text)).strip())

    html = PARAGRAPH.sub(lambda match: '' if metadata(match[1]) else match[0], LEGACY_CALLOUT.sub('', value))
    return ''.join(line for line in html.splitlines(keepends=True) if not metadata(line))


def normalize(value):
    if value is None:
        return {'level': 'none'}
    if isinstance(value, str):
        value = {'level': value}
    if not isinstance(value, dict) or set(value) - {'level', MA_OVERRIDE, *OPTIONS} or not value:
        raise ValueError('Invalid calculate configuration')
    result = dict(value)
    if 'level' in result and result['level'] not in LEVELS:
        raise ValueError('Unknown calculator level')
    if MA_OVERRIDE in result and (result[MA_OVERRIDE] is not True or 'level' not in result):
        raise ValueError(f'{MA_OVERRIDE} requires true and an explicit calculator level')
    for name in OPTIONS:
        if name not in result:
            continue
        items = result[name]
        if (not isinstance(items, list) or len(items) > 128
                or any(not isinstance(item, str) or not IDENTIFIER.fullmatch(item) for item in items)
                or len(set(items)) != len(items)):
            raise ValueError(f'Invalid calculate.{name}')
        if (name == 'enable_modules' and set(items) - ENABLABLE_MODULES
                or name == 'disable_modules' and set(items) - MODULES):
            raise ValueError(f'Invalid calculator module in {name}')
    return result


def validate(resource):
    if 'calculate' in resource:
        normalize(resource['calculate'])


def from_mathacademy(value):
    if isinstance(value, dict):
        # Only site-authored configuration may make an exception to the minimum.
        return normalize({key: item for key, item in value.items() if key != MA_OVERRIDE})
    if isinstance(value, str) and value in LEVELS:
        return normalize(value)
    level = MA_LEVELS.get(value, 'none') if isinstance(value, str) else 'none'
    return {'level': level, **({'enable_modules': ['graph']} if value == 'Graphing' else {})}


def legacy_mathacademy_mode(question):
    constraints = question.get('constraints')
    if isinstance(constraints, str) and constraints in MA_LEVELS:
        return constraints
    html = question.get('html', '')
    if isinstance(html, str) and (match := LEGACY_CALLOUT.search(html)):
        return MA_CALLOUT_LABELS.get(match.group('mode').casefold())
    return None


def policy(parent, question, *, mathacademy=False, default_level='scientific'):
    if parent.get('_unrestricted_calculator') is True:
        return {'level': 'cas', 'enable_modules': sorted(ENABLABLE_MODULES)}
    inherited = normalize(parent['calculate']) if 'calculate' in parent else {}
    if 'calculate' in question:
        local = normalize(question['calculate'])
    elif mathacademy and (mode := legacy_mathacademy_mode(question)) is not None:
        local = from_mathacademy(mode)
    else:
        local = {}
    if mathacademy:
        if default_level in MA_BELOW_MINIMUM:
            default_level = 'scientific'
        if inherited.get(MA_OVERRIDE) and not local.get(MA_OVERRIDE):
            # A site-authored Topic exception takes precedence over MA question metadata.
            local.pop('level', None)
        for config in (inherited, local):
            if config.get('level') in MA_BELOW_MINIMUM and not config.get(MA_OVERRIDE):
                config.pop('level')
    level = local.get('level', inherited.get('level', default_level))
    if level == 'none':
        return None
    result = {'level': level}
    for field in OPTIONS:
        base = inherited.get(field, ())
        if field == 'enable_modules' and 'level' in local:
            base = ()
        items = sorted(set(base) | set(local.get(field, ())))
        if items:
            result[field] = items
    return result


def presentation(parent, question, *, default_level='scientific'):
    ma = parent.get('source_adapter') == 'mathacademy'
    html = question['html']
    if ma:
        html = strip_mathacademy_labels(html)
    calculator_policy = policy(parent, question, mathacademy=ma, default_level=default_level)
    return {'html': html, **({'calculate': calculator_policy} if calculator_policy else {})}
