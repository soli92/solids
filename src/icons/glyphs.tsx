import * as React from "react";

import { SolidsIcon, type SolidsIconProps } from "./solids-icon";

type IconProps = Omit<SolidsIconProps, "children">;

export const IconHome = React.forwardRef<SVGSVGElement, IconProps>(function IconHome(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </SolidsIcon>
  );
});

export const IconSearch = React.forwardRef<SVGSVGElement, IconProps>(function IconSearch(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </SolidsIcon>
  );
});

export const IconUser = React.forwardRef<SVGSVGElement, IconProps>(function IconUser(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </SolidsIcon>
  );
});

export const IconSettings = React.forwardRef<SVGSVGElement, IconProps>(function IconSettings(
  props,
  ref
) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </SolidsIcon>
  );
});

export const IconMenu = React.forwardRef<SVGSVGElement, IconProps>(function IconMenu(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <line x1="4" x2="20" y1="12" y2="12" />
      <line x1="4" x2="20" y1="6" y2="6" />
      <line x1="4" x2="20" y1="18" y2="18" />
    </SolidsIcon>
  );
});

export const IconX = React.forwardRef<SVGSVGElement, IconProps>(function IconX(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </SolidsIcon>
  );
});

export const IconCheck = React.forwardRef<SVGSVGElement, IconProps>(function IconCheck(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M20 6 9 17l-5-5" />
    </SolidsIcon>
  );
});

export const IconChevronDown = React.forwardRef<SVGSVGElement, IconProps>(function IconChevronDown(
  props,
  ref
) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="m6 9 6 6 6-6" />
    </SolidsIcon>
  );
});

export const IconChevronRight = React.forwardRef<SVGSVGElement, IconProps>(function IconChevronRight(
  props,
  ref
) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="m9 18 6-6-6-6" />
    </SolidsIcon>
  );
});

export const IconPlus = React.forwardRef<SVGSVGElement, IconProps>(function IconPlus(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </SolidsIcon>
  );
});

export const IconMinus = React.forwardRef<SVGSVGElement, IconProps>(function IconMinus(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M5 12h14" />
    </SolidsIcon>
  );
});

export const IconTrash = React.forwardRef<SVGSVGElement, IconProps>(function IconTrash(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
    </SolidsIcon>
  );
});

export const IconPencil = React.forwardRef<SVGSVGElement, IconProps>(function IconPencil(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
      <path d="m15 5 4 4" />
    </SolidsIcon>
  );
});

export const IconCopy = React.forwardRef<SVGSVGElement, IconProps>(function IconCopy(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </SolidsIcon>
  );
});

export const IconExternalLink = React.forwardRef<SVGSVGElement, IconProps>(function IconExternalLink(
  props,
  ref
) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </SolidsIcon>
  );
});

export const IconAlertCircle = React.forwardRef<SVGSVGElement, IconProps>(function IconAlertCircle(
  props,
  ref
) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" x2="12" y1="8" y2="12" />
      <line x1="12" x2="12.01" y1="16" y2="16" />
    </SolidsIcon>
  );
});

export const IconInfo = React.forwardRef<SVGSVGElement, IconProps>(function IconInfo(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </SolidsIcon>
  );
});

export const IconStar = React.forwardRef<SVGSVGElement, IconProps>(function IconStar(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </SolidsIcon>
  );
});

export const IconHeart = React.forwardRef<SVGSVGElement, IconProps>(function IconHeart(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
    </SolidsIcon>
  );
});

export const IconSun = React.forwardRef<SVGSVGElement, IconProps>(function IconSun(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </SolidsIcon>
  );
});

export const IconMoon = React.forwardRef<SVGSVGElement, IconProps>(function IconMoon(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </SolidsIcon>
  );
});

export const IconMail = React.forwardRef<SVGSVGElement, IconProps>(function IconMail(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <rect width="20" height="16" x="2" y="4" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </SolidsIcon>
  );
});

export const IconCalendar = React.forwardRef<SVGSVGElement, IconProps>(function IconCalendar(
  props,
  ref
) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M8 2v4" />
      <path d="M16 2v4" />
      <rect width="18" height="18" x="3" y="4" rx="2" />
      <path d="M3 10h18" />
    </SolidsIcon>
  );
});

export const IconFolder = React.forwardRef<SVGSVGElement, IconProps>(function IconFolder(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.16 3.13A2 2 0 0 0 7.47 2H4a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2Z" />
    </SolidsIcon>
  );
});

// ─── Fantasy Icons (stroke arrotondato, feel medievale) ────────────────────────

