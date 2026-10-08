"use client";

import { useEffect, useRef, useState } from "react";
import { searchCid10, type CidOption } from "@/lib/api";

/**
 * Searchable combobox for CID-10 codes. Typing queries the catalogue (debounced)
 * and shows a dropdown of "code — description"; picking one calls `onSelect`
 * with the option and the display text. Typing free text calls `onSelect(null, text)`
 * so the caller can still keep a free-text diagnosis (the field is not locked to
 * the catalogue).
 */
export function CidCombobox({
  value,
  onSelect,
  placeholder,
  className,
}: {
  value: string;
  onSelect: (opt: CidOption | null, text: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [text, setText] = useState(value);
  const [opts, setOpts] = useState<CidOption[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setText(value);
  }, [value]);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (!open || text.trim().length < 2) {
      setOpts([]);
      return;
    }
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        setOpts(await searchCid10(text));
      } catch {
        setOpts([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [text, open]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div ref={box} className="relative">
      <input
        className={className}
        value={text}
        placeholder={placeholder}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          onSelect(null, e.target.value);
        }}
      />
      {open && text.trim().length >= 2 && (
        <div className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-md border bg-popover shadow-md">
          {loading && <div className="px-3 py-2 text-xs text-muted-foreground">…</div>}
          {!loading && opts.length === 0 && (
            <div className="px-3 py-2 text-xs text-muted-foreground">—</div>
          )}
          {opts.map((o) => (
            <button
              key={o.code}
              type="button"
              className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent"
              onClick={() => {
                const label = `${o.code} — ${o.description}`;
                onSelect(o, label);
                setText(label);
                setOpen(false);
              }}
            >
              <span className="font-medium">{o.code}</span>{" "}
              <span className="text-muted-foreground">{o.description}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
