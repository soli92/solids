/**
 * SoliDS — pane resizing for the M3 layout scaffold (drag handle).
 *
 * Material 3 (I/O 2026): panes are resized, expanded and collapsed with a drag
 * handle; on release they can snap to 360dp or 412dp; selecting the handle
 * (tap, double tap, Enter) toggles between layout sizes. Two behaviours:
 * - persistent: the width is remembered, also after a breakpoint change or a
 *   reload (default, for most resizable layouts);
 * - temporary: the width returns to the default when the layout is opened
 *   again (supporting pane layouts).
 *
 * No dependencies, no framework. React projects can also use the Resizable
 * component (react-resizable-panels).
 */

export type PaneResizeMode = "persistent" | "temporary";

export interface PaneResizeOptions {
  /** Pane whose width the handle controls (the fixed pane next to it). */
  pane: HTMLElement;
  /** Default width in px. Default: 360. */
  defaultWidth?: number;
  /** Minimum width in px before the pane collapses. Default: 240. */
  min?: number;
  /** Maximum width in px. Default: 640. */
  max?: number;
  /** Snap widths in px (M3: 360 and 412). */
  snap?: number[];
  /** Distance in px within which a release snaps. Default: 24. */
  snapThreshold?: number;
  /** Keyboard step in px (Shift: ×5). Default: 8. */
  step?: number;
  /** Where the pane sits relative to the handle. Default: "start". */
  side?: "start" | "end";
  mode?: PaneResizeMode;
  /** localStorage key, required for mode "persistent" to survive a reload. */
  storageKey?: string;
  /** Accessible name of the handle. Default: "Ridimensiona il pannello". */
  label?: string;
}

export interface PaneResizeState {
  width: number;
  collapsed: boolean;
}

export const M3_PANE_SNAP_WIDTHS = [360, 412] as const;

/** Clamps a width to [min, max]. */
export const clampWidth = (w: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, Math.round(w)));

/** Returns the snap width closest to `w` if within `threshold`, else `w`. */
export const snapWidth = (w: number, snap: readonly number[], threshold: number): number => {
  let best = w;
  let dist = threshold + 1;
  for (const s of snap) {
    const d = Math.abs(s - w);
    if (d <= threshold && d < dist) {
      best = s;
      dist = d;
    }
  }
  return best;
};

/**
 * Width after a key press. Arrow keys follow the visual direction: with the
 * pane on the start side, ArrowRight widens it (in RTL the arrows swap).
 * Returns null for keys that do not resize.
 */
export const keyboardWidth = (
  key: string,
  width: number,
  o: { min: number; max: number; step: number; shift: boolean; side: "start" | "end"; rtl: boolean },
): number | null => {
  const step = o.shift ? o.step * 5 : o.step;
  let grow = 0;
  if (key === "ArrowRight") grow = 1;
  else if (key === "ArrowLeft") grow = -1;
  else if (key === "Home") return o.min;
  else if (key === "End") return o.max;
  else return null;
  if (o.side === "end") grow = -grow;
  if (o.rtl) grow = -grow;
  return clampWidth(width + grow * step, o.min, o.max);
};

const readStored = (key: string | undefined): PaneResizeState | null => {
  if (!key) return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const v = JSON.parse(raw);
    return typeof v?.width === "number" ? { width: v.width, collapsed: Boolean(v.collapsed) } : null;
  } catch {
    return null;
  }
};

const writeStored = (key: string | undefined, s: PaneResizeState): void => {
  if (!key) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(s));
  } catch {
    /* storage unavailable: the width lives only for this page */
  }
};

/**
 * Turns `handle` into an accessible drag handle for `options.pane`.
 * Sets `--sd-pane-width` on the pane and `data-collapsed` when collapsed.
 * Returns a function that removes the listeners.
 */
