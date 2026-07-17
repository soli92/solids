// ============================================================
// @soli92/solids — Themed Icon Sets
//
// Sets:
//   - FANTASY  : scroll, sword, gem
//   - CYBERPUNK: chip, eye, signal
//   - 90S-PARTY: bolt, diamond, star
// ============================================================

import * as React from "react";
import { SolidsIcon, type SolidsIconProps } from "./solids-icon";

type IconProps = Omit<SolidsIconProps, "children">;

// ─────────────────────────────────────────────────────────────
// FANTASY SET
// Style: rounded strokes, organic shapes, medieval/magic feel
// ─────────────────────────────────────────────────────────────

/**
 * IconFantasyScroll
 * Rolled parchment scroll with decorative ribbons and text lines.
 */
export const IconFantasyScroll = React.forwardRef<SVGSVGElement, IconProps>(
  function IconFantasyScroll(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <rect x="4" y="5" width="16" height="14" rx="2" ry="2" />
        <path d="M4 5 C4 3 6 2 7 3 C8 4 7 5 6 5" />
        <path d="M20 5 C20 3 18 2 17 3 C16 4 17 5 18 5" />
        <path d="M4 19 C4 21 6 22 7 21 C8 20 7 19 6 19" />
        <path d="M20 19 C20 21 18 22 17 21 C16 20 17 19 18 19" />
        <line x1="7" y1="9"  x2="17" y2="9"  />
        <line x1="7" y1="12" x2="17" y2="12" />
        <line x1="7" y1="15" x2="13" y2="15" />
        <circle cx="15.5" cy="15" r="1" />
      </SolidsIcon>
    );
  }
);

/**
 * IconFantasySword
 * Medieval sword: blade, crossguard, rounded pommel. Diagonal 45°.
 */
export const IconFantasySword = React.forwardRef<SVGSVGElement, IconProps>(
  function IconFantasySword(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <line x1="5" y1="19" x2="17" y2="7" />
        <path d="M17 7 L19 5" />
        <line x1="7" y1="17" x2="13" y2="11" />
        <circle cx="4.5" cy="19.5" r="1.5" />
        <path d="M8 14 L6 16" />
        <path d="M10 12 L12 10" />
      </SolidsIcon>
    );
  }
);

/**
 * IconFantasyGem
 * Hexagonal magic gem with light-ray burst and sparkle center.
 */
export const IconFantasyGem = React.forwardRef<SVGSVGElement, IconProps>(
  function IconFantasyGem(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <polygon points="12,3 18,6.5 18,13.5 12,17 6,13.5 6,6.5" />
        <line x1="12" y1="3"   x2="12" y2="17" />
        <line x1="6"  y1="6.5" x2="18" y2="13.5" />
        <line x1="18" y1="6.5" x2="6"  y2="13.5" />
        <line x1="12" y1="1"   x2="12" y2="3"  />
        <line x1="21" y1="10"  x2="18" y2="10" />
        <line x1="3"  y1="10"  x2="6"  y2="10" />
        <circle cx="12" cy="10" r="1" />
      </SolidsIcon>
    );
  }
);


// ─────────────────────────────────────────────────────────────
// CYBERPUNK SET
// Style: geometric, sharp angles, tech/neon feel
// ─────────────────────────────────────────────────────────────

/**
 * IconCyberpunkChip
 * CPU microchip: square body, pins on all 4 sides, inner circuit cross.
 */
export const IconCyberpunkChip = React.forwardRef<SVGSVGElement, IconProps>(
  function IconCyberpunkChip(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <rect x="6" y="6" width="12" height="12" rx="1" />
        <rect x="9" y="9" width="6"  height="6"  rx="0" />
        <line x1="12" y1="9"  x2="12" y2="15" />
        <line x1="9"  y1="12" x2="15" y2="12" />
        <line x1="9"  y1="6" x2="9"  y2="3" />
        <line x1="12" y1="6" x2="12" y2="3" />
        <line x1="15" y1="6" x2="15" y2="3" />
        <line x1="9"  y1="18" x2="9"  y2="21" />
        <line x1="12" y1="18" x2="12" y2="21" />
        <line x1="15" y1="18" x2="15" y2="21" />
        <line x1="6" y1="9"  x2="3" y2="9"  />
        <line x1="6" y1="12" x2="3" y2="12" />
        <line x1="6" y1="15" x2="3" y2="15" />
        <line x1="18" y1="9"  x2="21" y2="9"  />
        <line x1="18" y1="12" x2="21" y2="12" />
        <line x1="18" y1="15" x2="21" y2="15" />
      </SolidsIcon>
    );
  }
);

