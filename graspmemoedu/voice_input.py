"""Temporary website dictation. This endpoint has no learning or archive side effect."""
import base64
from functools import lru_cache
import io
import json
from pathlib import Path
import re
import subprocess
from typing import Literal
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import wave

from pydantic import BaseModel, ConfigDict, Field

from .judge import independent_settings
from .service import DomainError
from .training_audio import decode_recording


VOICE_PATH = '/api/voice-input/transcribe'
VOICE_BODY_LIMIT = 6 * 1024 * 1024
RECORDER_FORMATS = {'audio/mp4': 'mov', 'audio/webm': 'matroska', 'audio/ogg': 'ogg'}
FORMULA = re.compile(r'[0-9A-Za-z_+*/^!%.,;:()\[\]=<>|&~\-π∞≤≥≠√×÷−%]+')
FUNCTIONS = set('abs acos acosh asin asinh atan atanh cbrt ceil cos cosh exp floor ln log log10 log2 max min mod nCr nPr pi pow round sign sin sinh sqrt tan tanh ans'.split())


class VoiceRecording(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mime_type: Literal['audio/mp4', 'audio/webm', 'audio/ogg', 'audio/wav']
    data_base64: str = Field(min_length=1, max_length=5592408)
    profile: Literal['general', 'answer', 'calculator', 'answer_commands']


def recorded_wave(payload):
    if payload.mime_type == 'audio/wav':
        return decode_recording(payload.data_base64)
    try:
        source = base64.b64decode(payload.data_base64, validate=True)
        # Bound decoding time and PCM output. Read only the submitted bytes.
        pcm = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-protocol_whitelist', 'pipe',
                              '-f', RECORDER_FORMATS[payload.mime_type], '-threads', '1', '-i', 'pipe:0',
                              '-map', '0:a:0', '-vn', '-t', '120.1', '-ac', '1', '-ar', '16000',
                              '-f', 's16le', 'pipe:1'], input=source, capture_output=True, timeout=15, check=True).stdout
        if not pcm or len(pcm) % 2 or len(pcm) > 120 * 16000 * 2:
            raise ValueError('Invalid duration')
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            wav.writeframes(pcm)
        return output.getvalue()
    except FileNotFoundError:
        raise DomainError('transcription_unavailable', '录音转换服务暂不可用。', 503) from None
    except (ValueError, OSError, subprocess.SubprocessError):
        raise DomainError('invalid_recording', '录音为空、格式无效或超过 120 秒，请重新录音。', 422) from None


@lru_cache
def prompt(name):
    return Path(__file__).with_name('voice_prompts').joinpath(name).read_text(encoding='utf-8')


def complete(instructions, source, *, input_key='recording_transcript', max_tokens=4500):
    config = independent_settings()
    base_url = config['base_url'].rstrip('/')
    host = urlsplit(base_url)
    if host.scheme != 'https' or not host.hostname or host.username or host.password or host.query or host.fragment:
        raise ValueError('Invalid refinement endpoint')
    messages = [{'role': 'system', 'content': instructions}, {'role': 'user', 'content': json.dumps(
        {input_key: source}, ensure_ascii=False)}]
    openai = host.hostname == 'api.openai.com'
    if openai:
        payload = {'model': config['model'], 'input': messages, 'store': False, 'max_output_tokens': max_tokens}
    else:
        payload = {'model': config['model'], 'messages': messages, 'max_tokens': max_tokens, 'temperature': 0}
        if host.hostname == 'api.deepseek.com':
            payload['thinking'] = {'type': 'disabled'}
    request = Request(base_url + ('/responses' if openai else '/chat/completions'),
                      data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={'Authorization': 'Bearer ' + config['api_key'], 'Content-Type': 'application/json'})
    with urlopen(request, timeout=23) as response:
        raw = json.loads(response.read(256 * 1024 + 1))
    if openai and raw.get('status') == 'completed':
        return ''.join(part['text'] for item in raw['output'] if item.get('type') == 'message'
                       for part in item.get('content', []) if part.get('type') == 'output_text')
    choice = raw['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Incomplete refinement')
    return choice['message']['content']


def refine_voice(text, profile, generate=complete):
    try:
        if profile == 'calculator':
            value = generate('这是非写作语音输入。仅把录音转成原话指定的可输入计算器的算式或算式片段。'
                             '使用 0-9、ASCII 运算符、括号、英文数学函数与变量。保留原式和运算顺序，不计算、不补写。'
                             '只输出一行算式，不输出空格、制表符、自然语言、结果、Markdown 或 LaTeX。无法辨认时输出空字符串。', text)
            value = value.strip(' ')
            if (not FORMULA.fullmatch(value) or len(value) > 4096 or
                    any(len(word) > 1 and word not in FUNCTIONS for word in re.findall(r'[A-Za-z_]+', value))):
                raise DomainError('voice_formula_invalid', '没有获得可输入的算式，请重试。', 422)
            return value
        route = 'non_writing' if profile == 'answer' else generate(
            prompt('decide-writing.md') + '\n只返回 writing、non_writing 或 uncertain 中的一个，省略其他字符。', text).strip()
        name = 'refine-dictation-non-writing.md' if route == 'non_writing' else 'refine-writing.md'
        formatting = ('这是学生当前作答的片段。只转写已经说出的内容，保留口述的事实、公式、结论和步骤，包括可能错误的答案。'
                      '明确保留每个空的序号、对应值、口述顺序，以及跳过、留空或改填等指令。'
                      '即使只说第二、第三空，也不要删去空号、按顺序重新编号或补写第一空。'
                      '不纠错、不解题、不添加标题、列表符号、解释或 Markdown。公式用适合原位插入的纯文本。'
                      if profile == 'answer' else '只输出可直接插入当前光标的正文。保留自然段，不加标题、大纲标记或说明。')
        value = generate(prompt(name) + '\n\n' + prompt('refine-quotation-style.md') + '\n\n' + formatting, text).strip()
        if not value or len(value) > 16000:
            raise ValueError('Invalid refinement')
        return value
    except (OSError, ValueError, KeyError, AttributeError, TypeError, IndexError):
        raise DomainError('voice_refinement_failed', '录音文字整理未完成，请重试或直接输入。', 502) from None
