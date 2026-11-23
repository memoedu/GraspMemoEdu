"""Exercise recording limits and real mobile-browser media containers on a loopback site."""
import argparse
import base64
import io
import json
from pathlib import Path
from urllib.parse import urlsplit
import wave

from playwright.sync_api import expect, sync_playwright

from graspmemoedu.voice_input import VoiceRecording, recorded_wave


MICROPHONE = """
([fallback, forceMp4]) => {
  window.micCalls = 0;
  Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {value: async () => {
    window.micCalls++;
    const audio = new AudioContext();
    if (audio.state !== 'running') await audio.resume();
    const tone = audio.createOscillator(), sink = audio.createMediaStreamDestination();
    tone.connect(sink); tone.start();
    window.testAudio = audio;
    return sink.stream;
  }});
  if (fallback && globalThis.AudioWorklet) AudioWorklet.prototype.addModule = () => Promise.reject(Error('Worklet blocked'));
  if (forceMp4) {
    const supported = MediaRecorder.isTypeSupported.bind(MediaRecorder);
    MediaRecorder.isTypeSupported = type => type.startsWith('audio/mp4') && supported(type);
  }
  const now = performance.now.bind(performance);
  window.clockAdvance = 0;
  Object.defineProperty(performance, 'now', {value: () => now() + window.clockAdvance});
}
"""


def exercise(context, base, invitation, fallback, force_mp4, *, use_limit):
    context.add_init_script(f'({MICROPHONE})({json.dumps([fallback, force_mp4])})')
    page = context.new_page()
    opened, uploads, errors = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def stream(route):
        packet = route.request.post_data_json
        opened.append(packet['op'])
        offset = packet.get('offset', 0) + len(base64.b64decode(packet.get('pcm', '')))
        route.fulfill(json={'offset': offset, **({'text': '合成录音'} if packet['op'] == 'finish' else {})})

    def recorded(route):
        payload = VoiceRecording.model_validate(route.request.post_data_json)
        with wave.open(io.BytesIO(recorded_wave(payload)), 'rb') as audio:
            seconds = audio.getnframes() / audio.getframerate()
            assert seconds > .15
        uploads.append(payload.mime_type)
        route.fulfill(json={'text': '合成录音'})

    page.route('**/api/voice-input/stream?*', stream)
    page.route('**/api/voice-input/transcribe?*', recorded)
    button = lambda name: page.get_by_role('button', name=name, exact=True)
    page.goto(base + '/#/settings')
    menu = page.locator('#userMenuButton')
    expect(menu).to_be_enabled()
    menu.evaluate('button => { if (button.getAttribute("aria-expanded") !== "true") button.click(); }')
    page.locator('#identityButton').click()
    page.locator('#invitationCode').fill(invitation)
    page.locator('#identitySubmitButton').click()
    page.locator('#identitySubmitButton').wait_for(state='hidden')
    field = page.locator('#profileDisplayName')
    field.fill('')
    field.focus()
    button('录音输入').tap()
    try:
        button('结束录音').wait_for(timeout=8000)
    except Exception as error:
        state = page.evaluate("""() => ({status: document.querySelector('.voiceToolPanel [role=status]')?.textContent,
                                         micRequests: window.micCalls, audioState: window.testAudio?.state,
                                         mediaRecorder: typeof MediaRecorder})""")
        raise AssertionError(state) from error
    timer = page.locator('.voiceDuration:visible')
    assert timer.inner_text() == '00 分钟: 00 秒 / 2 分钟'
    bounds = timer.bounding_box()
    assert 0 <= bounds['x'] and bounds['x'] + bounds['width'] <= context.pages[0].viewport_size['width']
    expect(timer).to_have_text('00 分钟: 01 秒 / 2 分钟')
    button('暂停录音').click()
    paused = timer.inner_text()
    page.evaluate('window.clockAdvance += 5000')
    assert timer.inner_text() == paused
    button('继续录音').click()
    if use_limit:
        page.evaluate('window.clockAdvance += 120000')
        button('结束录音').wait_for(state='hidden')
    else:
        button('结束录音').click()
    expect(field).to_have_value('合成录音')
    assert page.evaluate('window.micCalls') == 1 and not errors, errors
    assert opened.count('finish') + len(uploads) == 1
    if fallback:
        assert not opened and uploads == (['audio/mp4'] if force_mp4 else ['audio/webm'])
    else:
        assert not uploads and opened[0] == 'open' and 'pause' in opened
    return {'fallback': fallback, 'media': uploads[0] if uploads else 'PCM', 'automatic_stop': use_limit}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('fixture', type=Path)
    cli.add_argument('base')
    cli.add_argument('--engine', choices=('chromium', 'webkit'), required=True)
    args = cli.parse_args()
    assert urlsplit(args.base).hostname in ('localhost', '127.0.0.1')
    invitation = (args.fixture / 'fixture-invitation.txt').read_text().strip()
    with sync_playwright() as playwright:
        webkit = args.engine == 'webkit'
        browser = getattr(playwright, args.engine).launch(**({} if webkit else {'channel': 'chrome'}))
        try:
            device = playwright.devices['iPhone 13' if webkit else 'Pixel 7'].copy()
            device.pop('default_browser_type')
            for fallback in ([True] if webkit else [False, True]):
                with browser.new_context(**device, locale='zh-CN') as context:
                    result = exercise(context, args.base, invitation, fallback, webkit, use_limit=True)
                    print(json.dumps({'engine': args.engine, **result}), flush=True)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
