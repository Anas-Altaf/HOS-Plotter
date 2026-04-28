import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/Input";
import { autocomplete, type AutocompleteResult } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ResolvedLocation {
  label: string;
  lat: number;
  lng: number;
}

interface Props {
  id?: string;
  value: string;
  resolved?: ResolvedLocation | null;
  onChange: (v: string, resolved: ResolvedLocation | null) => void;
  placeholder?: string;
  error?: string;
}

export function LocationAutocomplete({ id, value, resolved, onChange, placeholder, error }: Props) {
  const [results, setResults] = useState<AutocompleteResult[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const lastQueryRef = useRef(value);

  useEffect(() => {
    if (value === lastQueryRef.current) return;
    lastQueryRef.current = value;
    if (resolved && resolved.label !== value) {
      onChange(value, null); // user edited after pick → invalidate
    }
    if (value.trim().length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await autocomplete(value);
        setResults(r);
        setOpen(r.length > 0);
        setActive(0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 280);
    return () => {
      clearTimeout(t);
      setLoading(false);
    };
  }, [value]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function pick(r: AutocompleteResult) {
    lastQueryRef.current = r.label;
    onChange(r.label, { label: r.label, lat: r.lat, lng: r.lng });
    setOpen(false);
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(results[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const isResolved = resolved && resolved.label === value;

  return (
    <div ref={wrapRef} className="relative">
      <div className="relative">
        <Input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value, null)}
          onKeyDown={onKey}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder={placeholder}
          className={cn(
            "pr-7",
            error && "border-destructive focus-visible:ring-destructive",
            isResolved && "border-emerald-300/60"
          )}
          autoComplete="off"
          aria-invalid={!!error}
        />
        {loading && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3 w-3 rounded-full border-2 border-muted-foreground/30 border-t-foreground animate-spin" />
        )}
        {!loading && isResolved && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 h-1.5 w-1.5 rounded-full bg-emerald-500" />
        )}
      </div>
      {error && <p className="mt-1 text-[11px] text-destructive">{error}</p>}
      {open && results.length > 0 && (
        <ul className="absolute z-30 mt-1 w-full max-h-64 overflow-auto rounded-md border border-border bg-card shadow-md">
          {results.map((r, i) => (
            <li key={`${r.label}-${i}`}>
              <button
                type="button"
                onClick={() => pick(r)}
                onMouseEnter={() => setActive(i)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-[13px]",
                  i === active ? "bg-muted" : "hover:bg-muted/60"
                )}
              >
                <span className="line-clamp-1">{r.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
