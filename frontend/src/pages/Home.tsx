import { TripForm } from "@/components/trip-form/TripForm";

export default function Home() {
  return (
    <div className="mx-auto max-w-xl px-4 sm:px-6 py-12 sm:py-16">
      <div className="mb-8">
        <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground font-medium mb-2">
          Trip Planner
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">New trip</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Enter trip details. Output: route, mandated stops, daily log sheets.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-5 sm:p-6 shadow-sm">
        <TripForm />
      </div>

      <dl className="mt-6 grid grid-cols-3 gap-px overflow-hidden rounded-md border border-border bg-border text-[11px]">
        <div className="bg-card px-3 py-2.5">
          <dt className="text-muted-foreground">Drive limit</dt>
          <dd className="font-mono text-foreground mt-0.5">11 h</dd>
        </div>
        <div className="bg-card px-3 py-2.5">
          <dt className="text-muted-foreground">On-duty window</dt>
          <dd className="font-mono text-foreground mt-0.5">14 h</dd>
        </div>
        <div className="bg-card px-3 py-2.5">
          <dt className="text-muted-foreground">Required reset</dt>
          <dd className="font-mono text-foreground mt-0.5">10 h off</dd>
        </div>
      </dl>
    </div>
  );
}
