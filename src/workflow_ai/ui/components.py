"""Inline Custom Components v2 for interactions core Streamlit does not provide.

Two progressive enhancements live here:

* a drag-and-drop (and keyboard-reorderable) step list;
* a Ctrl/Cmd+K command palette with shortcut hints.

Both are trusted, static code. All dynamic text is inserted with ``textContent``
from data passed through ``data=``, never as HTML, so model or user text cannot
inject markup. Every component is declared once at import time.
"""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

# ---------------------------------------------------------------------------
# Drag-and-drop step list
# ---------------------------------------------------------------------------

_STEP_HTML = """<div class="awg-root" aria-label="Reorder workflow steps"></div>"""

_STEP_CSS = """
.awg-root {
  display: flex; flex-direction: column; gap: 6px; padding: 4px 0;
  font-family: var(--awg-font, Inter, sans-serif);
}
.awg-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  background: var(--awg-surface, #151C31);
  border: 1px solid var(--awg-border, #2C3752);
  border-left: 3px solid var(--awg-accent, #8B7DFF);
  border-radius: var(--awg-radius, 12px);
  color: var(--awg-text, #EAEEFA); cursor: grab;
}
.awg-row:focus-visible { outline: 2px solid var(--awg-accent, #8B7DFF); outline-offset: 2px; }
.awg-row.awg-dragging { opacity: 0.45; }
.awg-id {
  font-size: 11px; font-weight: 700; letter-spacing: .04em;
  color: var(--awg-accent, #8B7DFF); min-width: 30px;
}
.awg-title { flex: 1; font-size: 13px; font-weight: 600; }
.awg-type {
  font-size: 11px; padding: 2px 8px; border-radius: 999px;
  background: var(--awg-surface-alt, #1E2740);
  color: var(--awg-muted, #A3ADC5);
}
.awg-grip { color: var(--awg-muted, #A3ADC5); font-size: 14px; }
.awg-empty { color: var(--awg-muted, #A3ADC5); font-size: 13px; padding: 10px; }
"""

_STEP_JS = """\
export default function (component) {
  const { parentElement, data, setTriggerValue } = component
  const root = parentElement.querySelector('.awg-root')
  if (!root) return

  const tokens = (data && data.tokens) || {}
  Object.keys(tokens).forEach((key) => {
    root.style.setProperty('--awg-' + key, tokens[key])
  })

  const steps = Array.isArray(data && data.steps) ? data.steps : []
  const emitOrder = () => {
    const ids = Array.from(root.querySelectorAll('.awg-row')).map((r) => r.dataset.id)
    setTriggerValue('order', ids)
  }
  const doc = root.ownerDocument

  root.textContent = ''
  if (!steps.length) {
    const empty = doc.createElement('div')
    empty.className = 'awg-empty'
    empty.textContent = 'No steps to reorder yet.'
    root.appendChild(empty)
    return
  }

  steps.forEach((step) => {
    const row = doc.createElement('div')
    row.className = 'awg-row'
    row.draggable = true
    row.tabIndex = 0
    row.dataset.id = String(step.id)
    row.setAttribute('role', 'listitem')
    row.setAttribute('aria-label', String(step.title) +
      '. Drag or press Alt plus arrow keys to reorder.')

    const id = doc.createElement('span')
    id.className = 'awg-id'
    id.textContent = String(step.id)

    const title = doc.createElement('span')
    title.className = 'awg-title'
    title.textContent = String(step.title)

    const kind = doc.createElement('span')
    kind.className = 'awg-type'
    kind.textContent = String(step.step_type || 'task')

    const grip = doc.createElement('span')
    grip.className = 'awg-grip'
    grip.textContent = '\\u2630'

    row.append(id, title, kind, grip)

    row.ondragstart = (event) => {
      row.classList.add('awg-dragging')
      if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
    }
    row.ondragend = () => row.classList.remove('awg-dragging')
    row.ondragover = (event) => { event.preventDefault() }
    row.ondrop = (event) => {
      event.preventDefault()
      const source = root.querySelector('.awg-dragging')
      if (!source || source === row) return
      const rows = Array.from(root.querySelectorAll('.awg-row'))
      const from = rows.indexOf(source)
      const to = rows.indexOf(row)
      if (from < 0 || to < 0) return
      if (from < to) {
        row.after(source)
      } else {
        row.before(source)
      }
      emitOrder()
    }
    row.onkeydown = (event) => {
      if (!event.altKey || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) return
      event.preventDefault()
      const sibling = event.key === 'ArrowUp' ? row.previousElementSibling : row.nextElementSibling
      if (!sibling || !sibling.classList.contains('awg-row')) return
      if (event.key === 'ArrowUp') {
        sibling.before(row)
      } else {
        sibling.after(row)
      }
      row.focus()
      emitOrder()
    }
    root.appendChild(row)
  })
}
"""