export const IconFantasyScroll = React.forwardRef<SVGSVGElement, IconProps>(function IconFantasyScroll(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M6 4h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
      <path d="M4 8a2 2 0 0 0 0 4" />
      <path d="M20 8a2 2 0 0 1 0 4" />
      <path d="M9 12h6" />
      <path d="M9 8h6" />
      <path d="M9 16h4" />
    </SolidsIcon>
  );
});

export const IconFantasySword = React.forwardRef<SVGSVGElement, IconProps>(function IconFantasySword(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M14.5 2.5 20 8l-9 9-5.5-1L4 21l5-1.5L18 10l-5.5-5.5" />
      <path d="M10 14 6 18" />
      <path d="M9 9.5 7 12" />
    </SolidsIcon>
  );
});

export const IconFantasyGem = React.forwardRef<SVGSVGElement, IconProps>(function IconFantasyGem(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M12 2 7 7l-5 5 5 5 5 5 5-5 5-5-5-5-5-5z" />
      <path d="m7 7 5 5 5-5" />
      <path d="m7 17 5-5" />
    </SolidsIcon>
  );
});

// ─── Cyberpunk Icons (geometric sharp, feel tech) ──────────────────────────────

export const IconCyberpunkChip = React.forwardRef<SVGSVGElement, IconProps>(function IconCyberpunkChip(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <rect x="7" y="7" width="10" height="10" rx="1" />
      <path d="M9 7V4M12 7V4M15 7V4" />
      <path d="M9 20v-3M12 20v-3M15 20v-3" />
      <path d="M7 9H4M7 12H4M7 15H4" />
      <path d="M20 9h-3M20 12h-3M20 15h-3" />
      <rect x="9" y="9" width="6" height="6" rx="0" />
    </SolidsIcon>
  );
});

export const IconCyberpunkEye = React.forwardRef<SVGSVGElement, IconProps>(function IconCyberpunkEye(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z" />
      <circle cx="12" cy="12" r="3" />
      <path d="M12 9v1M12 14v1M9 12h1M14 12h1" />
    </SolidsIcon>
  );
});

export const IconCyberpunkSignal = React.forwardRef<SVGSVGElement, IconProps>(function IconCyberpunkSignal(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props}>
      <path d="M2 12h3l2-5 3 10 2-7 2 4 2-2h6" />
      <path d="M19 6v2M21 8l-2 2" />
    </SolidsIcon>
  );
});

// ─── 90s Party Icons (bold, feel rave/MTV) ─────────────────────────────────────

export const IconPartyBolt = React.forwardRef<SVGSVGElement, IconProps>(function IconPartyBolt(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props} strokeWidth={props.strokeWidth ?? 2.5}>
      <path d="M13 2 4 13h7l-2 9 11-12h-7l2-8z" />
    </SolidsIcon>
  );
});

export const IconPartyDiamond = React.forwardRef<SVGSVGElement, IconProps>(function IconPartyDiamond(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props} strokeWidth={props.strokeWidth ?? 2.5}>
      <path d="M12 2 3 9l9 13 9-13-9-7z" />
      <path d="M3 9h18" />
      <path d="M9 2l-2 7M15 2l2 7" />
    </SolidsIcon>
  );
});

export const IconPartyStar = React.forwardRef<SVGSVGElement, IconProps>(function IconPartyStar(props, ref) {
  return (
    <SolidsIcon ref={ref} {...props} strokeWidth={props.strokeWidth ?? 2.5}>
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6L12 2z" />
    </SolidsIcon>
  );
});

type SoliBrandPalette = {
  frame: string;
  symbol: string;
  wordmark: string;
};

type SoliBrandIconProps = Omit<React.SVGProps<SVGSVGElement>, "color"> & {
  size?: number;
};

const SoliBrandIcon = React.forwardRef<
  SVGSVGElement,
  SoliBrandIconProps & { showWordmark: boolean; wide: boolean; palette: SoliBrandPalette }