export function attachPaneResize(handle: HTMLElement, options: PaneResizeOptions): () => void {
  const {
    pane,
    defaultWidth = 360,
    min = 240,
    max = 640,
    snap = [...M3_PANE_SNAP_WIDTHS],
    snapThreshold = 24,
    step = 8,
    side = "start",
    mode = "persistent",
    storageKey,
    label = "Ridimensiona il pannello",
  } = options;

  const stored = mode === "persistent" ? readStored(storageKey) : null;
  const state: PaneResizeState = stored
    ? { width: clampWidth(stored.width, min, max), collapsed: stored.collapsed }
    : { width: clampWidth(defaultWidth, min, max), collapsed: false };

  if (!pane.id) pane.id = `sd-pane-${Math.random().toString(36).slice(2, 9)}`;
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("aria-controls", pane.id);
  handle.setAttribute("aria-label", label);
  handle.setAttribute("aria-valuemin", String(min));
  handle.setAttribute("aria-valuemax", String(max));
  if (!handle.hasAttribute("tabindex")) handle.tabIndex = 0;

  const render = (persist: boolean) => {
    pane.style.setProperty("--sd-pane-width", `${state.width}px`);
    pane.toggleAttribute("data-collapsed", state.collapsed);
    handle.setAttribute("aria-valuenow", String(state.collapsed ? 0 : state.width));
    handle.setAttribute("aria-expanded", String(!state.collapsed));
    if (persist && mode === "persistent") writeStored(storageKey, state);
  };

  const isRtl = () => getComputedStyle(handle).direction === "rtl";

  let startX = 0;
  let startW = 0;
  let dragging = false;
  let moved = false;

  const onPointerDown = (e: PointerEvent) => {
    if (e.button !== 0) return;
    dragging = true;
    moved = false;
    startX = e.clientX;
    startW = state.collapsed ? 0 : state.width;
    handle.setPointerCapture(e.pointerId);
    handle.setAttribute("data-dragging", "");
    e.preventDefault();
  };

  const onPointerMove = (e: PointerEvent) => {
    if (!dragging) return;
    let dx = e.clientX - startX;
    if (Math.abs(dx) > 2) moved = true;
    if (side === "end") dx = -dx;
    if (isRtl()) dx = -dx;
    const raw = startW + dx;
    if (raw < min / 2) {
      state.collapsed = true;
    } else {
      state.collapsed = false;
      state.width = clampWidth(raw, min, max);
    }
    render(false);
  };

  const onPointerUp = (e: PointerEvent) => {
    if (!dragging) return;
    dragging = false;
    handle.removeAttribute("data-dragging");
    if (handle.hasPointerCapture(e.pointerId)) handle.releasePointerCapture(e.pointerId);
    if (moved && !state.collapsed) state.width = snapWidth(state.width, snap, snapThreshold);
    render(moved);
  };

  const toggle = () => {
    state.collapsed = !state.collapsed;
    render(true);
  };

  const onDblClick = () => toggle();

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggle();
      return;
    }
    const next = keyboardWidth(e.key, state.collapsed ? min : state.width, {
      min, max, step, shift: e.shiftKey, side, rtl: isRtl(),
    });
    if (next === null) return;
    e.preventDefault();
    state.collapsed = false;
    state.width = next;
    render(true);
  };

  handle.addEventListener("pointerdown", onPointerDown);
  handle.addEventListener("pointermove", onPointerMove);
  handle.addEventListener("pointerup", onPointerUp);
  handle.addEventListener("pointercancel", onPointerUp);
  handle.addEventListener("dblclick", onDblClick);
  handle.addEventListener("keydown", onKeyDown);
  render(false);

  return () => {
    handle.removeEventListener("pointerdown", onPointerDown);
    handle.removeEventListener("pointermove", onPointerMove);
    handle.removeEventListener("pointerup", onPointerUp);
    handle.removeEventListener("pointercancel", onPointerUp);
    handle.removeEventListener("dblclick", onDblClick);
    handle.removeEventListener("keydown", onKeyDown);
  };
}