_STEP_LIST = st.components.v2.component(
    "ai_workflow_generator.step_list",
    html=_STEP_HTML,
    css=_STEP_CSS,
    js=_STEP_JS,
)


def step_list(
    steps: list[dict[str, str]],
    *,
    tokens: dict[str, str],
    key: str = "awg_step_list",
    on_order_change: Callable[[], None] | None = None,
) -> object:
    """Mount the accessible drag-and-drop step list and return its result."""
    return _STEP_LIST(
        key=key,
        data={"steps": steps, "tokens": tokens},
        on_order_change=on_order_change or (lambda: None),
    )


# ---------------------------------------------------------------------------
# Command palette / keyboard shortcuts
# ---------------------------------------------------------------------------

_COMMAND_HTML = """
<div class="awg-cmd-root">
  <button class="awg-launch" type="button" aria-label="Open command palette">
    <span aria-hidden="true">⌘</span> Commands <kbd>Ctrl K</kbd>
  </button>
  <div class="awg-overlay" hidden role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="awg-panel">
      <input class="awg-search" type="text" placeholder="Type a command…"
        aria-label="Search commands" />
      <div class="awg-results" role="listbox"></div>
      <p class="awg-hint">↑↓ navigate · Enter run · Esc close</p>
    </div>
  </div>
</div>
"""

_COMMAND_CSS = """
.awg-cmd-root { font-family: var(--awg-font, Inter, sans-serif); }
.awg-launch {
  width: 100%; padding: 8px 10px; cursor: pointer;
  background: var(--awg-surface-alt, #1E2740);
  color: var(--awg-text, #EAEEFA);
  border: 1px solid var(--awg-border, #2C3752);
  border-radius: var(--awg-radius, 12px); text-align: left; font-size: 12px; font-weight: 600;
}
.awg-launch kbd {
  float: right; font-size: 10px; font-weight: 500; padding: 1px 5px;
  border: 1px solid var(--awg-border, #2C3752); border-radius: 4px;
  color: var(--awg-muted, #A3ADC5);
}
.awg-overlay {
  position: fixed; inset: 0; z-index: 10000; display: flex;
  align-items: flex-start; justify-content: center; padding-top: 14vh;
  background: rgba(4, 8, 20, .62);
}
.awg-overlay[hidden] { display: none; }
.awg-panel {
  width: min(520px, 92vw); padding: 12px;
  background: var(--awg-surface, #151C31);
  border: 1px solid var(--awg-border, #2C3752);
  border-radius: var(--awg-radius, 12px);
  box-shadow: 0 24px 70px rgba(0, 0, 0, .35);
  color: var(--awg-text, #EAEEFA);
}
.awg-search {
  width: 100%; box-sizing: border-box; padding: 10px 12px; font-size: 14px;
  background: var(--awg-surface-alt, #1E2740); color: var(--awg-text, #EAEEFA);
  border: 1px solid var(--awg-border, #2C3752);
  border-radius: calc(var(--awg-radius, 12px) - 3px);
}
.awg-results { margin-top: 8px; max-height: 320px; overflow-y: auto; }
.awg-item {
  display: flex; justify-content: space-between; gap: 12px; padding: 9px 10px;
  border-radius: 8px; cursor: pointer; font-size: 13px;
}
.awg-item.awg-active { background: var(--awg-accent, #8B7DFF); color: #FFFFFF; }
.awg-hint { margin: 10px 2px 2px; font-size: 11px; color: var(--awg-muted, #A3ADC5); }
"""

