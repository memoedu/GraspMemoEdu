import {Editor, defaultValueCtx, editorViewCtx, editorViewOptionsCtx, rootCtx} from '@milkdown/core';
import {docSchema, paragraphAttr, paragraphSchema, textSchema} from '@milkdown/preset-commonmark';
import {$node, $prose} from '@milkdown/utils';
import {baseKeymap} from '@milkdown/prose/commands';
import {history, closeHistory, redo, undo} from '@milkdown/prose/history';
import {keymap} from '@milkdown/prose/keymap';
import {Slice} from '@milkdown/prose/model';
import {NodeSelection, Plugin, TextSelection} from '@milkdown/prose/state';
import {MathfieldElement, validateLatex} from 'mathlive';
import {unified} from 'unified';
import {unifiedLatexFromString} from '@unified-latex/unified-latex-util-parse';
import {printRaw} from '@unified-latex/unified-latex-util-print-raw';
import {lints} from '@unified-latex/unified-latex-lint';
import katex from 'katex';
import {formulaSpans, formulaToken} from '../../web/formula-catalog.js';

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
const safe = latex => typeof latex === 'string' && latex.length <= 4000
  && !/\\(?:html\w*|css\w*|includegraphics|href|url|style|class|def|gdef|edef|newcommand|renewcommand)\b/i.test(latex)
  && validateLatex(latex).length === 0;

const formulaSchema = $node(mathType, () => ({
  inline: true, group: 'inline', atom: true, selectable: true,
  attrs: {latex: {default: ''}, display: {default: false}, raw: {default: null}},
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

function documentJSON(text) {
  const rows = [[]];
  function plain(value) {
    value.split('\n').forEach((part, index) => {
      if (index) rows.push([]);
      if (part) rows.at(-1).push({type: 'text', text: part});
    });
  }
  let from = 0;
  for (const match of formulaSpans(text)) {
    if (!safe(match.latex)) continue;
    plain(text.slice(from, match.from));
    rows.at(-1).push({type: mathType, attrs: {latex: match.latex, display: match.display, raw: match.raw}});
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

  let view;
  const update = $prose(() => new Plugin({
    filterTransaction(tr) {
      return !tr.docChanged || tr.getMeta('sourceSync') || options.enabled() && serialize(tr.doc).length <= options.maxLength();
    },
  }));
  const editor = await Editor.make().config(ctx => {
    ctx.set(rootCtx, host);
    ctx.set(defaultValueCtx, {type: 'json', value: documentJSON(options.value())});
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
          queueMicrotask(() => {
            if (!this.composing && host.isConnected) options.refresh(this.dom);
          });
        }
      },
      clipboardTextSerializer(slice) { return slice.content.textBetween(0, slice.content.size, '\n', asText); },
      handlePaste(view, event) {
        const text = event.clipboardData?.getData('text/plain');
        if (!text) return false;
        const value = /^\\[A-Za-z]/.test(text) && safe(text) ? wrap(text) : text;
        const doc = view.state.schema.nodeFromJSON(documentJSON(value));
        view.dispatch(closeHistory(view.state.tr.replaceSelection(Slice.maxOpen(doc.content))));
        return true;
      },
      handleTextInput(view, from, to, text) {
        if (!/[$)\]]$/.test(text)) return false;
        const start = view.state.doc.resolve(from);
        const before = start.parent.textBetween(0, start.parentOffset, '', () => '\uFFFC') + text;
        const match = formulaSpans(before).at(-1);
        if (!match || match.to !== before.length || match.latex.includes('\uFFFC') || !safe(match.latex)) return false;
        const node = view.state.schema.nodes[mathType].create({latex: match.latex, display: match.display, raw: match.raw});
        view.dispatch(view.state.tr.replaceWith(from - (match.raw.length - text.length), to, node));
        return true;
      },
    });
  }).use([docSchema, paragraphAttr, ...paragraphSchema, textSchema, formulaSchema, update,
    $prose(() => history()), $prose(() => keymap({'Mod-z': undo, 'Mod-Shift-z': redo, 'Mod-y': redo, ...baseKeymap}))
  ]).create();
  view = editor.action(ctx => ctx.get(editorViewCtx));

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
    math.onExport = (_, latex) => wrap(latex, node.attrs.display);
    math.value = node.attrs.latex;
    dom.append(math);

    function writeMath() {
      const pos = getPos();
      if (pos === undefined || !options.enabled()) return;
      const latex = math.value;
      if (latex === node.attrs.latex) return;
      const raw = {...node.attrs, latex, raw: null};
      const tr = view.state.tr.setNodeMarkup(pos, null, raw);
      if (serialize(tr.doc).length > options.maxLength()) {
        math.setValue(node.attrs.latex, {silenceNotifications: true});
        return;
      }
      view.dispatch(tr);
    }
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
    math.focus();
    if (edit) {
      math.position = 0;
      math.executeCommand('moveToNextPlaceholder');
    }
  }

  function insertFormula(from, to, candidate) {
    const latex = candidate.latex.replaceAll('#?', '\\placeholder{}');
    const node = view.state.schema.nodes[mathType].create({latex});
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
  view.dom.addEventListener('compositionend', () => queueMicrotask(() => options.refresh(view.dom)));

  return {
    root: view.dom,
    focus(offset, inside = false) {
      const pos = sourcePosition(view.state.doc, offset ?? serialize(view.state.doc).length);
      if (inside && view.state.doc.nodeAt(pos)?.type.name === mathType) { enterFormula(pos, true); return; }
      view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, pos)));
      view.focus();
    },
    replaceSource(text) {
      if (text === serialize(view.state.doc)) return;
      const doc = view.state.schema.nodeFromJSON(documentJSON(text));
      view.dispatch(view.state.tr.replaceWith(0, view.state.doc.content.size, doc.content).setMeta('sourceSync', true));
    },
    insertFormula(latex) {
      const {from, to} = this.sourceSelection();
      this.insertAt(from, to, latex);
    },
    insertAt(from, to, latex) {
      const doc = view.state.doc;
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
        const tr = view.state.tr.insertText(text.replace(/[\r\n]+/g, ' '), selection.from, selection.to);
        if (serialize(tr.doc).length > options.maxLength()) return false;
        view.dispatch(tr);
        return true;
      };
    },
    setDisabled() {
      view.setProps({editable: options.enabled});
      host.querySelectorAll('math-field').forEach(math => {math.readOnly = !options.enabled();});
    },
    destroy() { detach(); void editor.destroy(); },
  };
}

export function renderFormulaText(target, text) {
  const fragments = document.createDocumentFragment();
  let from = 0;
  for (const span of formulaSpans(text)) {
    if (!safe(span.latex)) continue;
    const item = document.createElement('span');
    if (span.display) item.className = 'siteFormulaDisplay';
    try {
      katex.render(span.latex, item, {displayMode: span.display, trust: false, throwOnError: true, maxExpand: 100, maxSize: 10});
    } catch { continue; }
    fragments.append(text.slice(from, span.from), item);
    from = span.to;
  }
  fragments.append(text.slice(from));
  target.replaceChildren(fragments);
}

export const isLatexFragment = safe;
