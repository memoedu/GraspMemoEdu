import {Editor, defaultValueCtx, editorViewCtx, editorViewOptionsCtx, rootCtx} from '@milkdown/core';
import {docSchema, paragraphAttr, paragraphSchema, textSchema} from '@milkdown/preset-commonmark';
import {$node, $prose} from '@milkdown/utils';
import {baseKeymap} from '@milkdown/prose/commands';
import {history, closeHistory, redo, undo} from '@milkdown/prose/history';
import {keymap} from '@milkdown/prose/keymap';
import {Slice} from '@milkdown/prose/model';
import {NodeSelection, Plugin, TextSelection} from '@milkdown/prose/state';
import {MathfieldElement, convertAsciiMathToLatex, convertLatexToAsciiMath, validateLatex} from 'mathlive';
import {unified} from 'unified';
import {unifiedLatexFromString} from '@unified-latex/unified-latex-util-parse';
import {printRaw} from '@unified-latex/unified-latex-util-print-raw';
import {lints} from '@unified-latex/unified-latex-lint';
import katex from 'katex';
import {bareMathRuns, followingArgument, formulaSpans, formulaToken} from '../../web/formula-catalog.js';

MathfieldElement.fontsDirectory = new URL('./fonts/', import.meta.url).href;
MathfieldElement.soundsDirectory = null;

const mathType = 'site_formula';
const sourceLatex = latex => latex.replaceAll('\\placeholder{}', '');
const wrap = (latex, display = false) => display ? '\\[' + latex + '\\]' : '\\(' + latex + '\\)';
const asText = node => node.attrs.raw ?? (sourceLatex(node.attrs.latex).trim() ? wrap(sourceLatex(node.attrs.latex), node.attrs.display) : '');
function serialize(doc) {
  const paragraphs = [];
  doc.forEach(row => paragraphs.push(row.textBetween(0, row.content.size, '', asText)));
  return paragraphs.join('\n');
}
const displayable = latex => typeof latex === 'string' && latex.length <= 4000
  && !/\\(?:html\w*|css\w*|includegraphics|href|url|style|class|def|gdef|edef|newcommand|renewcommand)\b/i.test(latex);
const safe = latex => displayable(latex) && validateLatex(latex).length === 0;

