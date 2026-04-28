import type { Stop } from "@/lib/types";
import { fmtHours, fmtTime } from "@/lib/utils";

const meta: Record<string, { label: string; dot: string }> = {
  pickup: { label: "Pickup", dot: "bg-emerald-500" },
  dropoff: { label: "Dropoff", dot: "bg-rose-500" },
  fuel: { label: "Fuel", dot: "bg-amber-500" },
  break_30: { label: "30-min break", dot: "bg-yellow-500" },
  rest_10: { label: "10-hr reset", dot: "bg-violet-500" },
  restart_34: { label: "34-hr restart", dot: "bg-slate-500" },
};

export function StopsTimeline({ stops }: { stops: Stop[] }) {
  if (!stops.length) return null;
  return (
    <ol className="space-y-2.5">
      {stops.map((s, i) => {
        const m = meta[s.type] || meta.fuel;
        return (
          <li
            key={i}
            className="flex items-start gap-3 rounded border border-border bg-background/50 px-3 py-2"
          >
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${m.dot}`} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-[13px] font-medium">{m.label}</span>
                <span className="text-[11px] text-muted-foreground font-mono tabular-nums">
                  Mile {s.mile.toFixed(0)} · {fmtHours(s.duration_min)}
                </span>
              </div>
              <div className="mt-0.5 text-[11px] text-muted-foreground font-mono tabular-nums">
                {fmtTime(s.start)} → {fmtTime(s.end)}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
