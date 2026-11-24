"""OpenAI vision requests via the site's existing TLS-transparent SSH forward."""

from contextlib import closing
from http.client import HTTPSConnection, HTTPException
import json
import os
import socket
import ssl

from .service import DomainError


OPENAI_HOST = 'api.openai.com'
OPENAI_BASE = f'https://{OPENAI_HOST}/v1'


def configured_vision():
    model = os.environ.get('GRASPMEMOEDU_OPENAI_VISION_MODEL', '').strip()
    if not model:
        return None
    key = (os.environ.get('GRASPMEMOEDU_OPENAI_VISION_API_KEY') or
           os.environ.get('GRASPMEMOEDU_CLIPPER_SPEECH_API_KEY', '')).strip()
    port = os.environ.get('GRASPMEMOEDU_CLIPPER_OPENAI_SSH_PORT', '')
    if not key or not port.isascii() or not port.isdecimal() or len(port) > 5 or not 1024 <= int(port) <= 65535:
        raise ValueError('Incomplete OpenAI vision configuration')
    return {'model': model, 'api_key': key, 'base_url': OPENAI_BASE, 'ssh_port': int(port)}


def openai_vision_post(config, endpoint, payload, timeout, limit):
    context = ssl.create_default_context()
    try:
        with closing(HTTPSConnection(OPENAI_HOST, timeout=timeout, context=context)) as connection:
            with socket.create_connection(('127.0.0.1', config['ssh_port']), timeout) as raw:
                connection.sock = context.wrap_socket(raw, server_hostname=OPENAI_HOST)
            connection.request('POST', endpoint, json.dumps(payload).encode(), {
                'Authorization': 'Bearer ' + config['api_key'],
                'Content-Type': 'application/json',
            })
            with connection.getresponse() as response:
                if not 200 <= response.status < 300:
                    raise DomainError('openai_vision_error', f'图像服务返回 HTTP {response.status}。', 502)
                content = response.read(limit + 1)
                if not content or len(content) > limit:
                    raise ValueError('Invalid OpenAI response size')
                return content
    except (HTTPException, OSError):
        raise DomainError('openai_vision_unavailable', '暂时无法连接图像服务，可稍后重试。', 502) from None
