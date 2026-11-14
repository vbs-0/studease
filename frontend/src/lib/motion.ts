// Scroll reveals, mouse parallax and a scroll-progress bar: pure DOM, no dependency.
// Reveal classes are added by script and removed again once the reveal has played, so React re-renders and
// hover transforms never fight them. Motion is on by default; ?motion=off turns it off and is remembered,
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

const SELECTOR = ".reveal, .panel, .info-card, .hero-card, .stat-card, .mint-card, table.register";

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
      el.classList.add("vx-in");
      io.unobserve(el);
      setTimeout(() => { el.classList.remove("vx-r", "vx-in"); el.style.transitionDelay = ""; }, 1300);
    }
  }, { threshold: 0.06, rootMargin: "0px 0px -4% 0px" });

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

  let raf = 0, mx = 0, my = 0;
  const onMove = (ev: MouseEvent) => {
    mx = (ev.clientX / window.innerWidth) * 2 - 1;
    my = (ev.clientY / window.innerHeight) * 2 - 1;
    if (!raf) raf = requestAnimationFrame(() => { raf = 0; root.style.setProperty("--mx", mx.toFixed(3)); root.style.setProperty("--my", my.toFixed(3)); });
  };
  const onScroll = () => {
    const max = root.scrollHeight - window.innerHeight;
    root.style.setProperty("--sp", max > 0 ? String(Math.min(1, window.scrollY / max)) : "0");
  };
  window.addEventListener("mousemove", onMove, { passive: true });
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  return () => { io.disconnect(); mo.disconnect(); window.removeEventListener("mousemove", onMove); window.removeEventListener("scroll", onScroll); };
}
