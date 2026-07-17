import * as React from "react";

export const SOLIDS_ICON_SIZES = {
  sm: 16,
  md: 20,
  lg: 24,
  xl: 32,
} as const;

export type SolidsIconSize = keyof typeof SOLIDS_ICON_SIZES | number;

const variantColor: Record<
  "default" | "muted" | "primary" | "on-primary",
  string
> = {
  default: "var(--sd-color-icon-default)",
  muted: "var(--sd-color-icon-muted)",
  primary: "var(--sd-color-icon-primary)",
  "on-primary": "var(--sd-color-icon-on-primary)",
};

export type SolidsIconVariant = keyof typeof variantColor;

export type SolidsIconProps = React.PropsWithChildren<
  Omit<React.SVGProps<SVGSVGElement>, "width" | "height" | "color"> & {
    size?: SolidsIconSize;
    variant?: SolidsIconVariant;
  }
>;

/**
 * Wrapper SVG per icone stroke: colore da token `--sd-color-icon-*`, dimensione da `size`.
 * Usa `currentColor` così puoi anche sovrascrivere con `className` / utility `.sd-icon-*`.
 */
export const SolidsIcon = React.forwardRef<SVGSVGElement, SolidsIconProps>(
  function SolidsIcon(
    {
      children,
      className,
      size = "md",
      variant = "default",
      strokeWidth = 2,
      style,
      ...props
    },
    ref
  ) {
    const px = typeof size === "number" ? size : SOLIDS_ICON_SIZES[size];
    return (
      <svg
        ref={ref}
        xmlns="http://www.w3.org/2000/svg"
        width={px}
        height={px}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={["shrink-0", className].filter(Boolean).join(" ")}
        style={{
          color: variantColor[variant],
          ...style,
        }}
        aria-hidden
        {...props}
      >
        {children}
      </svg>
    );
  }
);
