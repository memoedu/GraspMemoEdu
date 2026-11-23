"""Typed, visible notation shared by streaming recognition and answer formatting."""
import re
import unicodedata
from functools import lru_cache
from importlib.resources import files
from typing import Annotated, Literal

from cn2an import cn2an
from pypinyin import lazy_pinyin
from pydantic import BaseModel, ConfigDict, Field

Symbol = Annotated[str, Field(pattern=r'^[A-Za-z](?:[\^_]\{(?:[A-Za-z]{1,8}|\d{1,4})\})?$')]
Domain = Literal['coordinates', 'vectors', 'calculus', 'fractions', 'geometry', 'functions', 'sequences']


class VoiceContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stem: str = Field(default='', max_length=65536)
    domains: list[Domain] = Field(default_factory=list, max_length=7)
    symbols: list[Symbol] = Field(default_factory=list, max_length=32)
    dimensions: Literal[0, 2, 3] = 0
    style: Literal['mixed', 'literal', 'math', 'code'] = 'mixed'

    def hints(self):
        names = {'coordinates': '坐标', 'vectors': '向量', 'calculus': '微积分', 'fractions': '分式',
                 'geometry': '几何', 'functions': '函数', 'sequences': '数列'}
        return '、'.join([*(names[key] for key in self.domains), *self.symbols])[:400]

    def asr_input(self):
        # Fun-ASR accepts five user messages of at most 400 characters each.
        text = '\n'.join(filter(None, (self.hints(), self.stem)))
        if len(text) > 2000:
            text = text[:999] + '…' + text[-1000:]
        return {'context': [{'role': 'user', 'content': [{'type': 'input_text', 'text': text[i:i + 400]}]}
                            for i in range(0, len(text), 400)]} if text else {}


OPERATORS = {'加上': '+', '加': '+', '减去': '-', '减': '-', '负': '-', '乘以': '*', '乘': '*', '除以': '/',
             '除': '/', '等于': '=', '的平方': '^2', '平方': '^2', '的立方': '^3', '立方': '^3',
             '大于等于': '>=', '小于等于': '<=', '不等于': '!=', '大于': '>', '小于': '<',
             '左括号': '(', '右括号': ')', '×': '*', '÷': '/', '−': '-'}
NUMBER = r'[零〇一二两三四五六七八九十百千万亿点\d]+'
TOKENS = re.compile('|'.join(map(re.escape, sorted(OPERATORS, key=len, reverse=True))) +
                    '|' + NUMBER + r'(?:\.\d+)?|[a-zA-Z]|[-+*/^=().<>]')
DIGIT = '零〇一二两三四五六七八九'
LETTER_NAMES = {'艾克斯': 'x', '埃克斯': 'x', '艾克思': 'x', '歪': 'y', '艾弗': 'f', '艾夫': 'f',
                '泽德': 'z', '阿尔': 'r', '艾姆': 'm', '艾恩': 'n'}


def number(token):
    if re.fullmatch(r'\d+(?:\.\d+)?', token):
        return token
    try:
        if re.fullmatch('[' + DIGIT + ']+', token):
            return ''.join(str(cn2an(char, 'smart')) for char in token)
        return str(cn2an(token, 'smart'))
    except (ValueError, TypeError, IndexError, KeyError):
        return None


@lru_cache(maxsize=256)
def english_sound(word):
    # Match only short, single-syllable labels actually present in this question.
    # CMUdict is sorted. Other words/phonemes are left to contextual dictation.
    phones = {'N': 'n', 'L': 'n', 'M': 'm', 'T': 't', 'D': 'd', 'S': 's', 'Z': 'z', 'K': 'k',
              'B': 'b', 'P': 'p', 'F': 'f', 'W': 'w', 'Y': 'y', 'UW': 'u', 'IY': 'i',
              'OW': 'ou', 'EY': 'ei', 'AY': 'ai', 'AW': 'ao', 'AO': 'o', 'IH': 'i'}
    with files('cmudict').joinpath('data/cmudict.dict').open(encoding='utf-8') as dictionary:
        for line in dictionary:
            key, _, pronunciation = line.partition(' ')
            if key > word:
                break
            if key == word:
                parts = re.sub(r'\d', '', pronunciation).strip().split()
                if 1 <= len(parts) <= 4 and all(p in phones for p in parts):
                    return ''.join(phones[p] for p in parts).replace('yu', 'u')
    return ''


