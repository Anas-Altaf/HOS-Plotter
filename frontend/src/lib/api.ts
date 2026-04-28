import axios from "axios";
import type { TripPlanRequest, TripPlanResponse } from "./types";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL,
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

export async function planTrip(payload: TripPlanRequest): Promise<TripPlanResponse> {
  const res = await api.post<TripPlanResponse>("/api/trip/plan", payload);
  return res.data;
}

export interface AutocompleteResult {
  label: string;
  lat: number;
  lng: number;
}

export async function autocomplete(q: string): Promise<AutocompleteResult[]> {
  if (q.trim().length < 2) return [];
  const res = await api.get<{ results: AutocompleteResult[] }>("/api/geocode/autocomplete", {
    params: { q },
  });
  return res.data.results;
}
