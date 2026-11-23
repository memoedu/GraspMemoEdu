"""Typed, visible notation shared by streaming recognition and answer formatting."""
import re
import unicodedata
from functools import cached_property, lru_cache
from difflib import SequenceMatcher
from importlib.resources import files
from typing import Annotated, Literal

from cn2an import cn2an
from pypinyin import lazy_pinyin
from pydantic import BaseModel, ConfigDict, Field

Symbol = Annotated[str, Field(pattern=r'^[A-Za-z](?:[\^_]\{(?:[A-Za-z]{1,8}|\d{1,4})\})?$')]
Domain = Literal['coordinates', 'vectors', 'calculus', 'fractions', 'geometry', 'functions', 'sequences']


def excerpt(text, limit):
    if len(text) <= limit:
        return text
    tail = limit // 2
    return text[:limit - tail - 1] + '…' + text[-tail:]


class TextboxContext(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    before: str = Field(default='', max_length=4096)
    selected: str = Field(default='', max_length=4096)
    after: str = Field(default='', max_length=4096)

    @cached_property
    def text(self):
        return '\n'.join((self.before, self.selected, self.after))

    @cached_property
    def symbols(self):
        clean = re.sub(r'\\(?:text|operatorname|begin|end)\{[^}]*\}|\\[A-Za-z]+', ' ', self.text)
        pattern = r'(?<![A-Za-z])([A-Za-z])(?:\s*([_^])\s*(?:\{([A-Za-z]{1,8}|\d{1,4})\}|([A-Za-z]{1,8}|\d{1,4})))?(?![A-Za-z])'
        return tuple(dict.fromkeys(base + (mark + '{' + (braced or bare) + '}' if mark else '')
                                   for base, mark, braced, bare in re.findall(pattern, clean)))

    def asr_hint(self):
        return '\n'.join(label + text for label, text in (
            ('光标前：', self.before[-400:]), ('选区：', excerpt(self.selected, 160)), ('光标后：', self.after[:300])) if text)


class VoiceContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stem: str = Field(default='', max_length=65536)
    domains: list[Domain] = Field(default_factory=list, max_length=7)
    symbols: list[Symbol] = Field(default_factory=list, max_length=32)
    dimensions: Literal[0, 2, 3] = 0
    style: Literal['mixed', 'literal', 'math', 'code'] = 'mixed'
    textbox: TextboxContext | None = None

    def symbols_for(self, base):
        local = [s for s in self.textbox.symbols if s[0].lower() == base.lower()] if self.textbox else []
        return local or [s for s in self.symbols if s[0].lower() == base.lower()]

    def hints(self):
        names = {'coordinates': '坐标', 'vectors': '向量', 'calculus': '微积分', 'fractions': '分式',
                 'geometry': '几何', 'functions': '函数', 'sequences': '数列'}
        return '、'.join([*(names[key] for key in self.domains), *self.symbols])[:400]

    def asr_input(self, previous=''):
        # Fun-ASR accepts five user messages of at most 400 characters each.
        text = '\n'.join(filter(None, (self.hints(), self.stem)))
        suffix = '\n'.join(filter(None, (self.textbox.asr_hint() if self.textbox else '', previous[-240:])))
        text = '\n'.join(filter(None, (excerpt(text, 2000 - len(suffix) - bool(suffix)), suffix)))
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
    candidates = [s for s in context.symbols_for(base) if len(s) > 1]
    labels = [(s, s[3:-1]) for s in candidates]
    literal = number(suffix) or suffix.lower()
    matches = [s for s, label in labels if label.lower() == literal]
    if not matches and len(suffix) == 1 and (suffix.isdecimal() or suffix in DIGIT):
        digit = '零一二三四五六七八九'[int(number(suffix))]
        sound = re.sub('^[ln]', 'n', lazy_pinyin(digit)[0])
        sound = re.sub(r'(?<=[a-z])i(?:ou|u)$', 'u', sound)
        matches = [s for s, label in labels if label.isalpha() and english_sound(label.lower()) == sound]
    return matches[0] if len(matches) == 1 else None


def named_quantity(label, context):
    """Read an explicit name/symbol binding; defer ambiguous or indirect references."""
    name = re.escape(label)
    sources = [(context.stem, context.symbols)]
    if context.textbox:
        sources.insert(0, (context.textbox.text, context.textbox.symbols))
    for source, symbols in sources:
        stem = re.sub(r'\\[()[\]]|\$|\s+', '', source)
        matches = []
        for symbol in symbols:
            item = re.escape(symbol) + r'(?![a-zA-Z0-9_^])'
            if (re.search(name + r'(?:记[为作]|定义为|表示为|为)' + item, stem)
                    or re.search(name + r'(?:可)?用' + item + r'(?:来)?表示', stem)
                    or re.search(r'(?<![a-zA-Z0-9])' + item + r'(?:表示|代表)' + name, stem)):
                matches.append(symbol)
        if matches:
            return matches[0] if len(matches) == 1 else None
    return None


REPAIR = re.compile(r'(?:[，,。；;！!？?]\s*|(?<=[\d零一二两三四五六七八九十]))'
                    r'(?:不对|(?:我)?说错了|口误|更正一下)(?=$|[，,。；;\s]|应该|应为|是)'
                    r'[，,。；;\s]*(?:应该(?:是|说)|应为|是)?[，,。\s]*')


def direct_dictation(text, *, partial=False):
    """Resolve explicit restatements inside this recording. Leave ambiguous repairs for refinement."""
    if any(mark in text for mark in '“”「」"'):
        return text, False
    if partial:
        text = re.sub(r'[，,。；;]\s*不$', '', text)
    if not REPAIR.search(text):
        return text, False
    previous, *repairs = REPAIR.split(text)
    for replacement in repairs:
        body = replacement.strip('，,。！？!? ')
        if not body or partial and body in ('因', '应', '应该', '我说'):
            return previous, True
        # Only the clause being corrected may change. Earlier statements stay in place.
        start = max(previous.rfind(mark) for mark in '。！？!?；;') + 1
        clause = previous[start:]
        if re.fullmatch(NUMBER, body):
            last = re.search(NUMBER + r'$', clause)
            if last:
                previous = previous[:start + last.start()] + replacement
                continue
        # A repeated phrase anchors the replacement, e.g. a repeated variable, weekday or noun.
        if len(clause) > 256 or len(body) > 256:
            return text, True
        match = SequenceMatcher(None, clause, body, autojunk=False).find_longest_match()
        if match.size and match.b == 0:
            previous = previous[:start + match.a] + replacement
            continue
        return text, True
    return previous, False


PAUSE = r'[,、。;:]*'


def formula_notation(latex, context):
    return latex if context.style in ('math', 'literal') else r'\(' + latex + r'\)'


def structured_math(text, context):
    vector = re.fullmatch(r'(列向量|竖(?:着)?的?向量|行向量|横(?:着)?的?向量)(?:为|是)?' + PAUSE + r'(.+)', text)
    if vector:
        parts = re.split(r'[,、;。]+', vector[2].strip(',、;。'))
        values = [expression(piece, context) for piece in parts]
        if len(values) >= 2 and all(values):
            separator = r'\\' if vector[1][0] in '列竖' else '&'
            return r'\begin{pmatrix}' + separator.join(values) + r'\end{pmatrix}'
    derivative = re.fullmatch(
        r'偏([A-Za-z])(?:比|除以)偏([A-Za-z])' + PAUSE + r'(?:(?:等于|=)' + PAUSE + r'(.+))?', text)
    if derivative:
        function = expression(derivative[1], context)
        variable = expression(derivative[2], context)
        right = expression(derivative[3], context) if derivative[3] else ''
        if function and variable and (not derivative[3] or right):
            return (r'\frac{\partial ' + function + r'}{\partial ' + variable + '}'
                    + ('=' + right.replace('*', r'\cdot ') if right else ''))
    if text.startswith('积分'):
        limit = r'(?:负|-)?' + NUMBER
        bounds = re.compile(r'从' + PAUSE + '(' + limit + ')' + PAUSE + '到' + PAUSE + '(' + limit + ')')
        body = text[2:].strip(',、。;:')
        limits = bounds.match(body)
        if limits:
            body = body[limits.end():].lstrip(',、。;:')
        else:
            suffix = re.search(bounds.pattern + '$', body)
            if suffix:
                limits, body = suffix, body[:suffix.start()].rstrip(',、。;:')
        differential = re.fullmatch(r'(.+?)' + PAUSE + r'(?:微分|\*?[dD])' + PAUSE + r'([A-Za-z])', body)
        if differential:
            integrand = expression(differential[1], context)
            variable = expression(differential[2], context)
            values = [expression(bound, context) for bound in limits.groups()] if limits else []
            if integrand and variable and all(values):
                scripts = '_{' + values[0] + '}^{' + values[1] + '}' if values else ''
                return r'\int' + scripts + ' ' + integrand.replace('*', r'\cdot ') + r'\,d' + variable
    return None


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
        if relation and context.style == 'mixed' and (relation[2] in context.stem or
                                                      context.textbox and relation[2] in context.textbox.text):
            right = expression(relation[4], context)
            if right:
                left = named_quantity(relation[2], context)
                if not left and (context.symbols or context.textbox and context.textbox.symbols):
                    return None
                prefix = relation[1] + '，' if relation[1] else ''
                if left and not prefix:
                    return left + OPERATORS[relation[3]] + right
                return prefix + r'\(' + (left or r'\text{' + relation[2] + '}') + OPERATORS[relation[3]] + right + r'\)'
        latex = structured_math(compact, context)
        if latex:
            return formula_notation(latex, context)
    return expression(compact, context)


def expression(compact, context):
    # ASR sentences and commas can split a legitimate operator from its operands.
    # Remove pauses only at explicit operators. An ordinary list or stated grouping keeps its meaning.
    operators = r'(?:加上?|减去?|乘以?|除以?|等于|[+\-*/=])'
    compact = re.sub(r'[,，、。;；]+(?=' + operators + ')', '', compact)
    compact = re.sub('(' + operators + r')[,，、。;；]+', r'\1', compact)
    # A near-homophone of a spoken operator may occur between two explicit operands.
    # Restrict correction to this mathematical position; never apply it to prose.
    def between(match):
        spoken = lazy_pinyin(match[0])[0]
        return '乘' if re.fullmatch(r'(?:ch|sh)eng?', spoken) else match[0]
    compact = re.sub(r'(?<=[0-9零一二两三四五六七八九A-Za-z])[\u4e00-\u9fff](?=[a-zA-Z])', between, compact)
    # A decorated variable, spoken letter name or an explicit case request needs context-aware refinement.
    if re.search(r'[A-Za-z]{2,}', compact) or any(len(s) > 1 for base in set(re.findall('[A-Za-z]', compact))
                                                   for s in context.symbols_for(base)):
        return None
    tokens = TOKENS.findall(compact)
    if ''.join(tokens) != compact:
        return None
    result = []
    for token in tokens:
        if token in OPERATORS:
            result.append(OPERATORS[token])
        elif re.fullmatch('[A-Za-z]', token):
            matches = context.symbols_for(token)
            if len(matches) > 1:
                return None
            result.append(matches[0] if matches else token.lower())
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