function bareLatex(raw) {
  if (raw.includes('\\')) return raw;
  // MathLive's ASCII parser uses parentheses for script groups; TeX uses braces.
  const ascii = raw.replace(/[{}]/g, char => char === '{' ? '(' : ')');
  const latex = convertAsciiMathToLatex(ascii);
  return latex.replace(/\\left\\lfloor#\?\\right\\rfloor\s*\\left\(/g, '\\operatorname{floor}\\left(')
    .replace(/\\left\\lceil#\?\\right\\rceil\s*\\left\(/g, '\\operatorname{ceil}\\left(');
}

// Incomplete ASCII structures open a real MathLive slot, including the second
// argument of a fraction. Incomplete TeX commands remain editable until valid.
function inlineMath(raw) {
  if (!/[\\α-ωΑ-Ω√∞≤≥≠±×÷−+*/^_!=()[\]{}|<>-]/.test(raw)) return null;
  if (!/[A-Za-z0-9α-ωΑ-Ω√∞]/.test(raw)) return null;
  const format = raw.includes('\\') ? 'latex' : 'ascii';
  let latex;
  if (format === 'latex') {
    if (!safe(raw) || /(?:\{\}|[+*=<>-])$/.test(raw)) return null;
    try {
      katex.renderToString(raw, {trust: false, strict: 'ignore', throwOnError: true, maxExpand: 100, maxSize: 10});
    } catch { return null; }
    latex = raw;
  } else {
    const script = raw.match(/^(.+?)([\^_])(?:\{\})?$/);
    if (script) latex = bareLatex(script[1]) + script[2] + '{\\placeholder{}}';
    else if (raw.endsWith('/')) latex = '\\frac{' + bareLatex(raw.slice(0, -1)) + '}{\\placeholder{}}';
    else if (/[+*=<>-]$/.test(raw)) return null;
    else latex = bareLatex(raw).replace(/\\left\(\s*\\right\)/g, '\\left(\\placeholder{}\\right)');
  }
  return latex && safe(latex) ? {latex, format} : null;
}

export function answerMathSpans(value) {
  const spans = [];
  let start = 0;
  function bare(end) {
    const section = value.slice(start, end);
    const environment = section.trim();
    if (/^\\begin\{([A-Za-z*]+)\}[\s\S]*\\end\{\1\}$/.test(environment) && inlineMath(environment)) {
      const from = start + section.indexOf(environment);
      spans.push({from, to: from + environment.length, raw: environment, latex: environment, format: 'latex'});
      return;
    }
    // Keep an unfinished explicit delimiter and its contents together.
    if (/(?:^|[^\\])(?:\$|\\[(\[])/.test(section)) return;
    for (const item of bareMathRuns(section)) {
      const formula = inlineMath(item.raw);
      if (formula) spans.push({...item, ...formula, from: start + item.from, to: start + item.to});
    }
  }
  for (const span of formulaSpans(value)) {
    bare(span.from);
    if (safe(span.latex)) spans.push(span);
    start = span.to;
  }
  bare(value.length);
  return spans;
}

function asciiValue(latex, groupScripts = false) {
  let ascii = convertLatexToAsciiMath(sourceLatex(latex)).replaceAll('❓', '').replace(/\b([a-z]+) +\(/gi, '$1(');
  // MathLive wraps fraction operands and scripts. Simple exact answers keep the
  // familiar keyboard spelling while compound operands retain their grouping.
  ascii = ascii.replace(/\(([\w.]+)\)(?=\/)/g, '$1').replace(/\/\(([\w.]+)\)/g, '/$1');
  for (let i = ascii.length - 2; i >= 0; i--) {
    if (!'^_'.includes(ascii[i])) continue;
    const arg = followingArgument(ascii, i + 1);
    if (arg) {
      const value = !groupScripts && (/^[a-z]$|^\d+$/i.test(arg.body)) ? arg.body : '{' + arg.body + '}';
      ascii = ascii.slice(0, i + 1) + value + ascii.slice(arg.end);
    }
  }
  return ascii;
}

const formulaSchema = $node(mathType, () => ({
  inline: true, group: 'inline', atom: true, selectable: true,
  attrs: {latex: {default: ''}, display: {default: false}, raw: {default: null}, format: {default: null}},
  parseDOM: [{tag: 'span[data-site-latex]', getAttrs(dom) {
    const latex = dom.getAttribute('data-site-latex');
    return safe(latex) ? {latex, display: dom.hasAttribute('data-display')} : false;
  }}],
  toDOM: node => ['span', {'data-site-latex': sourceLatex(node.attrs.latex),
    ...(node.attrs.display ? {'data-display': ''} : {})}, asText(node)],
  parseMarkdown: {match: () => false, runner() {}},
  toMarkdown: {match: node => node.type.name === mathType,
    runner: (state, node) => state.addNode('text', undefined, asText(node))},
}));

function formulaAttrs(part, prose) {
  if (prose && part.format === 'latex') return {latex: part.latex, display: false};
  return {latex: part.latex, display: part.display, raw: part.raw, format: part.format};
}

function documentJSON(text, detectBare = false, prose = false) {
  const rows = [[]];
  function plain(value) {
    value.split('\n').forEach((part, index) => {
      if (index) rows.push([]);
      if (part) rows.at(-1).push({type: 'text', text: part});
    });
  }
  let from = 0;
  for (const match of detectBare ? answerMathSpans(text) : formulaSpans(text)) {
    if (prose && match.format === 'ascii' || !safe(match.latex)) continue;
    plain(text.slice(from, match.from));
    rows.at(-1).push({type: mathType, attrs: formulaAttrs(match, prose)});
    from = match.to;
  }
  plain(text.slice(from));
  return {type: 'doc', content: rows.map(content => ({type: 'paragraph', content}))};
}

function sourcePosition(doc, offset) {
  let remaining = offset, position = 1, found = false;
  doc.forEach((row, rowPos) => {
    if (found) return;
    position = rowPos + 1;
    row.forEach((node, offsetInRow) => {
      if (found) return;
      const length = node.isText ? node.text.length : asText(node).length;
      if (remaining < length || remaining === 0) {
        position = rowPos + 1 + offsetInRow + (node.isText ? remaining : 0);
        found = true;
      } else {
        remaining -= length;
        position += node.nodeSize;
      }
    });
    if (!found && remaining-- <= 0) found = true;
  });
  return position;
}

const lint = unified().use(unifiedLatexFromString).use(lints.unifiedLatexLintNoPlaintextOperators, {fix: true}).freeze();
function editedLatex(latex) {
  const value = sourceLatex(latex);
  // MathLive may serialize a fraction as \frac37. The TeX parser restores
  // argument groups for the form value, including nested and single-digit slots.
  try { return printRaw(lint.parse(wrap(value)).content[0].content); }
  catch { return value; }
}
const operator = /(?<![a-z\\])(?:sin|cos|tan|ln|log|exp|lim|max|min)(?![a-z])/i;
function fixOperator(source) {
  if (source.length > 220 || !operator.test(source)) return null;
  try {
    const tree = lint.parse(wrap(source));
    lint.runSync(tree);
    if (tree.content.length !== 1 || !Array.isArray(tree.content[0].content)) return null;
    const fixed = printRaw(tree.content[0].content);
    return fixed !== source && safe(fixed) ? fixed : null;
  } catch { return null; }
}

export async function createFormulaEditor(host, options) {
  const previewCache = new Map();
  function preview(latex) {
    if (previewCache.has(latex)) return previewCache.get(latex);
    let html = '';
    try {
      html = katex.renderToString(latex, {
        trust: false, throwOnError: true, maxExpand: 100, maxSize: 10, strict: 'ignore', output: 'html',
      });
    } catch { /* Unsupported fragments stay in the source editor. */ }
    if (previewCache.size >= 64) previewCache.delete(previewCache.keys().next().value);
    previewCache.set(latex, html);
    return html;
  }
  function correction(source) {
    if (!source || source.length > 220) return [];
    const fraction = source.match(/^([a-z0-9]+)\s*\/\s*([a-z0-9]+)$/i);
    const latex = fraction ? '\\frac{' + fraction[1] + '}{' + fraction[2] + '}' : fixOperator(source);
    if (!latex) return [];
    const html = preview(latex);
    return html ? [{label: fraction ? options.fraction : options.operator, latex, preview: html}] : [];
  }

  let view, recognitionTimer;
  const update = $prose(() => new Plugin({
    filterTransaction(tr) {
      return !tr.docChanged || tr.getMeta('sourceSync') || options.enabled() && serialize(tr.doc).length <= options.maxLength();
    },
  }));
  const editor = await Editor.make().config(ctx => {
    ctx.set(rootCtx, host);
    ctx.set(defaultValueCtx, {type: 'json', value: documentJSON(options.value(), options.detectInitialBare, !options.answer)});
    ctx.set(editorViewOptionsCtx, {
      editable: options.enabled,
      attributes: {role: 'textbox', 'aria-multiline': 'true', 'aria-label': options.label, spellcheck: 'false'},
      nodeViews: {[mathType]: mathView},
      dispatchTransaction(tr) {
        const result = this.state.applyTransaction(tr);
        this.updateState(result.state);
        const changed = result.transactions.some(transaction => transaction.docChanged);
        if (changed && !tr.getMeta('sourceSync')) options.change(serialize(this.state.doc));
        if (changed || tr.selectionSet) {
          clearTimeout(recognitionTimer);
          if (!tr.getMeta('sourceSync') && this.state.selection.empty && this.state.selection.$from.nodeBefore?.isText)
            recognitionTimer = setTimeout(promoteTypedRun, 180);
          queueMicrotask(() => {
            if (!this.composing && host.isConnected) options.refresh(this.dom);
          });
        }
      },
      clipboardTextSerializer(slice) { return slice.content.textBetween(0, slice.content.size, '\n', asText); },
      handlePaste(view, event) {
        const text = event.clipboardData?.getData('text/plain');
        if (!text) return false;
        const doc = view.state.schema.nodeFromJSON(documentJSON(text, true, !options.answer));
        view.dispatch(closeHistory(view.state.tr.replaceSelection(Slice.maxOpen(doc.content))));
        return true;
      },
      handleTextInput(view, from, to, text) {
        const start = view.state.doc.resolve(from);
        const prefix = start.parent.textBetween(0, start.parentOffset, '', () => '\uFFFC');
        if (view.composing) return false;
        if (text.length > 1) {
          const spans = answerMathSpans(text);
          if (!spans.some(part => options.answer || part.format !== 'ascii')) return false;
          const doc = view.state.schema.nodeFromJSON(documentJSON(text, true, !options.answer));
          view.dispatch(view.state.tr.replaceRange(from, to, Slice.maxOpen(doc.content)));
          return true;
        }
        const before = prefix + text;
        if (!/[\\$]/.test(prefix) && options.answer && ['(', '[', '^', '_', '/'].includes(text)) {
          const base = bareMathRuns(prefix).at(-1);
          const name = prefix.match(/[A-Za-z]+$/)?.[0];
          const fn = text === '(' && name && options.candidates(name).find(item => item.label === name);
          const previous = base?.to === prefix.length ? base.raw : '';
          if (!previous && !fn && text === '/') return false;
          const operand = previous ? bareLatex(previous) : '';
          const template = {'(': operand + '\\left(#?\\right)', '[': operand + '\\left[#?\\right]',
            '^': operand + '^{#?}', '_': operand + '_{#?}', '/': '\\frac{' + operand + '}{#?}'};
          insertFormula(from - (fn ? name.length : previous.length), to,
            {latex: fn?.latex || template[text], format: 'ascii'});
          return true;
        }
        if (!/[$)\]}\s]$/.test(text) && !options.answer) return false;
        const trailing = before.trimEnd();
        if (/\\[A-Za-z]+$/.test(trailing) && before === trailing) return false;
        const match = answerMathSpans(trailing).at(-1);
        if (!match || !options.answer && match.format === 'ascii' || match.to !== trailing.length || match.raw.includes('\uFFFC')) return false;
        const pos = from - (before.length - match.from - text.length);
        const node = view.state.schema.nodes[mathType].create(formulaAttrs(match, !options.answer));
        const tr = view.state.tr.replaceWith(pos, to, node);
        if (trailing.length < before.length) tr.insertText(before.slice(trailing.length), pos + 1);
        view.dispatch(tr);
        if (match.format && before === trailing) enterFormula(pos, false);
        return true;
      },
    });
  }).use([docSchema, paragraphAttr, ...paragraphSchema, textSchema, formulaSchema, update,
    $prose(() => history()), $prose(() => keymap({'Mod-z': undo, 'Mod-Shift-z': redo, 'Mod-y': redo, ...baseKeymap}))
  ]).create();
  view = editor.action(ctx => ctx.get(editorViewCtx));
  function promoteTypedRun(controlWordOnly = true) {
    if (!view?.hasFocus() || view.composing || !options.enabled()) return;
    const {selection, schema} = view.state, text = selection.$from.nodeBefore?.text;
    if (!selection.empty || !text || controlWordOnly && !/\\[a-z]+$/i.test(text)) return;
    const part = answerMathSpans(text).at(-1);
    if (!part || !options.answer && part.format === 'ascii' || part.to !== text.length) return;
    const pos = selection.from - part.raw.length;
    view.dispatch(view.state.tr.replaceWith(pos, selection.to, schema.nodes[mathType].create(formulaAttrs(part, !options.answer))));
    enterFormula(pos, false);
  }

  const typedClosers = new WeakSet();

  function mathView(node, view, getPos) {
    const math = document.createElement('math-field');
    const dom = document.createElement('span');
    dom.className = 'siteFormula';
    dom.classList.toggle('siteFormulaDisplay', node.attrs.display);
    dom.contentEditable = 'false';
    math.setAttribute('aria-label', options.formula);
    math.setAttribute('math-virtual-keyboard-policy', 'manual');
    math.popoverPolicy = 'off';
    math.readOnly = !options.enabled();
    math.defaultMode = node.attrs.display ? 'math' : 'inline-math';
    math.smartFence = true;
    math.smartSuperscript = false;
    math.onExport = (_, latex) => wrap(latex, node.attrs.display);
    math.value = node.attrs.latex;
    dom.append(math);

    let groupedScripts = !options.literal || /[\^_]\{/.test(node.attrs.raw || '');
    function writeMath() {
      const pos = getPos();
      if (pos === undefined || !options.enabled()) return;
      const latex = math.value;
      if (latex === node.attrs.latex) return;
      if (!latex) {
        const focused = document.activeElement === math;
        const tr = view.state.tr.delete(pos, pos + node.nodeSize);
        tr.setSelection(TextSelection.create(tr.doc, pos));
        view.dispatch(closeHistory(tr));
        if (focused) view.focus();
        return;
      }
      const format = node.attrs.format;
      const value = format === 'ascii' ? asciiValue(latex, groupedScripts) :
        format === 'latex' ? editedLatex(latex) : null;
      const raw = {...node.attrs, latex, raw: value};
      const tr = view.state.tr.setNodeMarkup(pos, null, raw);
      if (serialize(tr.doc).length > options.maxLength()) {
        math.setValue(node.attrs.latex, {silenceNotifications: true});
        return;
      }
      view.dispatch(tr);
    }
    // A typed TeX brace immediately after ^ or _ describes the group MathLive
    // already opened. Consume its closing brace by moving out of that group.
    let explicitScript = false;
    math.addEventListener('keydown', event => {
      if (event.isComposing || event.defaultPrevented || math.mode === 'latex') return;
      if (event.key === '{' && /[\^_]\{(?:\\placeholder\{\})?\}/.test(math.value)
        && (math.getValue(math.selection, 'latex').includes('\\placeholder') || math.getElementInfo(math.position)?.depth > 0)) {
        explicitScript = true;
        groupedScripts = true;
        event.preventDefault(); event.stopImmediatePropagation();
      } else if (event.key === '}' && (explicitScript || typedClosers.has(math))) {
        typedClosers.delete(math);
        explicitScript = false;
        event.preventDefault(); event.stopImmediatePropagation();
        math.executeCommand('moveAfterParent');
      }
    }, true);
    math.addEventListener('input', () => {
      writeMath();
      options.refresh(math);
    });
    math.addEventListener('change', writeMath);
    math.addEventListener('selection-change', () => options.refresh(math));
    const detach = options.register(math, () => {
      if (!options.enabled() || getPos() === undefined || math.mode === 'latex') return null;
      const selection = math.selection, latex = math.value;
      if (selection.ranges.length !== 1) return null;
      const [from, to] = selection.ranges[0];
      const signature = JSON.stringify(selection);
      const before = from === to ? math.getValue(Math.max(0, from - 32), from, 'latex') : '';
      const query = before.match(formulaToken)?.[0] || '';
      // A MathLive offset identifies an atom, not a character in serialized TeX.
      const start = from - query.length;
      const literalPrefix = query && start >= 0 && math.getValue(start, from, 'latex') === query;
      const selected = to > from ? math.getValue(from, to, 'latex') : literalPrefix ? query : '';
      const candidates = [...correction(selected), ...(literalPrefix ? options.candidates(query) : [])];
      return {
        bounds: math.getElementInfo(math.position)?.bounds || math.getBoundingClientRect(), candidates,
        current: () => math.isConnected && options.enabled() && math.value === latex
          && JSON.stringify(math.selection) === signature,
        apply(candidate) {
          math.selection = {ranges: [[to > from ? from : start, to]]};
          math.insert(candidate.latex, {format: 'latex', selectionMode: 'placeholder', focus: true});
          writeMath();
        },
      };
    });

    math.addEventListener('move-out', event => {
      const pos = getPos();
      if (pos === undefined) return;
      const forward = ['forward', 'downward'].includes(event.detail.direction);
      event.preventDefault();
      view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, pos + Number(forward))));
      view.focus();
    });
    math.addEventListener('keydown', event => {
      if (event.defaultPrevented || event.isComposing) return;
      if (event.key === 'Escape' && math.mode !== 'latex' && getPos() !== undefined) {
        event.preventDefault(); event.stopPropagation();
        view.dispatch(closeHistory(view.state.tr.setSelection(NodeSelection.create(view.state.doc, getPos()))));
        view.focus();
      }
      if ((event.ctrlKey || event.metaKey) && /^(z|y)$/i.test(event.key)) {
        event.preventDefault(); event.stopPropagation();
        (event.shiftKey || event.key.toLowerCase() === 'y' ? redo : undo)(view.state, view.dispatch);
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        writeMath();
        options.submit(event);
      }
    }, true);
    return {
      dom,
      update(next) {
        if (next.type !== node.type) return false;
        node = next;
        math.readOnly = !options.enabled();
        if (math.value !== next.attrs.latex) math.setValue(next.attrs.latex, {silenceNotifications: true});
        return true;
      },
      selectNode() { dom.classList.add('is-formula-selected'); },
      deselectNode() { dom.classList.remove('is-formula-selected'); },
      stopEvent: event => event.target === math || math.contains(event.target),
      ignoreMutation: () => true,
      destroy: detach,
    };
  }

  function enterFormula(pos, edit) {
    const math = view.nodeDOM(pos)?.querySelector?.('math-field');
    if (!math) { view.focus(); return; }
    // MathLive transfers focus to its keyboard delegate asynchronously. Focus
    // the visible host first so hiding the native field cannot cancel the transfer.
    HTMLElement.prototype.focus.call(math, {preventScroll: true});
    math.focus();
    if (edit && math.value.includes('\\placeholder{}')) {
      math.position = 0;
      math.executeCommand('moveToNextPlaceholder');
    } else {
      math.position = math.lastOffset;
    }
  }

  function insertFormula(from, to, candidate) {
    let template = candidate.latex;
    if (template.includes('#?') && /^[A-Za-z\\]/.test(template)) {
      const tail = view.state.doc.resolve(to);
      const suffix = tail.parent.textBetween(tail.parentOffset, tail.parent.content.size, '', () => '\uFFFC');
      const argument = followingArgument(suffix, 0);
      if (argument && !argument.body.includes('\uFFFC')) {
        template = template.replace('#?', () => bareLatex(argument.body) || '#?');
        to += argument.end;
      }
    }
    const latex = template.replaceAll('#?', '\\placeholder{}');
    const functionCall = /^[A-Za-z\\].*\\left\(#\?\\right\)$/.test(candidate.latex);
    const format = candidate.format || (options.literal ? (functionCall ? 'ascii' : 'latex') : null);
    const raw = format === 'ascii' ? asciiValue(latex) : format === 'latex' ? sourceLatex(latex) : null;
    const node = view.state.schema.nodes[mathType].create({latex, raw, format});
    const tr = view.state.tr.replaceWith(from, to, node);
    if (serialize(tr.doc).length > options.maxLength()) return;
    view.dispatch(closeHistory(tr));
    enterFormula(from, true);
  }

  const detach = options.register(view.dom, () => {
    if (!options.enabled() || view.composing) return null;
    const {doc, selection} = view.state;
    if (!(selection instanceof TextSelection) || !selection.$from.sameParent(selection.$to)) return null;
    const {from, to} = selection;
    const before = selection.$from.parent.textBetween(0, selection.$from.parentOffset, '', () => '\uFFFC');
    const query = from === to ? before.match(formulaToken)?.[0] || '' : '';
    const right = selection.$to.parent.textBetween(selection.$to.parentOffset, selection.$to.parent.content.size,
      '', () => '\uFFFC');
    const tail = query && /^[\\a-z_]/i.test(query) ? right.match(/^[a-z_0-9]*/i)[0].length : 0;
    return {
      bounds: view.coordsAtPos(to), candidates: from === to ? options.candidates(query) : correction(doc.textBetween(from, to)),
      current: () => view.dom.isConnected && options.enabled() && view.state.doc === doc && view.state.selection.eq(selection),
      apply: candidate => insertFormula(from - query.length, to + tail, candidate),
    };
  });
  view.dom.addEventListener('compositionend', () => {
    clearTimeout(recognitionTimer);
    recognitionTimer = setTimeout(() => { promoteTypedRun(false); options.refresh(view.dom); }, 20);
  });

  return {
    root: view.dom,
    value: () => serialize(view.state.doc),
    focus(offset, inside = false) {
      const pos = sourcePosition(view.state.doc, offset ?? serialize(view.state.doc).length);
      if (inside && view.state.doc.nodeAt(pos)?.type.name === mathType) { enterFormula(pos, true); return; }
      view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, pos)));
      view.focus();
    },
    focusTyped(text, offset) {
      const doc = view.state.doc;
      const parts = answerMathSpans(text);
      const adjusted = index => options.answer ? index : index + 4 * parts.filter(part => part.format === 'latex' && part.to <= index).length;
      const fragment = parts.find(part => part.format && (options.answer || part.format === 'latex') && offset > part.from && offset <= part.to);
      if (!fragment) { this.focus(adjusted(offset)); return; }
      const pos = sourcePosition(doc, adjusted(fragment.from));
      const math = view.nodeDOM(pos)?.querySelector?.('math-field');
      if (!math) { this.focus(offset); return; }
      enterFormula(pos, true);
      const tail = text.slice(offset, fragment.to);
      if (fragment.format === 'latex' && tail === '}') {
        math.position = Math.max(0, math.lastOffset - 1);
        typedClosers.add(math);
      }
      if (!math.value.includes('\\placeholder{}') && fragment.format === 'ascii') {
        // Continue inside a denominator/exponent when its last character was typed.
        if (offset === fragment.to && /(?:\/|[\^_])[\w.]+$/.test(fragment.raw))
          math.position = Math.max(0, math.lastOffset - 1);
        else if (offset < fragment.to && /^[)\]}]+$/.test(text.slice(offset, fragment.to)))
          math.position = Math.max(0, math.lastOffset - (fragment.to - offset));
      }
    },
    replaceSource(text) {
      if (text === serialize(view.state.doc)) return;
      const doc = view.state.schema.nodeFromJSON(documentJSON(text, true, !options.answer));
      view.dispatch(view.state.tr.replaceWith(0, view.state.doc.content.size, doc.content).setMeta('sourceSync', true));
    },
    insertFormula(latex) {
      const {from, to} = this.sourceSelection();
      this.insertAt(from, to, latex);
    },
    insertAt(from, to, latex) {
      const doc = view.state.doc;
      if (options.answer && (latex === '!' || /^[\^_]\{#\?\}$/.test(latex))) {
        const prefix = serialize(doc).slice(0, from);
        const base = bareMathRuns(prefix).at(-1);
        if (base?.to === prefix.length && !formulaSpans(prefix).some(span => span.to > base.from)) {
          latex = bareLatex(base.raw) + latex;
          from = base.from;
        }
      }
      if (!latex) {
        const selected = serialize(doc).slice(from, to);
        if (selected && safe(selected)) latex = selected;
        else { from = to; latex = '\\placeholder{}'; }
      }
      insertFormula(sourcePosition(doc, from), sourcePosition(doc, to), {latex});
    },
    sourceSelection() {
      const {doc, selection} = view.state;
      const offset = pos => serialize(doc.cut(0, pos)).length;
      return {from: offset(selection.from), to: offset(selection.to)};
    },
    focusSource(from, to = from) {
      const doc = view.state.doc;
      view.dispatch(view.state.tr.setSelection(TextSelection.create(doc, sourcePosition(doc, from), sourcePosition(doc, to))));
      view.focus();
    },
    anchor(target) {
      const {doc, selection} = view.state;
      if (target?.localName === 'math-field') {
        const latex = target.value, position = JSON.stringify(target.selection);
        return text => {
          if (doc !== view.state.doc || target.value !== latex || JSON.stringify(target.selection) !== position
            || !target.isConnected || !options.enabled()) return false;
          return target.insert(text, {format: 'auto', selectionMode: 'after'});
        };
      }
      return text => {
        if (doc !== view.state.doc || !view.state.selection.eq(selection) || !view.dom.isConnected || !options.enabled()) return false;
        const parsed = view.state.schema.nodeFromJSON(documentJSON(text, true, !options.answer));
        const tr = closeHistory(view.state.tr.replaceSelection(Slice.maxOpen(parsed.content)));
        if (serialize(tr.doc).length > options.maxLength()) return false;
        view.dispatch(tr);
        return true;
      };
    },
    setDisabled() {
      view.setProps({editable: options.enabled});
      host.querySelectorAll('math-field').forEach(math => {math.readOnly = !options.enabled();});
    },
    destroy() { clearTimeout(recognitionTimer); detach(); void editor.destroy(); },
  };
}

export function renderLatex(target, latex, display) {
  if (!displayable(latex)) return false;
  try {
    katex.render(latex, target, {displayMode: display, trust: false, throwOnError: true,
      strict: 'ignore', maxExpand: 100, maxSize: 10});
    return true;
  } catch {
    return false;
  }
}

export const isLatexFragment = safe;
