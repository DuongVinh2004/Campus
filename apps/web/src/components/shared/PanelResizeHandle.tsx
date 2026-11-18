"use client";

import { useEffect, useRef } from "react";

export function PanelResizeHandle({ label, width, onChange, min, max, defaultWidth }: {
  label: string; width: number; onChange: (width: number) => void; min: number; max: number; defaultWidth: number;
}) {
  const drag = useRef<{ x: number; width: number } | null>(null);
  const handle = useRef<HTMLDivElement>(null);
  const latest = useRef({ width, onChange });
  latest.current = { width, onChange };
  function resize(value: number, element: HTMLElement) {
    const left = element.parentElement?.getBoundingClientRect().left ?? 0;
    onChange(Math.round(Math.max(min, Math.min(value, max, window.innerWidth - left - 320))));
  }
  useEffect(() => {
    const element = handle.current;
    if (!element) return;
    const constrain = () => {
      const left = element.parentElement?.getBoundingClientRect().left ?? 0;
      const limit = Math.max(min, Math.min(max, window.innerWidth - left - 320));
      if (latest.current.width > limit) latest.current.onChange(Math.round(limit));
    };
    const observer = new ResizeObserver(constrain);
    if (element.parentElement?.parentElement) observer.observe(element.parentElement.parentElement);
    window.addEventListener("resize", constrain);
    return () => { observer.disconnect(); window.removeEventListener("resize", constrain); };
  }, [min, max]);
  return <div ref={handle} role="separator" aria-label={label} aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={width} tabIndex={0}
    className="campus-panel-resizer"
    onPointerDown={event => {
      if (event.button !== 0) return;
      event.preventDefault(); drag.current = { x: event.clientX, width }; event.currentTarget.setPointerCapture(event.pointerId);
    }}
    onPointerMove={event => { if (drag.current) resize(drag.current.width + event.clientX - drag.current.x, event.currentTarget); }}
    onPointerUp={event => { drag.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}
    onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}
    onDoubleClick={event => resize(defaultWidth, event.currentTarget)}
    onKeyDown={event => {
      const next = ({ ArrowLeft: width - 10, ArrowRight: width + 10, Home: min, End: max } as Record<string, number>)[event.key];
      if (next !== undefined) { event.preventDefault(); resize(next, event.currentTarget); }
    }} />;
}
