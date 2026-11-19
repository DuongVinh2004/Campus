"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Keep source bytes in memory while Activity suspends object-URL effects. */
export function usePreviewImages() {
  const blobs = useRef(new Map<string, Blob>());
  const urls = useRef(new Map<string, string>());
  const visible = useRef(false);
  const [images, setImages] = useState<Record<string, string>>({});

  useEffect(() => {
    visible.current = true;
    const restored: Record<string, string> = {};
    for (const [key, blob] of blobs.current) {
      const url = URL.createObjectURL(blob);
      urls.current.set(key, url); restored[key] = url;
    }
    setImages(restored);
    return () => {
      visible.current = false;
      for (const url of urls.current.values()) URL.revokeObjectURL(url);
      urls.current.clear();
    };
  }, []);

  const cacheImage = useCallback((key: string, blob: Blob) => {
    blobs.current.set(key, blob);
    if (!visible.current) return;
    const previous = urls.current.get(key);
    const url = URL.createObjectURL(blob);
    urls.current.set(key, url);
    setImages(current => ({ ...current, [key]: url }));
    if (previous) URL.revokeObjectURL(previous);
  }, []);

  return { images, cacheImage };
}
