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

export interface LogoLoaderOverlayProps
  extends Omit<LogoLoaderProps, "className">,
    React.HTMLAttributes<HTMLDivElement> {
  message?: string;
  blur?: boolean;
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

function LogoLoaderOverlay({
  message = "Loading...",
  blur = true,
  size = 120,
  animation = "spin",
  durationMs = 1400,
  src,
  alt,
  imageClassName,
  style,
  className,
  ...props
}: LogoLoaderOverlayProps) {
  return (
    <div
      className={cn(
        "fixed inset-0 z-[var(--sd-z-modal,60)] flex flex-col items-center justify-center gap-3",
        className
      )}
      style={{
        background: "var(--sd-color-bg-overlay)",
        color: "var(--sd-color-text-inverse)",
        backdropFilter: blur ? "blur(4px)" : undefined,
        ...style,
      }}
      {...props}
    >
      <LogoLoader
        src={src}
        alt={alt ?? message}
        size={size}
        animation={animation}
        durationMs={durationMs}
        imageClassName={imageClassName}
      />
      {message ? (
        <p
          className="text-sm"
          style={{
            color: "var(--sd-color-text-inverse)",
            fontFamily: "var(--sd-font-body)",
          }}
        >
          {message}
        </p>
      ) : null}
    </div>
  );
}

export { LogoLoader, LogoLoaderOverlay };
