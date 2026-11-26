"use client"

/**
 * SoliDS — Material 3 layout scaffold (bars → rails → panes) as React components.
 * Thin wrappers over the .sd-scaffold* / .sd-pane* classes of utilities.css; the
 * drag handle uses attachPaneResize() (lib/pane-resize).
 */
import * as React from "react"

import { cn } from "@/lib/utils"
import { attachPaneResize, type PaneResizeMode } from "@/lib/pane-resize"

type Breakpoint = "medium" | "expanded" | "large" | "extra-large"

const visibility = (hideBelow?: Breakpoint, hideFrom?: Breakpoint) =>
  cn(hideBelow && `sd-hide-below-${hideBelow}`, hideFrom && `sd-hide-from-${hideFrom}`)

type VisibilityProps = {
  /** Hidden under this breakpoint (e.g. a second pane that appears from expanded). */
  hideBelow?: Breakpoint
  /** Hidden from this breakpoint up (e.g. the navigation bar, replaced by a rail from medium). */
  hideFrom?: Breakpoint
}

const Scaffold = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("sd-scaffold", className)} {...props} />
  )
)
Scaffold.displayName = "Scaffold"

const ScaffoldBar = React.forwardRef<
  HTMLElement,
  React.HTMLAttributes<HTMLElement> & VisibilityProps & { position?: "top" | "bottom" }
>(({ position = "top", hideBelow, hideFrom, className, ...props }, ref) => {
  const Tag = position === "top" ? "header" : "footer"
  return (
    <Tag
      ref={ref as React.Ref<HTMLElement>}
      className={cn(`sd-scaffold-bar-${position}`, visibility(hideBelow, hideFrom), className)}
      {...props}
    />
  )
})
ScaffoldBar.displayName = "ScaffoldBar"

const ScaffoldRail = React.forwardRef<
  HTMLElement,
  React.HTMLAttributes<HTMLElement> & VisibilityProps & { side?: "start" | "end" }
>(({ side = "start", hideBelow, hideFrom, className, ...props }, ref) => {
  const Tag = side === "start" ? "nav" : "aside"
  return (
    <Tag
      ref={ref as React.Ref<HTMLElement>}
      className={cn(`sd-scaffold-rail-${side}`, visibility(hideBelow, hideFrom), className)}
      {...props}
    />
  )
})
ScaffoldRail.displayName = "ScaffoldRail"

const ScaffoldPanes = React.forwardRef<
  HTMLElement,
  React.HTMLAttributes<HTMLElement> & {
    /** Stack panes vertically under a breakpoint, or in portrait orientation. */
    reflow?: "below-medium" | "below-expanded" | "below-large" | "portrait"
  }
>(({ reflow, className, ...props }, ref) => (
  <main
    ref={ref as React.Ref<HTMLElement>}
    className={cn("sd-scaffold-panes", reflow && `sd-panes-reflow-${reflow}`, className)}
    {...props}
  />
))
ScaffoldPanes.displayName = "ScaffoldPanes"

const paneVariant = {
  flexible: "sd-pane",
  fixed: "sd-pane-fixed",
  "fixed-412": "sd-pane-fixed sd-pane-fixed-412",
  resizable: "sd-pane-resizable",
  floating: "sd-pane-floating",
  docked: "sd-pane-docked",
  adaptive: "sd-pane-adaptive",
} as const

const Pane = React.forwardRef<
  HTMLElement,
  React.HTMLAttributes<HTMLElement> &
    VisibilityProps & {
      /** flexible (default) grows with the window; fixed 360/412px; resizable pairs with PaneHandle. */
      variant?: keyof typeof paneVariant
      /** Vertical scrolling inside the pane. */
      scroll?: boolean
      as?: "section" | "aside" | "div"
    }
>(({ variant = "flexible", scroll, hideBelow, hideFrom, as: Tag = "section", className, ...props }, ref) => (
  <Tag
    ref={ref as React.Ref<HTMLDivElement>}
    className={cn(paneVariant[variant], scroll && "sd-pane-scroll", visibility(hideBelow, hideFrom), className)}
    {...props}
  />
))
Pane.displayName = "Pane"

type PaneHandleProps = Omit<React.HTMLAttributes<HTMLDivElement>, "children"> & {
  /** The resizable pane this handle controls. */
  pane: React.RefObject<HTMLElement | null>
  /** localStorage key: with mode "persistent" the width survives a reload. */
  storageKey?: string
  mode?: PaneResizeMode
  side?: "start" | "end"
  defaultWidth?: number
  min?: number
  max?: number
  label?: string
}

const PaneHandle = React.forwardRef<HTMLDivElement, PaneHandleProps>(
  ({ pane, storageKey, mode, side, defaultWidth, min, max, label, className, ...props }, ref) => {
    const local = React.useRef<HTMLDivElement>(null)
    React.useImperativeHandle(ref, () => local.current as HTMLDivElement)
    React.useEffect(() => {
      if (!local.current || !pane.current) return
      return attachPaneResize(local.current, {
        pane: pane.current, storageKey, mode, side, defaultWidth, min, max, label,
      })
    }, [pane, storageKey, mode, side, defaultWidth, min, max, label])
    return <div ref={local} className={cn("sd-pane-handle", className)} {...props} />
  }
)
PaneHandle.displayName = "PaneHandle"

export { Scaffold, ScaffoldBar, ScaffoldRail, ScaffoldPanes, Pane, PaneHandle }
