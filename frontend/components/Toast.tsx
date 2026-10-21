"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { CircleAlert, CircleCheck, Info, X } from "lucide-react";

export function Toast({ message, tone = "success" }: {
  message: string;
  tone?: "success" | "error" | "info";
}) {
  const [viewport, setViewport] = useState<HTMLElement | null>(null);
  const [visible, setVisible] = useState(true);
  const [pinned, setPinned] = useState(false);

  useEffect(() => { setViewport(document.getElementById("toast-viewport")); }, []);
  useEffect(() => { setVisible(true); setPinned(false); }, [message]);
  useEffect(() => {
    if (!viewport || !visible || pinned) return;
    const timer = window.setTimeout(() => setVisible(false), 5000);
    return () => window.clearTimeout(timer);
  }, [message, viewport, visible, pinned]);

  if (!viewport || !visible) return null;
  const Icon = tone === "error" ? CircleAlert : tone === "info" ? Info : CircleCheck;
  return createPortal(
    <div className={`toast toast--${tone}`} onMouseEnter={() => setPinned(true)} onFocusCapture={() => setPinned(true)}>
      <Icon aria-hidden="true" className="toastIcon" size={20} />
      <p role={tone === "error" ? "alert" : "status"}>{message}</p>
      <button aria-label="Dismiss notification" className="toastClose" onClick={() => setVisible(false)} type="button"><X aria-hidden="true" size={18} /></button>
    </div>, viewport,
  );
}
