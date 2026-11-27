const SAMPLE = '昨日は朝ごはんを食べませんでした。水も飲みませんでした。夕方、店に行きました。でも、パンは買いませんでした。';
let draft = SAMPLE;

function showDetails(details, segment) {
  const title = document.createElement('h3');
  title.className = 'cardTitle';
  title.textContent = segment.kind === 'word' ? segment.lemma : segment.text;
  const note = document.createElement('p');

  if (segment.kind === 'word') {
    title.lang = 'ja';
    const word = [segment.reading, segment.gloss].filter(Boolean).join(' · ');
    note.textContent = word || '已识别词典形';
    if (segment.text !== segment.lemma) {
      note.append(`（原文：${segment.text}）`);
    }
    details.replaceChildren(title, note);
    return;
  }

  note.textContent = segment.label;
  const breakdown = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = '查看语素拆分';
  const parts = document.createElement('ul');
  for (const part of segment.parts) {
    const row = document.createElement('li');
    const surface = document.createElement('span');
    surface.lang = 'ja';
    surface.textContent = part.text;
    row.append(surface, ` · ${part.explanation}`);
    parts.append(row);
  }
  breakdown.append(summary, parts);
  details.replaceChildren(title, note, breakdown);
}

export function renderReadingView(host) {
  const panel = document.createElement('section');
  panel.className = 'panelCard readingPanel';
  panel.innerHTML = `
    <h1 class="pageTitle">阅读分析</h1>
    <form class="readingForm">
      <label for="readingText">日文原文</label>
      <textarea id="readingText" class="readingInput" lang="ja" rows="4" maxlength="2000" required></textarea>
      <div class="actionRow">
        <button class="btn btn--primary" type="submit">分析原文</button>
        <button class="btn btn--ghost" type="button" data-load-example>载入例句</button>
      </div>
    </form>
    <div class="readingStatus mutedText" role="status"></div>
    <a class="readingLesson" hidden>前往丁寧語</a>
    <p class="readingText" lang="ja" hidden></p>
    <div class="readingDetails" aria-live="polite" hidden></div>
  `;
  host.replaceChildren(panel);
  const form = panel.querySelector('form');
  const input = panel.querySelector('textarea');
  const status = panel.querySelector('.readingStatus');
  const lesson = panel.querySelector('.readingLesson');
  const result = panel.querySelector('.readingText');
  const details = panel.querySelector('.readingDetails');
  let pending;
  input.value = draft;

  function clearResult() {
    pending?.abort();
    status.textContent = '';
    result.hidden = true;
    details.hidden = true;
    lesson.hidden = true;
  }

  async function analyze() {
    clearResult();
    const controller = new AbortController();
    pending = controller;
    status.textContent = '正在分析日文…';
    try {
      const response = await fetch('/api/reading/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: input.value }),
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message || '分析失败，请重试。');
      if (!panel.isConnected || controller.signal.aborted) return;
      result.replaceChildren();
      for (const segment of data.segments) {
        if (segment.kind === 'text') {
          result.append(segment.text);
          continue;
        }
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `readingToken${segment.kind === 'grammar' ? ' readingToken--grammar' : ''}`;
        button.textContent = segment.text;
        button.addEventListener('click', () => {
          result.querySelector('[aria-pressed="true"]')?.setAttribute('aria-pressed', 'false');
          button.setAttribute('aria-pressed', 'true');
          details.hidden = false;
          showDetails(details, segment);
        });
        button.setAttribute('aria-pressed', 'false');
        result.append(button);
      }
      result.hidden = false;
      const links = result.querySelector('button');
      status.textContent = links ? '点击带下划线的词查原形和读音。' : '这段文本没有可查词的日文词条。';
      if (data.lesson_url) {
        if (!data.grammar_ready) {
          status.append(' 学完「动词礼貌体的四种形式」后即可查看动词句尾提示。');
        } else if (result.querySelector('.readingToken--grammar')) {
          status.append(' 也可以点击带底色的动词礼貌句尾。');
        }
        lesson.href = data.lesson_url;
        lesson.hidden = false;
      } else {
        status.append(' 关联本机丁寧語进度后可查看语法提示。');
      }
    } catch (error) {
      if (panel.isConnected && !controller.signal.aborted) {
        status.textContent = error.message || '分析失败，请重试。';
      }
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    analyze();
  });
  input.addEventListener('input', () => {
    draft = input.value;
    clearResult();
  });
  panel.querySelector('[data-load-example]').addEventListener('click', () => {
    draft = SAMPLE;
    input.value = SAMPLE;
    analyze();
  });
  if (input.value.trim()) analyze();
}

renderReadingView(document.querySelector('#readingApp'));
