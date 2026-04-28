export type StopType =
  | "pickup"
  | "dropoff"
  | "fuel"
  | "break_30"
  | "rest_10"
  | "restart_34";

export type DutyStatus = "OFF" | "SB" | "D" | "ON";

export interface Waypoint {
  label: string;
  lat: number;
  lng: number;
  type: "current" | "pickup" | "dropoff";
}

export interface RouteLeg {
  from: string;
  to: string;
  distance_mi: number;
  duration_min: number;
}

export interface Stop {
  type: StopType;
  label: string;
  lat: number | null;
  lng: number | null;
  mile: number;
  start: string;
  end: string;
  duration_min: number;
}

export interface LogSegment {
  status: DutyStatus;
  start_min: number;
  end_min: number;
}

export interface LogRemark {
  time_min: number;
  text: string;
}

export interface DailyLog {
  date: string;
  from_location: string;
  to_location: string;
  segments: LogSegment[];
  totals: Record<DutyStatus, number>;
  total_miles_today: number;
  remarks: LogRemark[];
  recap: Record<string, { A: number; B: number; C: number }>;
}

export interface TripPlanResponse {
  route: {
    geometry: [number, number][];
    total_distance_mi: number;
    total_drive_minutes: number;
    legs: RouteLeg[];
    waypoints: Waypoint[];
  };
  stops: Stop[];
  logs: DailyLog[];
  summary: {
    total_distance_mi: number;
    total_duration_min: number;
    trip_start: string;
    trip_end: string;
    log_days: number;
  };
}

export interface CoordHint {
  label: string;
  lat: number;
  lng: number;
}

export interface TripPlanRequest {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_coord?: CoordHint;
  pickup_coord?: CoordHint;
  dropoff_coord?: CoordHint;
  current_cycle_hours: number;
  cycle_type: "70_8" | "60_7";
  start_time?: string;
}