def marked_symbol(compact, context):
    spoken = re.fullmatch(r'([A-Za-z])([A-Za-z]{1,8}|[0-9零一二两三四五六七八九]{1,4})', compact)
    if not spoken:
        return None
    base, suffix = spoken.groups()
    candidates = [s for s in context.symbols if len(s) > 1 and s[0].lower() == base.lower()]
    labels = [(s, s[3:-1]) for s in candidates]
    literal = number(suffix) or suffix.lower()
    matches = [s for s, label in labels if label.lower() == literal]
    if not matches and len(suffix) == 1 and (suffix.isdecimal() or suffix in DIGIT):
        digit = '零一二三四五六七八九'[int(number(suffix))]
        sound = re.sub('^[ln]', 'n', lazy_pinyin(digit)[0])
        sound = re.sub(r'(?<=[a-z])i(?:ou|u)$', 'u', sound)
        matches = [s for s, label in labels if label.isalpha() and english_sound(label.lower()) == sound]
    return matches[0] if len(matches) == 1 else None


def quick_math(transcript, profile, context):
    """Only handle complete, unambiguous token streams; defer prose and scope to the model."""
    if profile not in {'calculator', 'answer'} or context.style == 'code':
        return None
    text = unicodedata.normalize('NFKC', transcript).strip().rstrip('。.!！?？').strip()
    compact = re.sub(r'\s+', '', text)
    for spoken, symbol in LETTER_NAMES.items():
        compact = compact.replace(spoken, symbol)
    if not compact:
        return None
    if profile == 'answer' and 'coordinates' in context.domains:
        dimension = context.dimensions or 2
        values = re.fullmatch(r'(?:坐标(?:是|为)?|点)?\(?((?:负?[-\d' + DIGIT + r']+[,、]){1,2}负?[-\d' + DIGIT + r']+)\)?', compact)
        pieces = re.split('[,、]', values[1]) if values else []
        scalar = re.search(r'横坐标|纵坐标|坐标轴|距离|斜率|distance|slope|[xy]-coordinate', context.stem, re.I)
        if not pieces and not scalar:
            pieces = re.findall(r'[负-]?[' + DIGIT + r'\d]', compact)
            if ''.join(pieces) != compact:
                pieces = []
        if len(pieces) == dimension:
            coords = []
            for piece in pieces:
                value = number(piece.lstrip('负-'))
                if value is None:
                    return None
                coords.append(('-' if piece.startswith(('负', '-')) else '') + value)
            return '(' + ','.join(coords) + ')'
    if profile == 'answer':
        symbol = marked_symbol(compact, context)
        if symbol:
            return symbol
        relation = re.fullmatch(r'(其中|于是|因此|所以)?[,，]?([\u4e00-\u9fff]{1,10})(等于|大于|小于)(.+)', compact)
        if relation and relation[2] in context.stem and context.style == 'mixed':
            right = expression(relation[4], context)
            if right:
                prefix = relation[1] + '，' if relation[1] else ''
                return prefix + r'\(\text{' + relation[2] + '}' + OPERATORS[relation[3]] + right + r'\)'
        if compact.startswith('积分'):
            integral = re.fullmatch(r'积分[,，、]?(.+?)[,，、]?(?:微分|\*?[dD])([A-Za-z])', compact)
            if integral:
                body = expression(integral[1], context)
                if body:
                    latex = r'\int ' + body.replace('*', r'\cdot ') + r'\,d' + integral[2].lower()
                    return latex if context.style == 'math' else r'\(' + latex + r'\)'
    return expression(compact, context)


def expression(compact, context):
    # A near-homophone of a spoken operator may occur between two explicit operands.
    # Restrict correction to this mathematical position; never apply it to prose.
    def between(match):
        spoken = lazy_pinyin(match[0])[0]
        return '乘' if re.fullmatch(r'(?:ch|sh)eng', spoken) else match[0]
    compact = re.sub(r'(?<=[0-9零一二两三四五六七八九A-Za-z])[\u4e00-\u9fff](?=[a-zA-Z])', between, compact)
    # A decorated variable, spoken letter name or an explicit case request needs context-aware refinement.
    if re.search(r'[A-Za-z]{2,}', compact) or any(len(s) > 1 and s[0].lower() in compact.lower() for s in context.symbols):
        return None
    tokens = TOKENS.findall(compact)
    if ''.join(tokens) != compact:
        return None
    result = []
    for token in tokens:
        if token in OPERATORS:
            result.append(OPERATORS[token])
        elif re.fullmatch('[A-Za-z]', token):
            matches = [symbol for symbol in context.symbols if symbol.lower() == token.lower()]
            result.append(matches[0] if len(matches) == 1 else token.lower())
        elif re.fullmatch(NUMBER + r'(?:\.\d+)?', token):
            value = number(token)
            if value is None:
                return None
            result.append(value)
        else:
            result.append(token)
    value = ''.join(result)
    # Only accept a number, variable or a chain with explicit operators and balanced simple groups.
    if '(' in value or ')' in value:
        return None
    atom = r'(?:\d+(?:\.\d+)?|[A-Za-z])'
    if not re.fullmatch(r'[+-]?' + atom + r'(?:(?:[+\-*/^=<>]|[<>!]=)[+-]?' + atom + r')*', value):
        return None
    return value