>(function SoliBrandIcon(
  {
    size = 96,
    className,
    style,
    showWordmark,
    wide,
    palette,
    ...props
  },
  ref
) {
  const width = wide ? 160 : 120;
  const height = showWordmark ? 120 : 90;
  const cx = wide ? 80 : 60;
  const cy = 44;
  const frameLeft = wide ? 16 : 12;
  const frameRight = wide ? 144 : 108;
  const frameTop = 8;
  const frameBottom = 80;
  const gearR = 16;
  const gearTeeth = Array.from({ length: 8 }, (_, i) => i * (Math.PI / 4));
  return (
    <svg
      ref={ref}
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${width} ${height}`}
      width={size}
      height={(size * height) / width}
      className={className}
      style={style}
      {...props}
    >
      <g fill="none" stroke={palette.frame} strokeWidth="2">
        <rect x={frameLeft} y={frameTop} width={frameRight - frameLeft} height={frameBottom - frameTop} />
        <polygon points={`${cx},${frameTop - 8} ${frameRight + 8},${cy} ${cx},${frameBottom + 8} ${frameLeft - 8},${cy}`} />
        <line x1={frameLeft} y1={frameTop} x2={frameRight} y2={frameBottom} />
        <line x1={frameRight} y1={frameTop} x2={frameLeft} y2={frameBottom} />
        <line x1={cx} y1={frameTop} x2={cx} y2={frameBottom} />
        <path d={`M${frameLeft + 10} ${cy + 8}h12`} />
        <path d={`M${frameRight - 22} ${cy - 4}h12`} />
      </g>
      <g fill={palette.symbol} stroke={palette.symbol}>
        {gearTeeth.map((a) => {
          const x = cx + Math.cos(a) * (gearR + 5);
          const y = cy + Math.sin(a) * (gearR + 5);
          return <rect key={a} x={x - 2} y={y - 2} width="4" height="4" transform={`rotate(${(a * 180) / Math.PI} ${x} ${y})`} />;
        })}
        <circle cx={cx} cy={cy} r={gearR} />
      </g>
      <circle cx={cx} cy={cy} r={9} fill="white" />
      <text
        x={cx}
        y={cy + 3}
        textAnchor="middle"
        fontFamily="Georgia, serif"
        fontWeight="700"
        fontSize="14"
        fill={palette.symbol}
      >
        S
      </text>
      {showWordmark ? (
        <text
          x={cx}
          y={108}
          textAnchor="middle"
          fontFamily="var(--sd-font-heading, Inter, sans-serif)"
          fontWeight="700"
          fontSize="18"
          fill={palette.wordmark}
        >
          Soli
        </text>
      ) : null}
    </svg>
  );
});

const monoPalette: SoliBrandPalette = {
  frame: "#0b0f14",
  symbol: "#0b0f14",
  wordmark: "#0b0f14",
};

const goldPalette: SoliBrandPalette = {
  frame: "#b8922e",
  symbol: "#c8a23a",
  wordmark: "#0b0f14",
};

const themedPalette: SoliBrandPalette = {
  frame: "var(--sd-color-icon-primary)",
  symbol: "var(--sd-color-icon-primary)",
  wordmark: "var(--sd-color-text-primary)",
};

export const IconSoli1x1WithTextMono = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli1x1WithTextMono(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark wide={false} palette={monoPalette} />;
  }
);

export const IconSoli4x3WithTextMono = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli4x3WithTextMono(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark wide palette={monoPalette} />;
  }
);

export const IconSoli1x1SymbolOnlyMono = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli1x1SymbolOnlyMono(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark={false} wide={false} palette={monoPalette} />;
  }
);

export const IconSoli4x3SymbolOnlyMono = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli4x3SymbolOnlyMono(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark={false} wide palette={monoPalette} />;
  }
);

export const IconSoli1x1WithTextGold = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli1x1WithTextGold(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark wide={false} palette={goldPalette} />;
  }
);

export const IconSoli4x3WithTextGold = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli4x3WithTextGold(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark wide palette={goldPalette} />;
  }
);

export const IconSoli1x1SymbolOnlyGold = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli1x1SymbolOnlyGold(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark={false} wide={false} palette={goldPalette} />;
  }
);

export const IconSoli4x3SymbolOnlyGold = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli4x3SymbolOnlyGold(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark={false} wide palette={goldPalette} />;
  }
);

export const IconSoli1x1WithTextTheme = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli1x1WithTextTheme(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark wide={false} palette={themedPalette} />;
  }
);

export const IconSoli4x3WithTextTheme = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli4x3WithTextTheme(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark wide palette={themedPalette} />;
  }
);

export const IconSoli1x1SymbolOnlyTheme = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli1x1SymbolOnlyTheme(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark={false} wide={false} palette={themedPalette} />;
  }
);

export const IconSoli4x3SymbolOnlyTheme = React.forwardRef<SVGSVGElement, SoliBrandIconProps>(
  function IconSoli4x3SymbolOnlyTheme(props, ref) {
    return <SoliBrandIcon ref={ref} {...props} showWordmark={false} wide palette={themedPalette} />;
  }
);
