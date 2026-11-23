"""Time synthesized speech through an isolated, fully configured website (Playwright)."""
import argparse
import base64
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

MIC = """
() => {
  Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {value: async () => {
    const clock = new AudioContext({sampleRate: 16000, latencyHint: 'interactive', sinkId: {type: 'none'}});
    await clock.resume();
    const sink = clock.createMediaStreamDestination();
    window.testMicrophone = {clock, sink};
    return sink.stream;
  }});
}
"""
PLAY = """
async encoded => {
  const {clock, sink} = window.testMicrophone;
  const raw = Uint8Array.from(atob(encoded), letter => letter.charCodeAt(0));
  const sample = await clock.decodeAudioData(raw.buffer);
  const values = sample.getChannelData(0);
  let end = values.length;
  while (end && Math.abs(values[end - 1]) * 32768 <= 40) end--;
  const source = clock.createBufferSource();
  source.buffer = sample; source.connect(sink);
  const answer = document.querySelector('#trainingAnswer');
  const start = clock.currentTime + .05, duration = end / sample.sampleRate;
  window.voiceTimes = {duration: Math.round(duration * 1000)};
  answer.addEventListener('input', () => {
    if (answer.value.trim() && !voiceTimes.inserted) voiceTimes.inserted = performance.now();
  });
  source.onended = () => {
    voiceTimes.voiceEnd = performance.now();
    setTimeout(() => {
      voiceTimes.stopped = performance.now();
      [...document.querySelectorAll('button')].find(b => b.textContent === '结束录音' && b.offsetWidth).click();
    }, 32);
  };
  source.start(start, 0, duration);
}
"""
RENDERED = """
() => {
  const field = document.querySelector('#trainingAnswer');
  if (!window.voiceTimes?.inserted || !field?.value) return false;
  const surface = field.form.querySelector('[data-formula-surface]:not([hidden])');
  const formula = surface?.querySelector('math-field');
  if (!formula || !formula.getBoundingClientRect().width) return false;
  if (!voiceTimes.framePending) {
    voiceTimes.framePending = true;
    requestAnimationFrame(() => requestAnimationFrame(() => { voiceTimes.painted = performance.now(); }));
  }
  return Boolean(voiceTimes.painted);
}
"""
CASES = {'algebra': ('variable', 'x+3-y'), 'pair': ('coordinate', '(-1,1)'),
         'iteration': ('script', 'y^{new}'), 'index': ('script', 'y_{6}'),
         'order': ('order', '7-3*2'), 'integral': ('integral', r'\intx^2+3\cdotx\,dx'),
         'reading-one': ('reading', 'q=5'), 'reading-two': ('reading', 'p=5'),
         'textbox-before': ('reading', 'm=5'), 'textbox-after': ('reading', 'n=5')}
TEXTBOX = {'textbox-before': ('更新后的读数用 m 表示。', '。'),
           'textbox-after': ('结果：', '。更新后的读数用 n 表示。')}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for key in ('fixture', 'audio', 'output'):
        cli.add_argument('--' + key, type=Path, required=True)
    cli.add_argument('--base', default='http://127.0.0.1:18791')
    cli.add_argument('--chromium')
    cli.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    args = cli.parse_args()
    if urlsplit(args.base).hostname not in ('127.0.0.1', 'localhost'):
        cli.error('Use a loopback synthetic fixture')
    evidence = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chromium, args=['--autoplay-policy=no-user-gesture-required'])
        page = browser.new_page(locale='zh-CN')
        page.add_init_script('(' + MIC + ')()')
        page.set_default_timeout(18000)
        try:
            def failed_request(response):
                path = urlsplit(response.url).path
                if path.startswith('/api/') and response.status >= 400:
                    print(f'fixture HTTP {response.status} {path}', flush=True)
            page.on('response', failed_request)
            page.goto(args.base + '/#/subjects/math/topic/calculator-fixture')
            page.get_by_role('button', name='下一页', exact=True).last.wait_for()
            page.locator('#userMenuButton').click()
            page.locator('#identityButton').click()
            page.locator('#invitationCode').fill((args.fixture / 'fixture-invitation.txt').read_text().strip())
            page.locator('#identitySubmitButton').click()
            page.locator('#identitySubmitButton').wait_for(state='hidden')
            packets = []
            def observe(request):
                if urlsplit(request.url).path == '/api/voice-input/stream' and request.method == 'POST':
                    body = request.post_data_json
                    packets.append(body['op'])
                    if body['op'] == 'open':
                        assert body['context']['stem'] and 'HIDDEN_REFERENCE' not in json.dumps(body)
            page.on('request', observe)
            for key in args.cases:
                clip, expected = CASES[key]
                packets.clear()
                page.goto(args.base + '/#/subjects/math/banks/isolated-bank/group-a?question=voice-' + key)
                answer = page.locator('#trainingAnswer')
                answer.wait_for()
                if key in TEXTBOX:
                    before, after = TEXTBOX[key]
                    answer.fill(before + '旧值' + after)
                    answer.evaluate('(el, p) => el.setSelectionRange(p, p+2)', len(before))
                answer.focus()
                page.get_by_role('button', name='录音输入', exact=True).click()
                page.get_by_role('button', name='结束录音', exact=True).wait_for()
                page.evaluate(PLAY, base64.b64encode((args.audio / (clip + '.wav')).read_bytes()).decode('ascii'))
                page.wait_for_function(RENDERED, timeout=35000)
                result = page.evaluate("""() => {const t=voiceTimes; return {speech_ms:t.duration,
                  end_to_paint_ms:Math.round(t.painted-t.voiceEnd), stop_to_paint_ms:Math.round(t.painted-t.stopped),
                  stop_to_input_ms:Math.round(t.inserted-t.stopped), text:document.querySelector('#trainingAnswer').value};}""")
                assert 'audio' in packets and 'finish' in packets and result['stop_to_input_ms'] >= 0, (key, packets, result)
                assert expected in result['text'].replace(' ', ''), (key, result)
                if key in TEXTBOX:
                    assert result['text'] == before + expected + after, (key, result)
                result.update(case=key, audio_posts=packets.count('audio'))
                evidence.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
        finally:
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
            browser.close()
    if any(row['end_to_paint_ms'] >= 1000 for row in evidence):
        raise SystemExit('Speech-end to painted answer exceeded one second.')


if __name__ == '__main__':
    main()
