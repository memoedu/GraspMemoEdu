"""Time synthesized speech through an isolated, fully configured website (Playwright)."""
import argparse
import base64
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

MIC = """
(delay) => {
  let loading;
  const addModule = AudioWorklet.prototype.addModule;
  AudioWorklet.prototype.addModule = async function (...args) {
    loading = performance.now();
    if (delay) await new Promise(done => setTimeout(done, delay));
    return addModule.apply(this, args);
  };
  document.addEventListener('click', event => {
    if (event.target.closest('button')?.getAttribute('aria-label') === '录音输入') {
      window.micTiming = {clicked: performance.now(), loading: null, microphone: null};
      const observer = new MutationObserver(() => {
        const stop = [...document.querySelectorAll('.voiceToolPanel button')].find(b => b.textContent === '结束录音');
        if (stop && !stop.hidden && stop.offsetWidth) {
          micTiming.ready = performance.now();
          micTiming.loading = loading >= micTiming.clicked ? loading : null;
          observer.disconnect();
        }
      });
      observer.observe(document.body, {subtree:true,attributes:true,childList:true,attributeFilter:['hidden']});
    }
  }, true);
  Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {value: async () => {
    micTiming.microphone = performance.now();
    if (delay) await new Promise(done => setTimeout(done, delay));
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
      voiceTimes.beforeStop = answer.value;
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
         'textbox-before': ('reading', 'm=5'), 'textbox-after': ('reading', 'n=5'),
         'vector-row': ('vector-row', r'\begin{pmatrix}1&2\end{pmatrix}'),
         'vector-column': ('vector-column', r'\begin{pmatrix}3\\1\end{pmatrix}'),
         'integral-bounds': ('integral-bounds', r'\int_{1}^{3}x^2+3\cdotx\,dx'),
         'partial': ('partial', r'\frac{\partialf}{\partialx}=6x+6'),
         'calculation': ('calculation', '2*3=7'), 'repair': ('repair', '12+38')}
TEXTBOX = {'textbox-before': ('更新后的读数用 m 表示。', '。'),
           'textbox-after': ('结果：', '。更新后的读数用 n 表示。')}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for key in ('fixture', 'audio', 'output'):
        cli.add_argument('--' + key, type=Path, required=True)
    cli.add_argument('--base', default='http://127.0.0.1:18791')
    cli.add_argument('--chromium')
    cli.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    cli.add_argument('--transport', choices=('background', 'file', 'legacy'), default='background')
    cli.add_argument('--setup-delay-ms', type=int, default=0, help='Inject the same latency into permission and worklet loading')
    args = cli.parse_args()
    if urlsplit(args.base).hostname not in ('127.0.0.1', 'localhost'):
        cli.error('Use a loopback synthetic fixture')
    evidence = []
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chromium, args=['--autoplay-policy=no-user-gesture-required'])
        page = browser.new_page(locale='zh-CN')
        page.add_init_script(f'({MIC})({args.setup_delay_ms})')
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
                api = '/api/voice-input/transcribe' if args.transport == 'file' else '/api/voice-input/stream'
                if urlsplit(request.url).path == api and request.method == 'POST':
                    body = request.post_data_json
                    packets.append(body)
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
                timing = page.evaluate('micTiming')
                page.evaluate(PLAY, base64.b64encode((args.audio / (clip + '.wav')).read_bytes()).decode('ascii'))
                try:
                    page.wait_for_function(RENDERED, timeout=35000)
                except Exception as error:
                    result = {'case': key, 'error': 'Formula did not display',
                              'status': page.locator('.voiceToolPanel [role="status"]').text_content(),
                              'text': answer.input_value()}
                    evidence.append(result)
                    failures.append(key)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                    continue
                result = page.evaluate("""() => {const t=voiceTimes; return {speech_ms:t.duration,
                  end_to_paint_ms:Math.round(t.painted-t.voiceEnd), stop_to_paint_ms:Math.round(t.painted-t.stopped),
                  stop_to_input_ms:Math.round(t.inserted-t.stopped), beforeStop:t.beforeStop,
                  text:document.querySelector('#trainingAnswer').value};}""")
                if args.transport != 'file':
                    assert any(packet.get('op') == 'finish' for packet in packets), key
                    if args.transport == 'background':
                        assert packets[0]['manual'] and any(packet.get('op') == 'audio' for packet in packets), key
                        assert result['beforeStop'] == (before + '旧值' + after if key in TEXTBOX else ''), key
                else:
                    assert len(packets) == 1 and packets[0]['segmented'], key
                assert result['stop_to_input_ms'] >= 0 and packets[0]['context']['stem']
                assert 'HIDDEN_REFERENCE' not in json.dumps(packets[0]['context'])
                rendered = result['text'].replace(' ', '')
                rendered = re.sub(r'\\int_([0-9])\^([0-9])', r'\\int_{\1}^{\2}', rendered)
                rendered = rendered.replace('6\\cdotx', '6x').replace(r'\left(\begin{matrix}', r'\begin{pmatrix}')
                rendered = rendered.replace(r'\end{matrix}\right)', r'\end{pmatrix}')
                if key in ('integral', 'integral-bounds'):
                    # Both multiplication spellings and grouping of the whole integrand are equivalent.
                    rendered = re.sub(r'(?<=\d)(?=[a-z])', lambda _: r'\cdot', rendered)
                    rendered = re.sub(
                        r'(\\int(?:_\{[^}]+\}\^\{[^}]+\})?)(?:\\left)?\(([^()]+?)(?:\\right)?\)(?=\\,d)',
                        r'\1\2', rendered)
                passed = expected in rendered
                if key == 'repair':
                    passed &= '36' not in rendered and '不对' not in rendered
                if key in TEXTBOX:
                    passed &= result['text'] == before + expected + after
                if not passed: failures.append(key)
                assert timing['ready'] >= timing['clicked']
                setup_gap = (round(timing['loading'] - timing['microphone'])
                             if timing['loading'] is not None and timing['microphone'] is not None else None)
                result.update(case=key, audio_posts=len(packets), mic_open_ms=round(timing['ready']-timing['clicked']),
                              mic_reused=timing['microphone'] is None, setup_gap_ms=setup_gap, passed=passed)
                evidence.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
        finally:
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
            browser.close()
    if failures:
        raise SystemExit('Failed voice cases: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
