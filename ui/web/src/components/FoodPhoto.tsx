import { ImagePlus, Utensils } from "lucide-react";
import { useRef, useState } from "react";
import { createPortal } from "react-dom";

import { fittedPhoto, photoSource, useAct, vita, type Settings } from "../api";
import { Dialog } from "./Dialog";
import { useToast } from "./Toasts";

/**
 * A food with no image of its own: its tile picks a photo, which is stored in Luna Visia
 * (captioned and tagged) and shown on every entry of the food, like update_food_image.
 */
export function AddFoodImage({ source, name, settings, className }: { source?: string | null; name: string; settings: Settings; className: string }) {
  const act = useAct();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const url = photoSource(source);

  const store = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    toast(`Storing the photo of ${name} in Luna Visia…`);
    const stored = await act(async () => {
      const photo = await fittedPhoto(file, settings.food_image_size, settings.food_photo_quality);
      await vita.addFoodImage(name, photo);
    }, `The photo of ${name} could not be stored in Luna Visia.`);
    setBusy(false);
    if (stored) toast(`${name} now shows your photo, saved in Luna Visia`);
  };

  return (
    <>
      <button className={`${className} vt-photo-add`} type="button" disabled={busy} aria-busy={busy}
        aria-label={`Add a photo of ${name}`} title={`Add a photo of ${name}; it is stored in Luna Visia`} onClick={() => input.current?.click()}>
        {url && <img src={url} alt="" loading="lazy" decoding="async" />}
        <span className="vt-photo-add-mark">{busy ? <span className="lv-busy-dot" /> : <ImagePlus size={16} />}</span>
      </button>
      <input ref={input} type="file" hidden accept={settings.photo_upload_types.map((type) => `.${type}`).join(",")}
        onChange={(event) => { store(event.target.files?.[0]); event.target.value = ""; }} />
    </>
  );
}

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
