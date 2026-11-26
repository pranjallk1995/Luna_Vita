import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";

import { messageOf } from "../lib";

/** pdf.js, loaded on first use so the rest of the app does not carry it. */
async function pdfjs() {
  const [library, worker] = await Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
  ]);
  library.GlobalWorkerOptions.workerSrc = worker.default;
  return library;
}

// Sharper than CSS pixels on a phone, but bounded: a 30-page report stays light on memory.
const MAX_PIXEL_RATIO = 2;

function Page({ pdf, number }: { pdf: PDFDocumentProxy; number: number }) {
  const holder = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [aspect, setAspect] = useState(297 / 210);
  const [near, setNear] = useState(number === 1);

  useEffect(() => {
    let live = true;
    pdf.getPage(number).then((page) => {
      const { width, height } = page.getViewport({ scale: 1 });
      if (live) setAspect(height / width);
    });
    return () => { live = false; };
  }, [pdf, number]);

  // Draw a page only once it scrolls near the screen.
  useEffect(() => {
    if (near || !holder.current) return;
    const watcher = new IntersectionObserver((entries) => entries.some((entry) => entry.isIntersecting) && setNear(true), { rootMargin: "600px 0px" });
    watcher.observe(holder.current);
    return () => watcher.disconnect();
  }, [near]);

  useEffect(() => {
    if (!near || !canvas.current || !holder.current) return;
    let task: { cancel: () => void } | null = null;
    let live = true;
    pdf.getPage(number).then((page) => {
      const target = canvas.current;
      if (!live || !target || !holder.current) return;
      const cssWidth = holder.current.clientWidth || 600;
      const ratio = Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO);
      const viewport = page.getViewport({ scale: (cssWidth * ratio) / page.getViewport({ scale: 1 }).width });
      target.width = Math.floor(viewport.width);
      target.height = Math.floor(viewport.height);
      const context = target.getContext("2d");
      if (!context) return;
      const render = page.render({ canvasContext: context, viewport });
      task = render;
      render.promise.catch(() => undefined);
    });
    return () => {
      live = false;
      task?.cancel();
    };
  }, [pdf, number, near]);

  return (
    <div className="vt-pdf-page" ref={holder} style={{ aspectRatio: `1 / ${aspect}` }}>
      <canvas ref={canvas} aria-label={`Page ${number}`} />
    </div>
  );
}

/** A PDF drawn page by page with pdf.js: phones (Chrome on Android among them) cannot show one in a frame. */
export function PdfPages({ source, title }: { source: string; title: string }) {
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    let opened: PDFDocumentProxy | null = null;
    (async () => {
      try {
        const response = await fetch(source, { credentials: "same-origin" });
        if (!response.ok) throw new Error(response.status === 404 ? "This report's PDF was not found in Luna Lexia." : `The PDF could not be loaded (HTTP ${response.status}).`);
        const data = new Uint8Array(await response.arrayBuffer());
        const library = await pdfjs();
        opened = await library.getDocument({ data, isEvalSupported: false, useSystemFonts: true }).promise;
        if (live) setPdf(opened);
        else opened.destroy();
      } catch (error) {
        if (live) setFailure(messageOf(error, "The PDF could not be shown."));
      }
    })();
    return () => {
      live = false;
      opened?.destroy();
    };
  }, [source]);

  if (failure) return <p className="lv-alert lv-alert-error vt-pdf-note" role="alert">{failure}</p>;
  if (!pdf) return <p className="vt-empty-note vt-pdf-note">Opening the PDF…</p>;
  return (
    <div className="vt-pdf" role="document" aria-label={title}>
      {Array.from({ length: pdf.numPages }, (_, index) => <Page key={index} pdf={pdf} number={index + 1} />)}
      <p className="vt-caption">{pdf.numPages} {pdf.numPages === 1 ? "page" : "pages"}</p>
    </div>
  );
}