_COMMAND_JS = """\
const registered = new WeakSet()

export default function (component) {
  const { parentElement, data, setTriggerValue } = component
  const root = parentElement.querySelector('.awg-cmd-root')
  if (!root) return

  const tokens = (data && data.tokens) || {}
  Object.keys(tokens).forEach((key) => root.style.setProperty('--awg-' + key, tokens[key]))

  const overlay = root.querySelector('.awg-overlay')
  const search = root.querySelector('.awg-search')
  const results = root.querySelector('.awg-results')
  const launch = root.querySelector('.awg-launch')
  const commands = Array.isArray(data && data.commands) ? data.commands : []
  let active = 0

  const render = () => {
    const term = (search.value || '').toLowerCase()
    const matches = commands.filter((c) =>
      String(c.label).toLowerCase().includes(term) || String(c.hint).toLowerCase().includes(term))
    active = Math.max(0, Math.min(active, Math.max(matches.length - 1, 0)))
    results.textContent = ''
    matches.forEach((command, index) => {
      const item = results.ownerDocument.createElement('div')
      item.className = 'awg-item' + (index === active ? ' awg-active' : '')
      item.setAttribute('role', 'option')
      const label = results.ownerDocument.createElement('span')
      label.textContent = String(command.label)
      const hint = results.ownerDocument.createElement('span')
      hint.textContent = String(command.hint)
      item.append(label, hint)
      item.onclick = () => {
        overlay.hidden = true
        setTriggerValue('command', String(command.id))
      }
      results.appendChild(item)
    })
    return matches
  }

  const open = () => {
    overlay.hidden = false
    search.value = ''
    active = 0
    render()
    search.focus()
  }
  const close = () => { overlay.hidden = true }

  launch.onclick = open
  overlay.onclick = (event) => { if (event.target === overlay) close() }
  search.oninput = render

  search.onkeydown = (event) => {
    const items = results.querySelectorAll('.awg-item')
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      active = Math.min(active + 1, items.length - 1)
      render()
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      active = Math.max(active - 1, 0)
      render()
    }
    else if (event.key === 'Enter' && items.length) {
      event.preventDefault()
      const term = (search.value || '').toLowerCase()
      const matches = commands.filter((c) =>
        String(c.label).toLowerCase().includes(term) || String(c.hint).toLowerCase().includes(term))
      close()
      setTriggerValue('command', String(matches[active].id))
    } else if (event.key === 'Escape') { event.preventDefault(); close() }
  }

  if (!registered.has(parentElement)) {
    registered.add(parentElement)
    const doc = root.ownerDocument
    const onGlobalKey = (event) => {
      const modifier = event.ctrlKey || event.metaKey
      if (modifier && String(event.key).toLowerCase() === 'k') {
        event.preventDefault()
        if (overlay.hidden) {
          open()
        } else {
          close()
        }
      } else if (modifier && event.key === 'Enter') {
        event.preventDefault()
        close()
        setTriggerValue('command', 'generate')
      } else if (event.key === 'Escape' && !overlay.hidden) {
        close()
      }
    }
    doc.addEventListener('keydown', onGlobalKey)
    return () => {
      doc.removeEventListener('keydown', onGlobalKey)
      registered.delete(parentElement)
    }
  }
  return () => {}
}
"""

_COMMAND_PALETTE = st.components.v2.component(
    "ai_workflow_generator.command_palette",
    html=_COMMAND_HTML,
    css=_COMMAND_CSS,
    js=_COMMAND_JS,
)


def command_palette(
    commands: list[dict[str, str]],
    *,
    tokens: dict[str, str],
    key: str = "awg_command_palette",
    on_command_change: Callable[[], None] | None = None,
) -> object:
    """Mount the keyboard command palette and return its result."""
    return _COMMAND_PALETTE(
        key=key,
        data={"commands": commands, "tokens": tokens},
        on_command_change=on_command_change or (lambda: None),
    )


__all__ = ["command_palette", "step_list"]
