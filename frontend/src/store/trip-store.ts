import { create } from "zustand";
import type { TripPlanRequest, TripPlanResponse } from "@/lib/types";

interface TripState {
  inputs: TripPlanRequest | null;
  result: TripPlanResponse | null;
  loading: boolean;
  error: string | null;
  setInputs: (i: TripPlanRequest) => void;
  setResult: (r: TripPlanResponse) => void;
  setLoading: (b: boolean) => void;
  setError: (e: string | null) => void;
  reset: () => void;
}

const STORAGE_KEY = "hos-plotter:last-result";

const initial: TripPlanResponse | null = (() => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as TripPlanResponse) : null;
  } catch {
    return null;
  }
})();

export const useTripStore = create<TripState>((set) => ({
  inputs: null,
  result: initial,
  loading: false,
  error: null,
  setInputs: (i) => set({ inputs: i }),
  setResult: (r) => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(r));
    set({ result: r });
  },
  setLoading: (b) => set({ loading: b }),
  setError: (e) => set({ error: e }),
  reset: () => {
    sessionStorage.removeItem(STORAGE_KEY);
    set({ inputs: null, result: null, loading: false, error: null });
  },
}));
