import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTripStore } from "@/store/trip-store";
import { RouteMap } from "@/components/route-map/RouteMap";
import { StopsTimeline } from "@/components/stops-timeline/StopsTimeline";
import { LogSheets } from "@/components/log-sheet/LogSheets";
import { fmtHours, fmtMiles, fmtTime } from "@/lib/utils";

export default function Result() {
  const result = useTripStore((s) => s.result);
  const navigate = useNavigate();

  useEffect(() => {
    if (!result) navigate("/", { replace: true });
  }, [result, navigate]);

  if (!result) return null;

  const { route, stops, logs, summary } = result;

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 space-y-6">
      <div className="no-print">
        <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground font-medium mb-1">Trip plan</div>
        <h1 className="text-xl font-semibold tracking-tight">
          {route.waypoints[0]?.label}
          <span className="text-muted-foreground font-normal mx-2">→</span>
          {route.waypoints[1]?.label}
          <span className="text-muted-foreground font-normal mx-2">→</span>
          {route.waypoints[2]?.label}
        </h1>
        <p className="mt-1 text-[12px] text-muted-foreground font-mono">
          {fmtTime(summary.trip_start)} — {fmtTime(summary.trip_end)}
        </p>
      </div>

      <dl className="no-print grid grid-cols-2 sm:grid-cols-4 gap-px overflow-hidden rounded-md border border-border bg-border">
        <Stat label="Distance" value={fmtMiles(summary.total_distance_mi)} />
        <Stat label="Drive time" value={fmtHours(route.total_drive_minutes)} />
        <Stat label="Total trip" value={fmtHours(summary.total_duration_min)} />
        <Stat label="Log days" value={String(summary.log_days)} />
      </dl>

      <div className="no-print">
        <RouteMap data={result} />
      </div>

      <div className="no-print grid lg:grid-cols-5 gap-4">
        <section className="lg:col-span-2 rounded-md border border-border bg-card">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-[13px] font-semibold tracking-tight">Stops</h2>
            <p className="text-[11px] text-muted-foreground mt-0.5">Required by HOS rules.</p>
          </div>
          <div className="p-4">
            <StopsTimeline stops={stops} />
          </div>
        </section>

        <section className="lg:col-span-3 rounded-md border border-border bg-card">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-[13px] font-semibold tracking-tight">Route legs</h2>
          </div>
          <ul className="divide-y divide-border">
            {route.legs.map((l, i) => (
              <li key={i} className="px-4 py-3 flex flex-wrap items-baseline justify-between gap-2">
                <div className="text-[13px]">
                  <span className="text-muted-foreground mr-2 font-mono">{String(i + 1).padStart(2, "0")}</span>
                  {l.from} <span className="text-muted-foreground">→</span> {l.to}
                </div>
                <div className="text-[12px] text-muted-foreground font-mono tabular-nums">
                  {fmtMiles(l.distance_mi)} · {fmtHours(l.duration_min)}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="rounded-md border border-border bg-card">
        <div className="px-4 py-3 border-b border-border no-print">
          <h2 className="text-[13px] font-semibold tracking-tight">Driver Daily Logs</h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">One sheet per calendar day. Drawn on the FMCSA grid.</p>
        </div>
        <div className="p-4">
          <LogSheets logs={logs} />
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-card px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-base font-semibold mt-0.5 font-mono tabular-nums">{value}</div>
    </div>
  );
}
