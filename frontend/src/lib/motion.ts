// Scroll reveals: pure DOM, no dependency. Reveal classes are added by script, so React re-renders only ever remove
// them (the content then simply shows). Motion is on by default; ?motion=off turns it off and is remembered,
// ?motion=on turns it back on. prefers-reduced-motion is honoured by the stylesheet.
const KEY = "studease.motion";

function preference(): string | null {
  try {
    const q = new URLSearchParams(location.search).get("motion");
    if (q === "on" || q === "off") localStorage.setItem(KEY, q);
    return localStorage.getItem(KEY);
  } catch {
    return null; // storage blocked: default to on
  }
}

const SELECTOR = ".reveal, .panel, h1, table.register";

export function initMotion(): () => void {
  if (typeof window === "undefined" || preference() === "off") return () => {};
  const root = document.documentElement;
  root.setAttribute("data-motion", "on");
  const io = new IntersectionObserver((entries) => {
    let i = 0;
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const el = e.target as HTMLElement;
      el.style.transitionDelay = `${Math.min(i++, 6) * 70}ms`;
      el.classList.add("vx-in"); // vx-r was applied in an earlier task, so the transition still plays
      io.unobserve(el);
    }
  }, { threshold: 0.08, rootMargin: "0px 0px -6% 0px" });
  const seen = new WeakSet<Element>();
  const scan = () => {
    document.querySelectorAll(SELECTOR).forEach((el) => {
      if (seen.has(el)) return;
      seen.add(el);
      if (el.parentElement?.closest(SELECTOR)) return; // reveal only the outermost, never nested twice
      el.classList.add("vx-r");
      io.observe(el);
    });
  };
  scan();
  const mo = new MutationObserver(scan);
  mo.observe(document.body, { childList: true, subtree: true });
  return () => { io.disconnect(); mo.disconnect(); };
}
