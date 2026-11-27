"""Offline dictionary forms and the four masu forms used in the local reader."""

import re

from graspmemoedu.service import DomainError


POLITE_TOPIC_ID = "jp07-polite-forms"
POLITE_POINT_ID = "p-jp07-masu"
MAX_TEXT_LENGTH = 2000

_ENDINGS = (
    (("ませ", "ん", "でし", "た"), "过去否定", ("礼貌助动词「ます」的活用形", "表示否定", "礼貌助动词「です」的活用形", "表示过去")),
    (("まし", "た"), "过去肯定", ("礼貌助动词「ます」的活用形", "表示过去")),
    (("ませ", "ん"), "非过去否定", ("礼貌助动词「ます」的活用形", "表示否定")),
    (("ます",), "非过去肯定", ("礼貌助动词「ます」",)),
)
_WORD_TYPES = {"名詞", "代名詞", "動詞", "形容詞", "形状詞", "連体詞", "副詞", "感動詞"}
_JAPANESE = re.compile(r"[ぁ-ゖァ-ヺ々一-鿿]")
_KATAKANA_TO_HIRAGANA = {code: code - 0x60 for code in range(0x30A1, 0x30F7)}
_GLOSSES = {
    "朝ごはん": "早饭", "昨日": "昨天", "食べる": "吃", "水": "水", "飲む": "喝",
    "夕方": "傍晚", "店": "店铺", "行く": "去", "でも": "但是", "パン": "面包",
    "買う": "买", "学校": "学校", "読む": "读", "見る": "看", "来る": "来", "する": "做",
}


def _tokens(text):
    # The tagger has mutable native state. Keep it request-local for concurrent reads.
    try:
        from fugashi import Tagger
        import unidic_lite

        directory = unidic_lite.DICDIR
        tagger = Tagger(f'-r "{directory}/mecabrc" -d "{directory}"')
    except (ImportError, RuntimeError, OSError) as exc:
        raise DomainError("reading_dictionary_unavailable", "日语词典不可用。请安装 requirements-japanese-reading.txt 中的依赖。", 503) from exc

    tokens = []
    cursor = 0
    for word in tagger(text):
        start = text.find(word.surface, cursor)
        if start < 0:
            return [(text, None, False)]
        if start > cursor:
            tokens.append((text[cursor:start], None, False))
        tokens.append((word.surface, word.feature, not word.is_unk))
        cursor = start + len(word.surface)
    if cursor < len(text):
        tokens.append((text[cursor:], None, False))
    return tokens


def _polite_ending(tokens, index):
    # A verb stem followed by an attested ます auxiliary, not a substring match.
    if index == 0:
        return None
    previous = tokens[index - 1][1]
    feature = tokens[index][1]
    if (previous is None or previous.pos1 != "動詞" or not previous.cForm.startswith("連用形")
            or feature is None or feature.pos1 != "助動詞" or feature.lemma != "ます"):
        return None
    for parts, label, explanations in _ENDINGS:
        group = tokens[index:index + len(parts)]
        if tuple(token[0] for token in group) == parts and all(
            entry is not None and entry.pos1 == "助動詞" for _, entry, _ in group
        ):
            return parts, label, explanations
    return None


def analyze_reading(text, *, grammar_ready):
    if not text.strip() or "\0" in text:
        raise DomainError("invalid_reading_text", "请输入要分析的日文。", 422)
    tokens = _tokens(text)
    segments = []
    index = 0
    while index < len(tokens):
        surface, feature, known = tokens[index]
        ending = _polite_ending(tokens, index)
        if ending is not None:
            parts, label, explanations = ending
            segment = {"text": "".join(parts), "kind": "text"}
            if grammar_ready:
                segment.update(kind="grammar", label=f"礼貌体・{label}", point_id=POLITE_POINT_ID,
                               parts=[{"text": part, "explanation": explanation}
                                      for part, explanation in zip(parts, explanations)])
            segments.append(segment)
            index += len(parts)
            continue

        segment = {"text": surface, "kind": "text"}
        if known and feature.pos1 in _WORD_TYPES and _JAPANESE.search(surface):
            lemma = feature.orthBase or surface
            reading = (feature.kanaBase or feature.kana or "").translate(_KATAKANA_TO_HIRAGANA)
            segment.update(kind="word", lemma=lemma, reading=reading, gloss=_GLOSSES.get(lemma, ""))
        if segment["kind"] == "text" and segments and segments[-1]["kind"] == "text":
            segments[-1]["text"] += surface
        else:
            segments.append(segment)
        index += 1
    return segments
