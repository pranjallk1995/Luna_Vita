import { Utensils } from "lucide-react";
import { useState } from "react";
import { createPortal } from "react-dom";

import { photoSource } from "../api";
import { Dialog } from "./Dialog";

/** A food photo that opens large on click, or a plain tile when there is none or it cannot be loaded. */
export function FoodPhoto({ source, name, className, emptyClass }: { source?: string | null; name: string; className: string; emptyClass: string }) {
  const [failed, setFailed] = useState(false);
  const [zoomed, setZoomed] = useState(false);
  const url = photoSource(source);
  if (!url || failed) {
    return (
      <span className={emptyClass}>
        <Utensils size={20} />
      </span>
    );
  }
  return (
    <>
      <button className={`${className} vt-photo-zoom`} type="button" aria-label={`Zoom the photo of ${name}`} onClick={() => setZoomed(true)}>
        <img src={url} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />
      </button>
      {zoomed &&
        createPortal(
          <Dialog title={name} size="large" onClose={() => setZoomed(false)}>
            <img className="vt-photo-large" src={photoSource(source, true)} alt={name} decoding="async" />
          </Dialog>,
          document.body,
        )}
    </>
  );
}
