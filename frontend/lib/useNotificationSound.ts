"use client";

import { useCallback, useEffect, useRef } from "react";

export function useNotificationSound() {
  const contextRef = useRef<AudioContext | null>(null);
  const nextToneRef = useRef(0);

  useEffect(() => {
    // Browsers require a user gesture before audio can play.
    const unlock = () => {
      try {
        if (!contextRef.current && typeof window.AudioContext === "function") {
          contextRef.current = new window.AudioContext();
        }
        const context = contextRef.current;
        if (context?.state === "suspended") void context.resume().catch(() => {});
      } catch {
        // Audio availability must not prevent sending or receiving messages.
      }
    };
    document.addEventListener("pointerdown", unlock, true);
    document.addEventListener("keydown", unlock, true);
    return () => {
      document.removeEventListener("pointerdown", unlock, true);
      document.removeEventListener("keydown", unlock, true);
      const context = contextRef.current;
      contextRef.current = null;
      if (context) void context.close().catch(() => {});
    };
  }, []);

  return useCallback((count = 1) => {
    const context = contextRef.current;
    if (!context || context.state !== "running") return;
    try {
      let start = Math.max(context.currentTime, nextToneRef.current);
      for (let index = 0; index < count; index += 1) {
        for (const [offset, frequency] of [[0, 660], [0.12, 880]]) {
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          oscillator.type = "sine";
          oscillator.frequency.value = frequency;
          gain.gain.setValueAtTime(0, start + offset);
          gain.gain.linearRampToValueAtTime(0.12, start + offset + 0.01);
          gain.gain.exponentialRampToValueAtTime(0.001, start + offset + 0.16);
          oscillator.connect(gain);
          gain.connect(context.destination);
          oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
          oscillator.start(start + offset);
          oscillator.stop(start + offset + 0.18);
        }
        start += 0.4;
      }
      nextToneRef.current = start;
    } catch {
      // Keep chat usable on devices where browser audio is unavailable.
    }
  }, []);
}
