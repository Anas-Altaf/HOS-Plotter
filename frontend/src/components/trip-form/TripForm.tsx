import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LocationAutocomplete, type ResolvedLocation } from "./LocationAutocomplete";
import { planTrip } from "@/lib/api";
import { useTripStore } from "@/store/trip-store";
import { cn } from "@/lib/utils";

const schema = z
  .object({
    current_location: z.string().min(2, "Required"),
    pickup_location: z.string().min(2, "Required"),
    dropoff_location: z.string().min(2, "Required"),
    current_cycle_hours: z.coerce.number().min(0, "Min 0").max(70, "Max 70"),
    cycle_type: z.enum(["70_8", "60_7"]),
  })
  .refine((d) => d.pickup_location.trim().toLowerCase() !== d.dropoff_location.trim().toLowerCase(), {
    message: "Pickup and dropoff must differ",
    path: ["dropoff_location"],
  })
  .refine((d) => d.current_cycle_hours <= (d.cycle_type === "70_8" ? 70 : 60), {
    message: "Exceeds selected cycle max",
    path: ["current_cycle_hours"],
  });

type FormData = z.infer<typeof schema>;

type Coords = {
  current: ResolvedLocation | null;
  pickup: ResolvedLocation | null;
  dropoff: ResolvedLocation | null;
};

export function TripForm() {
  const navigate = useNavigate();
  const setResult = useTripStore((s) => s.setResult);
  const setInputs = useTripStore((s) => s.setInputs);
  const setLoading = useTripStore((s) => s.setLoading);
  const loading = useTripStore((s) => s.loading);

  const [coords, setCoords] = useState<Coords>({ current: null, pickup: null, dropoff: null });

  const {
    control,
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      current_location: "",
      pickup_location: "",
      dropoff_location: "",
      current_cycle_hours: 0,
      cycle_type: "70_8",
    },
  });

  const cycleType = watch("cycle_type");
  const cycleHours = watch("current_cycle_hours");
  const cycleMax = cycleType === "70_8" ? 70 : 60;
  const cycleRemaining = Math.max(0, cycleMax - (Number(cycleHours) || 0));
  const showRestartHint = cycleRemaining < 14 && (Number(cycleHours) || 0) > 0;

  const allResolved = !!(coords.current && coords.pickup && coords.dropoff);

  async function onSubmit(data: FormData) {
    setLoading(true);
    setInputs(data);
    const wakingTimer = setTimeout(() => {
      toast.message("Waking up server…", { description: "Free hosting cold start, ~20s." });
    }, 5000);
    try {
      const res = await planTrip({
        ...data,
        current_coord: coords.current ?? undefined,
        pickup_coord: coords.pickup ?? undefined,
        dropoff_coord: coords.dropoff ?? undefined,
      });
      setResult(res);
      navigate("/result");
    } catch (e: any) {
      const msg =
        e?.response?.data?.detail ||
        (e?.response?.data && JSON.stringify(e.response.data)) ||
        e?.message ||
        "Something went wrong.";
      toast.error("Could not plan trip", { description: String(msg).slice(0, 200) });
    } finally {
      clearTimeout(wakingTimer);
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="current_location">Current location</Label>
          <Controller
            control={control}
            name="current_location"
            render={({ field }) => (
              <LocationAutocomplete
                id="current_location"
                value={field.value}
                resolved={coords.current}
                onChange={(v, r) => {
                  field.onChange(v);
                  setCoords((c) => ({ ...c, current: r }));
                }}
                placeholder="City, ST"
                error={errors.current_location?.message}
              />
            )}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="pickup_location">Pickup</Label>
          <Controller
            control={control}
            name="pickup_location"
            render={({ field }) => (
              <LocationAutocomplete
                id="pickup_location"
                value={field.value}
                resolved={coords.pickup}
                onChange={(v, r) => {
                  field.onChange(v);
                  setCoords((c) => ({ ...c, pickup: r }));
                }}
                placeholder="City, ST"
                error={errors.pickup_location?.message}
              />
            )}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="dropoff_location">Dropoff</Label>
          <Controller
            control={control}
            name="dropoff_location"
            render={({ field }) => (
              <LocationAutocomplete
                id="dropoff_location"
                value={field.value}
                resolved={coords.dropoff}
                onChange={(v, r) => {
                  field.onChange(v);
                  setCoords((c) => ({ ...c, dropoff: r }));
                }}
                placeholder="City, ST"
                error={errors.dropoff_location?.message}
              />
            )}
          />
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="current_cycle_hours">Cycle used (hrs)</Label>
          <Input
            id="current_cycle_hours"
            type="number"
            step="0.5"
            min={0}
            max={cycleMax}
            {...register("current_cycle_hours")}
            className={cn("font-mono", errors.current_cycle_hours && "border-destructive")}
          />
          {errors.current_cycle_hours && (
            <p className="text-[11px] text-destructive">{errors.current_cycle_hours.message}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label>Cycle</Label>
          <Controller
            control={control}
            name="cycle_type"
            render={({ field }) => (
              <div className="grid grid-cols-2 gap-1 h-10 p-1 rounded-md border border-input bg-card">
                {(["70_8", "60_7"] as const).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => field.onChange(opt)}
                    className={cn(
                      "rounded text-xs font-medium transition-colors",
                      field.value === opt
                        ? "bg-foreground text-background"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {opt === "70_8" ? "70 hr / 8 day" : "60 hr / 7 day"}
                  </button>
                ))}
              </div>
            )}
          />
        </div>
      </div>

      {showRestartHint && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          Cycle near limit ({cycleRemaining.toFixed(1)} hr remaining). A 34-hour restart will likely be inserted.
        </div>
      )}

      {!allResolved && (watch("current_location") || watch("pickup_location") || watch("dropoff_location")) && (
        <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-[12px] text-muted-foreground">
          Tip: pick a suggestion from the dropdown to lock the exact location.
        </div>
      )}

      <Button type="submit" size="md" disabled={loading} className="w-full">
        {loading ? "Planning trip…" : "Plan trip"}
      </Button>
    </form>
  );
}
