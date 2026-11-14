import { useEffect } from "react";

const SITE = "StudEase";

/** Per-route title and meta description (a single-page app has one index.html, so each page sets its own). */
export function usePage(title: string, description: string): void {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE}` : SITE;
    let tag = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (!tag) {
      tag = document.createElement("meta");
      tag.name = "description";
      document.head.appendChild(tag);
    }
    tag.content = description;
  }, [title, description]);
}
