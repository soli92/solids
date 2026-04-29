import * as React from "react";

import { IconSoli4x3WithTextTheme } from "@/icons";
import { cn } from "@/lib/utils";

type LogoLoaderAnimation = "spin" | "pulse" | "none";

export interface LogoLoaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Optional custom logo source (svg/png).
   * When omitted, the loader uses the default Soli 4:3 theme-aware logo.
   */
  src?: string;
  alt?: string;
  size?: number;
  animation?: LogoLoaderAnimation;
  durationMs?: number;
  imageClassName?: string;
}

function LogoLoader({
  src,
  alt = "Loading",
  size = 96,
  animation = "spin",
  durationMs = 1400,
  className,
  imageClassName,
  style,
  ...props
}: LogoLoaderProps) {
  const animationClassName =
    animation === "spin" ? "animate-spin" : animation === "pulse" ? "animate-pulse" : "";

  const animationStyle: React.CSSProperties =
    animation === "spin" ? { animationDuration: `${durationMs}ms` } : {};

  return (
    <div
      role="status"
      aria-label={alt}
      className={cn("inline-flex items-center justify-center", className)}
      style={{ ...style }}
      {...props}
    >
      <div
        className={cn(animationClassName)}
        style={animationStyle}
      >
        {src ? (
          <img
            src={src}
            alt={alt}
            width={size}
            className={cn("h-auto max-w-none", imageClassName)}
          />
        ) : (
          <IconSoli4x3WithTextTheme
            size={size}
            aria-hidden
            className={cn("h-auto", imageClassName)}
          />
        )}
      </div>
    </div>
  );
}

export { LogoLoader };
