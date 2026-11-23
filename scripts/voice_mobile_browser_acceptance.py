"""Exercise recording limits and real mobile-browser media containers on a loopback site."""
import argparse
import base64
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import wave

from playwright.sync_api import expect, sync_playwright

from graspmemoedu.voice_input import VoiceRecording, recorded_wave


MICROPHONE = """
([fallback, forceMp4, mp4Fixture]) => {
  window.micCalls = 0;
  if ('serviceWorker' in navigator) navigator.serviceWorker.register = async () => null;
  window.fixtureRecorder = typeof MediaRecorder === 'undefined';
  if (!navigator.mediaDevices) Object.defineProperty(navigator, 'mediaDevices', {value: {}});
  if (window.fixtureRecorder && mp4Fixture) {
    // The Windows WebKit test port can lack a native media encoder.
    // Keep the browser UI and actual backend decoder in the test.
    globalThis.AudioWorkletNode = undefined;
    globalThis.MediaRecorder = class extends EventTarget {
      static isTypeSupported(type) { return type === 'audio/mp4'; }
      mimeType = 'audio/mp4';
      state = 'inactive';
      start() { this.state = 'recording'; }
      pause() { this.state = 'paused'; }
      resume() { this.state = 'recording'; }
      stop() {
        this.state = 'inactive';
        const bytes = Uint8Array.from(atob(mp4Fixture), char => char.charCodeAt(0));
        this.dispatchEvent(Object.assign(new Event('dataavailable'), {data: new Blob([bytes], {type: this.mimeType})}));
        this.dispatchEvent(new Event('stop'));
      }
    };
  }
  Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {value: async () => {
    window.micCalls++;
    if (window.fixtureRecorder && mp4Fixture) {
      const track = Object.assign(new EventTarget(), {stop() {}});
      return {active: true, getTracks: () => [track], getAudioTracks: () => [track]};
    }
    const audio = new AudioContext();
    window.testAudio = audio;
    if (audio.state !== 'running') await audio.resume();
    const tone = audio.createOscillator(), sink = audio.createMediaStreamDestination();
    tone.connect(sink); tone.start();
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


def exercise(context, base, invitation, fallback, force_mp4, mp4_fixture, *, use_limit):
    context.add_init_script(f'({MICROPHONE})({json.dumps([fallback, force_mp4, mp4_fixture])})')
    page = context.new_page()
    opened, uploads, errors = [], [], []
    frames = bytearray()
    offset = part = 0
    page.on('pageerror', lambda error: errors.append(str(error)))

    def stream(route):
        nonlocal offset, part
        packet = route.request.post_data_json
        operation = packet['op']
        opened.append(operation)
        if operation == 'open':
            assert packet['manual'] and packet['independent']
            route.fulfill(json={'offset': 0})
            return
        assert packet['offset'] == offset and packet['part'] == part
        pcm = base64.b64decode(packet['pcm'])
        frames.extend(pcm)
        offset += len(pcm)
        if operation in ('cut', 'finish'):
            assert len(frames) > 4800
            frames.clear()
            uploads.append('audio/wav')
            route.fulfill(json={'offset': offset, 'text': '第一段' if len(uploads) == 1 else '第二段'})
            offset = 0
            part += 1
        else:
            route.fulfill(json={'offset': offset})

    def recorded(route):
        payload = VoiceRecording.model_validate(route.request.post_data_json)
        assert payload.segmented
        with wave.open(io.BytesIO(recorded_wave(payload)), 'rb') as audio:
            seconds = audio.getnframes() / audio.getframerate()
            assert seconds > .15
        uploads.append(payload.mime_type)
        route.fulfill(json={'text': '第一段' if len(uploads) == 1 else '第二段'})

    page.route(re.compile(r'/api/voice-input/stream(?:\?|$)'), stream)
    page.route(re.compile(r'/api/voice-input/transcribe(?:\?|$)'), recorded)
    button = lambda name: page.get_by_role('button', name=name, exact=True)
    page.goto(base + '/#/settings')
    # Use a synthetic fixture account. The test exercises the microphone UI,
    # independently of menu animations and synthetic touch event ordering.
    page.evaluate("""async invitation => {
      const session = await (await fetch('/api/session')).json();
      const login = await fetch('/api/access/login', {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Learning-Session': session.session_token},
        body: JSON.stringify({invitation_code: invitation})});
      if (!login.ok) throw Error('Fixture login failed ' + login.status);
      localStorage.setItem('graspmemoedu:identity:' + location.origin, (await login.json()).identity_token);
      localStorage.setItem('graspmemoedu:identity-role:' + location.origin, 'account');
    }""", invitation)
    page.reload()
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
    assert not uploads
    assert ('audio' in opened) != fallback
    button('暂停录音').click()
    paused = timer.inner_text()
    page.evaluate('window.clockAdvance += 5000')
    assert timer.inner_text() == paused
    assert not uploads
    button('转写').tap()
    expect(field).to_have_value('第一段')
    expect(timer).to_have_text('00 分钟: 00 秒 / 2 分钟')
    button('继续录音').click()
    expect(timer).to_have_text('00 分钟: 01 秒 / 2 分钟')
    if use_limit:
        page.evaluate('window.clockAdvance += 120000')
        button('结束录音').wait_for(state='hidden')
    else:
        button('结束录音').click()
    try:
        expect(field).to_have_value('第一段第二段')
    except AssertionError as error:
        status = page.locator('.voiceToolPanel [role="status"]').text_content()
        raise AssertionError((status, opened, uploads, errors)) from error
    assert page.evaluate('window.micCalls') == 1 and not errors, errors
    assert (not opened) == fallback
    assert uploads == [('audio/mp4' if force_mp4 else 'audio/webm') if fallback else 'audio/wav'] * 2
    return {'fallback': fallback, 'media': uploads[0], 'automatic_stop': use_limit,
            'fixture_encoder': page.evaluate('window.fixtureRecorder')}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('fixture', type=Path)
    cli.add_argument('base')
    cli.add_argument('--engine', choices=('chromium', 'webkit'), required=True)
    cli.add_argument('--mp4-fixture', type=Path, help='Use these synthetic AAC/MP4 bytes if the WebKit port lacks an encoder')
    args = cli.parse_args()
    assert urlsplit(args.base).hostname in ('localhost', '127.0.0.1')
    invitation = (args.fixture / 'fixture-invitation.txt').read_text().strip()
    mp4_fixture = base64.b64encode(args.mp4_fixture.read_bytes()).decode() if args.mp4_fixture else None
    with sync_playwright() as playwright:
        webkit = args.engine == 'webkit'
        browser = getattr(playwright, args.engine).launch(**({} if webkit else {'channel': 'chrome'}))
        try:
            device = playwright.devices['iPhone 13' if webkit else 'Pixel 7'].copy()
            device.pop('default_browser_type')
            modes = [(True, True)] if webkit else [(False, False), (True, False), (True, True)]
            for fallback, force_mp4 in modes:
                with browser.new_context(**device, locale='zh-CN') as context:
                    result = exercise(context, args.base, invitation, fallback, force_mp4, mp4_fixture, use_limit=True)
                    print(json.dumps({'engine': args.engine, **result}), flush=True)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