/**
 * IconCyberpunkEye
 * Cybernetic eye: angular almond outline, scan lines, mechanical pupil.
 */
export const IconCyberpunkEye = React.forwardRef<SVGSVGElement, IconProps>(
  function IconCyberpunkEye(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <path d="M2 12 L6 7 L12 5 L18 7 L22 12 L18 17 L12 19 L6 17 Z" />
        <circle cx="12" cy="12" r="4" />
        <line x1="8"  y1="10.5" x2="16" y2="10.5" />
        <line x1="8"  y1="12"   x2="16" y2="12"   />
        <line x1="8"  y1="13.5" x2="16" y2="13.5" />
        <rect x="10.5" y="10.5" width="3" height="3" rx="0" />
        <line x1="6"  y1="7"  x2="8"  y2="9"  />
        <line x1="18" y1="7"  x2="16" y2="9"  />
        <line x1="6"  y1="17" x2="8"  y2="15" />
        <line x1="18" y1="17" x2="16" y2="15" />
      </SolidsIcon>
    );
  }
);

/**
 * IconCyberpunkSignal
 * Angular radio signal: chevron-waves with glitch effect.
 */
export const IconCyberpunkSignal = React.forwardRef<SVGSVGElement, IconProps>(
  function IconCyberpunkSignal(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <rect x="10" y="10" width="4" height="4" rx="0" />
        <path d="M7 8 L5 12 L7 16" />
        <path d="M17 8 L19 12 L17 16" />
        <path d="M5 5 L2 12 L5 19" />
        <path d="M19 5 L22 12 L19 19" />
      </SolidsIcon>
    );
  }
);


// ─────────────────────────────────────────────────────────────
// 90S-PARTY SET
// Style: bold thick strokes, exaggerated shapes, rave/MTV/Memphis
// ─────────────────────────────────────────────────────────────

/**
 * IconPartyBolt
 * Thick cartoon lightning bolt, 90s style. Bold stroke.
 */
export const IconPartyBolt = React.forwardRef<SVGSVGElement, IconProps>(
  function IconPartyBolt(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <polyline
          points="13,2 6,13 11,13 11,22 18,11 13,11"
          strokeWidth={2.5}
          strokeLinejoin="round"
        />
      </SolidsIcon>
    );
  }
);

/**
 * IconPartyDiamond
 * Bold diamond with facets and reflection shard. Hip-hop feel.
 */
export const IconPartyDiamond = React.forwardRef<SVGSVGElement, IconProps>(
  function IconPartyDiamond(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <polygon points="12,2 20,9 12,22 4,9" strokeWidth={2.5} />
        <line x1="4"  y1="9" x2="20" y2="9" strokeWidth={2.5} />
        <line x1="8"  y1="9" x2="12" y2="22" />
        <line x1="16" y1="9" x2="12" y2="22" />
        <polyline points="7,9 9,5 12,9" />
      </SolidsIcon>
    );
  }
);

/**
 * IconPartyStar
 * Bold 5-point star with double-outline effect. Retro 90s MTV feel.
 */
export const IconPartyStar = React.forwardRef<SVGSVGElement, IconProps>(
  function IconPartyStar(props, ref) {
    return (
      <SolidsIcon ref={ref} {...props}>
        <polygon
          points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"
          strokeWidth={2.5}
        />
        <circle cx="12" cy="12" r="1.5" />
      </SolidsIcon>
    );
  }
);
