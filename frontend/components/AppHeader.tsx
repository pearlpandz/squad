"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { invalidateNavigationData, prefetchNavigationData } from "@/lib/api";
import { Bot, FolderKanban, LayoutTemplate, ChevronLeft, ChevronRight, LogOut, Menu, Moon, ShieldCheck, Sun, Users, X } from "lucide-react";
import { useAdminSession } from "@/components/AdminSession";
import { Toast } from "@/components/Toast";

type ThemeMode = "light" | "dark";

export function AppHeader() {
  const [theme, setTheme] = useState<ThemeMode>("light");
  const [collapsed, setCollapsed] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobile, setMobile] = useState(false);
  const sidebar = useRef<HTMLElement>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut } = useAdminSession();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const menus = [
    { href: "/teams", label: "Teams", icon: Users, active: pathname.startsWith("/teams") },
    { href: "/projects", label: "Projects", icon: FolderKanban, active: pathname === "/" || pathname.startsWith("/projects") },
    { href: "/agents", label: "AI Co-workers", icon: Bot, active: pathname.startsWith("/agents") },
    { href: "/templates", label: "Agent Templates", icon: LayoutTemplate, active: pathname.startsWith("/templates") },
  ].filter((item) => item.href !== "/templates" || session.is_admin);

  function prefetchMenu(href: string) {
    router.prefetch(href);
    void prefetchNavigationData(href);
  }

  useEffect(() => {
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
    if (connection?.saveData || ["slow-2g", "2g"].includes(connection?.effectiveType ?? "")) return;
    let cancelled = false;
    // Warm one directory at a time after the current page has had time to load.
    const timer = window.setTimeout(async () => {
      for (const href of ["/teams", "/projects", "/agents", "/templates"]) {
        if (href === "/templates" && !session.is_admin) continue;
        if (cancelled || document.visibilityState !== "visible") break;
        if (pathname.startsWith(href)) continue;
        router.prefetch(href);
        await prefetchNavigationData(href);
      }
    }, 1500);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [pathname, router, session.is_admin]);

  useEffect(() => {
    const refreshOnReturn = () => { if (document.visibilityState === "visible") invalidateNavigationData(); };
    window.addEventListener("focus", refreshOnReturn);
    document.addEventListener("visibilitychange", refreshOnReturn);
    return () => {
      window.removeEventListener("focus", refreshOnReturn);
      document.removeEventListener("visibilitychange", refreshOnReturn);
    };
  }, []);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("synergy-theme");
    const nextTheme = savedTheme === "dark" ? "dark" : "light";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    setCollapsed(window.localStorage.getItem("collab-sidebar-collapsed") !== "false");
    const media = window.matchMedia("(max-width: 760px)");
    const resize = () => { setMobile(media.matches); if (!media.matches) setMobileOpen(false); };
    resize();
    media.addEventListener("change", resize);
    return () => media.removeEventListener("change", resize);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.navigationExpanded = String(!collapsed);
  }, [collapsed]);

  useEffect(() => { setMobileOpen(false); }, [pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const content = document.getElementById("page-content");
    const overflow = document.body.style.overflow;
    if (content) content.inert = true;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(sidebar.current?.querySelectorAll<HTMLElement>("a[href], button:not([disabled])") ?? [])
      .filter((element) => element.getClientRects().length > 0);
    focusable()[0]?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setMobileOpen(false); }
      if (event.key !== "Tab") return;
      const elements = focusable();
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      if (content) content.inert = false;
      document.body.style.overflow = overflow;
      if (previous?.isConnected && previous.getClientRects().length) previous.focus();
    };
  }, [mobileOpen]);

  function toggleTheme() {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("synergy-theme", nextTheme);
  }

  function toggleSidebar() {
    const next = !collapsed;
    setCollapsed(next);
    window.localStorage.setItem("collab-sidebar-collapsed", String(next));
  }

  async function logout() {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await signOut();
      setMobileOpen(false);
      router.replace("/login");
    } catch (caught) {
      setLogoutError(caught instanceof Error ? caught.message : "Unable to log out. Please retry.");
      setLoggingOut(false);
    }
  }

  return <>
    {logoutError && <Toast message={logoutError} tone="error" />}
    <a className="appSkipLink" href="#page-content" onClick={(event) => { event.preventDefault(); document.getElementById("page-content")?.focus(); }}>Skip to content</a>
    <header className="mobileAppBar">
      <button aria-controls="app-navigation" aria-expanded={mobileOpen} aria-label="Open navigation" className="appNavigationControl" onClick={() => setMobileOpen(true)} type="button"><Menu size={22} /></button>
      <Link className="appMobileBrand" href="/teams">SQUAD.</Link>
    </header>
    {mobileOpen && <button aria-label="Close navigation" className="appNavigationBackdrop" onClick={() => setMobileOpen(false)} tabIndex={-1} type="button" />}
    <aside aria-hidden={mobile && !mobileOpen ? true : undefined} aria-label="Workspace navigation" aria-modal={mobile && mobileOpen ? true : undefined}
      className={`appNavigation${collapsed ? " collapsed" : ""}${mobileOpen ? " mobileOpen" : ""}`} id="app-navigation" ref={sidebar} role={mobile ? "dialog" : undefined}>
      <div className="appNavigationHeader">
        <Link aria-label="SQUAD. home" className="appNavigationBrand" href="/teams" onClick={() => setMobileOpen(false)} title="SQUAD."><span className="appBrandMark">S.</span><span className="appBrandName">SQUAD.</span></Link>

        <button aria-label="Close navigation" className="appNavigationControl appMobileClose" onClick={() => setMobileOpen(false)} type="button"><X size={22} /></button>
      </div>
      <nav aria-label="Main navigation" className="appNavigationLinks" id="app-primary-navigation">
        {menus.map(({ href, label, icon: Icon, active }) => <Link aria-current={active ? "page" : undefined} aria-label={label} href={href} key={href}
          onMouseEnter={() => prefetchMenu(href)} onFocus={() => prefetchMenu(href)} onTouchStart={() => prefetchMenu(href)}
          onClick={() => setMobileOpen(false)} title={label}>
          <Icon aria-hidden="true" size={21} /><span className="appNavigationLabel">{label}</span>
        </Link>)}
      </nav>
      <div className="appNavigationFooter">
        <button aria-label={loggingOut ? "Logging out" : "Logout"} className="appNavigationTheme" disabled={loggingOut} onClick={() => void logout()} title="Logout" type="button">
          <LogOut size={18} aria-hidden="true" /><span className="appNavigationLabel">{loggingOut ? "Logging out…" : "Logout"}</span>
        </button>
        <Link className="appNavigationTheme" href="/admin" aria-label={session.is_admin ? "Admin workspace" : "Your account"} title={session.is_admin ? "Admin workspace" : "Your account"}>
          <ShieldCheck size={18} aria-hidden="true" /><span className="appNavigationLabel">{session.is_admin ? "Admin workspace" : "Your account"}</span>
        </Link>
        <button aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"} className="appNavigationTheme" onClick={toggleTheme} title={theme === "light" ? "Dark theme" : "Light theme"} type="button">
          {theme === "light" ? <Moon aria-hidden="true" size={20} /> : <Sun aria-hidden="true" size={20} />}<span className="appNavigationLabel">{theme === "light" ? "Dark theme" : "Light theme"}</span>
        </button>
        <div aria-hidden="true" className="appNavigationProfile"><div className="avatar profile"><span /></div></div>
      </div>
    </aside>
    <button aria-controls="app-primary-navigation" aria-expanded={!collapsed} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      className="appSidebarToggle appDesktopToggle" onClick={toggleSidebar} title={collapsed ? "Expand sidebar" : "Collapse sidebar"} type="button">
      {collapsed ? <ChevronRight aria-hidden="true" size={14} /> : <ChevronLeft aria-hidden="true" size={14} />}
    </button>
  </>;
}
