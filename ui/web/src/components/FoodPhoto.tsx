import { Utensils } from "lucide-react";
import { useState } from "react";

import { photoSource } from "../api";

/** A food photo, or a plain tile when there is none or it cannot be loaded. */
export function FoodPhoto({ source, alt, className, emptyClass }: { source?: string | null; alt: string; className: string; emptyClass: string }) {
  const [failed, setFailed] = useState(false);
  const url = photoSource(source);
  if (!url || failed) {
    return (
      <span className={emptyClass}>
        <Utensils size={20} />
      </span>
    );
  }
  return <img className={className} src={url} alt={alt} loading="lazy" decoding="async" onError={() => setFailed(true)} />;
}
