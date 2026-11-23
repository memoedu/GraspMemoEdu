/** Render local Guide Markdown using the existing Marked/MathJax runtimes. */
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import {escapedAt, mathAt, mathSpans} from '../web/math-syntax.js';

const bundled = process.env.CODEX_NODE_MODULES || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const mathRuntime = process.env.MATH_TOPIC_PDF_RUNTIME || 'D:/Caches/MathTopicPdf/node_modules';
const guideRuntime = process.env.GRASPMEMOEDU_NODE_MODULES || 'D:/Caches/GraspMemoEdu/node-runtime/node_modules';
const br = createRequire(path.join(bundled, '_entry.cjs'));
const mr = createRequire(path.join(mathRuntime, '_entry.cjs'));
const gr = createRequire(path.join(guideRuntime, '_entry.cjs'));
const { Marked } = await import(pathToFileURL(br.resolve('marked')).href);
const sanitizeHtml = gr('sanitize-html');
const escape = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let adaptor, svg, document;
const formulas = [];
const resources = new Set();
const headings = new Map();
const ASSET_ROOT = 'https://guide-asset.invalid/';

function mathHtml(latex, display) {
  if (/\\(?:href|url|html\w*|includegraphics|class|style|cssId|require)\b/i.test(latex)) throw new Error('Active TeX is not supported');
  if (!document) {
    const { mathjax } = mr('mathjax-full/js/mathjax.js');
    const { TeX } = mr('mathjax-full/js/input/tex.js');
    const { SVG } = mr('mathjax-full/js/output/svg.js');
    const { liteAdaptor } = mr('mathjax-full/js/adaptors/liteAdaptor.js');
    const { RegisterHTMLHandler } = mr('mathjax-full/js/handlers/html.js');
    const { AllPackages } = mr('mathjax-full/js/input/tex/AllPackages.js');
    adaptor = liteAdaptor();
    RegisterHTMLHandler(adaptor);
    const tex = new TeX({
      packages: AllPackages.filter(name => !['noundefined', 'noerrors', 'html', 'require', 'autoload'].includes(name)),
      formatError: (_jax, error) => { throw error; }
    });
    svg = new SVG({ fontCache: 'none' });
    document = mathjax.document('', { InputJax: tex, OutputJax: svg });
  }
  const rendered = adaptor.outerHTML(document.convert(latex, { display, em: 15, ex: 7.5, containerWidth: 732 }));
  if (/data-mml-node="merror"|data-mjx-error|<(?:script|iframe|foreignObject|image)\b|\son\w+\s*=|(?:href|src)="(?:https?:|\/\/|data:|javascript:)|(?:url|expression)\s*\(|@import/i.test(rendered)) throw new Error('Invalid math');
  const tag = display ? 'div' : 'span';
  return `<${tag} class="${display ? 'mathDisplay' : 'mathInline'}" aria-label="${escape(latex)}">${rendered}</${tag}>`;
}

function math(latex, display) {
  const marker = `GUIDEMATHPLACEHOLDER${formulas.length}END`;
  formulas.push({marker, html: mathHtml(latex, display)});
  return display ? `<p>${marker}</p>\n` : marker;
}

const literal = value => escape(value).replace(/\r?\n/g, '<br>');

function normalizeAnswerMath(value) {
  // Some older structured answers persisted the transport escaping as text.
  // A real matrix's double backslashes are row boundaries.
  if (/\\\\begin\{[^{}]+\}[\s\S]*\\\\end\{/.test(value)) return value.replace(/\\\\/g, '\\');
  if (/\\begin\{|\\end\{/.test(value)) return value;
  return value.replace(/(?<!\\)\\\\(?=[A-Za-z()[\]])/g, '\\');
}

function bareAnswerMath(value) {
  if (/[$\x60\r\n]|<\/?[A-Za-z][^>]*>/.test(value)) return false;
  const symbols = value.trim().replace(/\\(?:text|textrm|operatorname)\{[^{}]*\}/g, 'λ')
    .replace(/\\[A-Za-z]+/g, 'λ').replace(/\b(?:sin|cos|tan|ln|log|exp)\b/g, 'λ');
  if (/(?:[A-Za-z]{2,}\s+[A-Za-z]{2,}|[^\x00-\x7FΑ-Ωα-ω×÷−≤≥≠±∞∈∫√∑π])/.test(symbols)) return false;
  if (!/\\[A-Za-z]+/.test(value) && !/\p{L}[\d\s]*(?:[=^_+*/<>≤≥≠-])|\d+[+\-*/=]\p{L}/u.test(symbols)) return false;
  return !/[A-Za-z]{3,}/.test(symbols) && /^[\d\p{L}\s+*/=^_{}()[\],.:;|!%&<>\-×÷−≤≥≠±∞∈∫√∑π\\]+$/u.test(symbols);
}

function answerTextHtml(value, allowBare = true) {
  const render = (tex, display, fallback) => {
    try { return mathHtml(normalizeAnswerMath(tex), display); }
    catch { return literal(fallback); }
  };
  const native = [...value.matchAll(/\[math\]([\s\S]+?)\[\/math\]/gi)]
    .filter(match => !escapedAt(value, match.index))
    .map(match => ({from: match.index, to: match.index + match[0].length, raw: match[0], latex: match[1], display: false}));
  const spans = [...mathSpans(value), ...native].sort((a, b) => a.from - b.from);
  if (!spans.length) {
    if (!allowBare) return literal(value);
    const candidate = normalizeAnswerMath(value).trim();
    const legacy = mathAt(candidate);
    if (legacy?.to === candidate.length) return render(legacy.latex, legacy.display, value);
    return bareAnswerMath(candidate) ? render(candidate, false, value) : literal(value);
  }
  let offset = 0, output = '';
  for (const {from, to, raw, latex, display} of spans) {
    if (from < offset) continue;
    output += literal(value.slice(offset, from)) + render(latex, display, raw);
    offset = to;
  }
  return output + literal(value.slice(offset));
}

function answerHtml(value) {
  if (!value.includes('\x60')) return answerTextHtml(value);
  let offset = 0, output = '';
  for (const match of value.matchAll(/(\x60+)[\s\S]*?\1(?!\x60)/g)) {
    output += answerTextHtml(value.slice(offset, match.index), false) + literal(match[0]);
    offset = match.index + match[0].length;
  }
  const last = value.slice(offset);
  const openCode = last.indexOf('\x60');
  return output + (openCode < 0 ? answerTextHtml(last, false)
    : answerTextHtml(last.slice(0, openCode), false) + literal(last.slice(openCode)));
}

function resourceUrl(raw, isImage) {
  const value = String(raw || '').trim();
  if (!value || /[\u0000-\u001f\\]/.test(value) || value.startsWith('//')) return '';
  if (value.startsWith('#')) return isImage ? '' : value;
  if (/^[a-z][a-z0-9+.-]*:/i.test(value)) {
    try {
      const url = new URL(value);
      if (url.username || url.password) return '';
      return (isImage ? url.protocol === 'https:' : ['https:', 'http:', 'mailto:'].includes(url.protocol)) ? url.href : '';
    } catch { return ''; }
  }
  let decoded;
  try { decoded = decodeURIComponent(value.split(/[?#]/)[0]); } catch { return ''; }
  if (decoded.startsWith('/') || /[\u0000-\u001f\\:]/.test(decoded)) return '';
  const pieces = decoded.split('/').filter(piece => piece && piece !== '.');
  if (!pieces.length || pieces.some(piece => piece === '..')) return '';
  const relative = pieces.join('/');
  const extension = path.posix.extname(relative).toLowerCase();
  if (!(isImage ? ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.bmp'] : ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.bmp', '.pdf', '.txt', '.csv']).includes(extension)) return '';
  resources.add(relative);
  return ASSET_ROOT + pieces.map(encodeURIComponent).join('/') + '?v=GUIDEASSETVERSION';
}

const marked = new Marked({
  gfm: true,
  renderer: {
    html(token) { return escape(token.text); },
    heading(token) {
      const slug = token.text.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, '').trim().replace(/\s+/g, '-') || 'section';
      const count = (headings.get(slug) || 0) + 1;
      headings.set(slug, count);
      return `<h${token.depth} id="${escape(slug + (count > 1 ? '-' + count : ''))}">${this.parser.parseInline(token.tokens)}</h${token.depth}>\n`;
    }
  },
  walkTokens(token) {
    if (token.type === 'image' || token.type === 'link') token.href = resourceUrl(token.href, token.type === 'image');
  },
  extensions: [{
    name: 'guideBlockMath', level: 'block',
    tokenizer(source) {
      const span = mathAt(source, 0, {allowUnbalanced: true});
      if (span?.display) return {type: 'guideBlockMath', ...span};
    },
    renderer(token) { return math(token.latex, true); }
  }, {
    name: 'guideInlineMath', level: 'inline',
    start(source) { return /\$|\\[([]|\\begin\{/.exec(source)?.index; },
    tokenizer(source) {
      const span = mathAt(source, 0, {allowUnbalanced: true});
      if (span) return {type: 'guideInlineMath', ...span};
    },
    renderer(token) { return math(token.latex, token.display); }
  }]
});

let input = '';
for await (const chunk of process.stdin) input += chunk;
const {markdown, answer_values} = JSON.parse(input);
if (Array.isArray(answer_values)) {
  if (Buffer.byteLength(input) > 1024 * 1024 || answer_values.some(value => typeof value !== 'string')) {
    throw new Error('Invalid answer render input');
  }
  const answer_html = answer_values.map(answerHtml);
  process.stdout.write(JSON.stringify({html: '', answer_html, resources: [],
    math_css: document ? adaptor.textContent(svg.styleSheet(document)) : ''}));
} else {
if (typeof markdown !== 'string' || Buffer.byteLength(markdown) > 1024 * 1024) throw new Error('Guide source is too large');
let html = sanitizeHtml(marked.parse(markdown), {
  allowedTags: [...sanitizeHtml.defaults.allowedTags, 'img', 'del', 'details', 'summary'],
  allowedAttributes: {
    a: ['href', 'title', 'target', 'rel'], img: ['src', 'alt', 'title', 'loading'],
    h1: ['id'], h2: ['id'], h3: ['id'], h4: ['id'], h5: ['id'], h6: ['id'],
    code: ['class'], th: ['align'], td: ['align']
  },
  allowedSchemes: ['http', 'https', 'mailto'],
  allowProtocolRelative: false,
  transformTags: {
    a: (_tag, attributes) => ({ tagName: 'a', attribs: { ...attributes, rel: 'noopener noreferrer', ...(attributes.href?.startsWith('#') ? {} : { target: '_blank' }) } }),
    img: (_tag, attributes) => ({ tagName: 'img', attribs: { ...attributes, loading: 'lazy' } })
  }
});
for (const formula of formulas) html = html.replaceAll(`<p>${formula.marker}</p>`, formula.html).replaceAll(formula.marker, formula.html);
process.stdout.write(JSON.stringify({ html, math_css: document ? adaptor.textContent(svg.styleSheet(document)) : '', resources: [...resources] }));
}
