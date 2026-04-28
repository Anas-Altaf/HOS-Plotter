import { useMemo, useState } from "react";
import Map, { Layer, Source, Marker, Popup, type MapRef } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { Fuel, Coffee, Bed, RotateCw, Package, Flag, Navigation } from "lucide-react";
import type { Stop, TripPlanResponse } from "@/lib/types";
import { fmtTime, fmtHours } from "@/lib/utils";

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY;

const STYLE_URL = MAPTILER_KEY
  ? `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_KEY}`
  : {
      version: 8 as const,
      sources: {
        osm: {
          type: "raster" as const,
          tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© OpenStreetMap",
        },
      },
      layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
      glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    };

const stopColor: Record<string, string> = {
  pickup: "#059669",
  dropoff: "#e11d48",
  fuel: "#d97706",
  break_30: "#ca8a04",
  rest_10: "#7c3aed",
  restart_34: "#475569",
};

function StopIcon({ type, className }: { type: string; className?: string }) {
  const C = className ?? "h-3.5 w-3.5";
  if (type === "pickup") return <Package className={C} />;
  if (type === "dropoff") return <Flag className={C} />;
  if (type === "fuel") return <Fuel className={C} />;
  if (type === "break_30") return <Coffee className={C} />;
  if (type === "rest_10") return <Bed className={C} />;
  if (type === "restart_34") return <RotateCw className={C} />;
  return <Navigation className={C} />;
}

interface Props {
  data: TripPlanResponse;
}

export function RouteMap({ data }: Props) {
  const [popup, setPopup] = useState<{ lng: number; lat: number; stop: Stop } | null>(null);
  const [mapRef, setMapRef] = useState<MapRef | null>(null);

  const routeGeoJson = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: [
        {
          type: "Feature" as const,
          properties: {},
          geometry: {
            type: "LineString" as const,
            coordinates: data.route.geometry,
          },
        },
      ],
    }),
    [data.route.geometry]
  );

  const initialView = useMemo(() => {
    const lngs = data.route.geometry.map((c) => c[0]);
    const lats = data.route.geometry.map((c) => c[1]);
    if (!lngs.length) return { longitude: -98, latitude: 39, zoom: 4 };
    const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats);
    return { longitude: (minLng + maxLng) / 2, latitude: (minLat + maxLat) / 2, zoom: 4 };
  }, [data.route.geometry]);

  const fitBounds = () => {
    if (!mapRef) return;
    const lngs = data.route.geometry.map((c) => c[0]);
    const lats = data.route.geometry.map((c) => c[1]);
    if (!lngs.length) return;
    mapRef.fitBounds(
      [
        [Math.min(...lngs), Math.min(...lats)],
        [Math.max(...lngs), Math.max(...lats)],
      ],
      { padding: 60, duration: 600 }
    );
  };

  return (
    <div className="relative h-[52vh] min-h-[400px] rounded-md overflow-hidden border border-border">
      <Map
        ref={(r) => setMapRef(r)}
        initialViewState={initialView}
        mapStyle={STYLE_URL as any}
        onLoad={fitBounds}
      >
        <Source id="route" type="geojson" data={routeGeoJson}>
          <Layer
            id="route-casing"
            type="line"
            paint={{ "line-color": "#0f172a", "line-width": 6, "line-opacity": 0.18 }}
          />
          <Layer
            id="route-line"
            type="line"
            paint={{ "line-color": "#0f172a", "line-width": 2.5 }}
          />
        </Source>

        {data.route.waypoints.map((w, i) => (
          <Marker key={`wp-${i}`} longitude={w.lng} latitude={w.lat} anchor="bottom">
            <div
              className="grid place-items-center h-6 w-6 rounded-full text-white text-[10px] font-semibold ring-2 ring-white shadow"
              style={{ background: w.type === "current" ? "#0f172a" : w.type === "pickup" ? "#059669" : "#e11d48" }}
              title={w.label}
            >
              {w.type === "current" ? "A" : w.type === "pickup" ? "B" : "C"}
            </div>
          </Marker>
        ))}

        {data.stops
          .filter((s) => s.lat != null && s.lng != null && !["pickup", "dropoff"].includes(s.type))
          .map((s, i) => (
            <Marker key={`s-${i}`} longitude={s.lng!} latitude={s.lat!} anchor="bottom">
              <button
                type="button"
                onClick={() => setPopup({ lng: s.lng!, lat: s.lat!, stop: s })}
                className="grid place-items-center h-4 w-4 rounded-full ring-2 ring-white shadow-sm hover:scale-110 transition-transform"
                style={{ background: stopColor[s.type] || "#6b7280" }}
                aria-label={s.label}
              />
            </Marker>
          ))}

        {popup && (
          <Popup
            longitude={popup.lng}
            latitude={popup.lat}
            anchor="top"
            closeOnClick={false}
            onClose={() => setPopup(null)}
            className="font-sans"
          >
            <div className="text-xs space-y-1 min-w-[160px]">
              <div className="font-semibold">{popup.stop.label}</div>
              <div className="text-muted-foreground">Mile {popup.stop.mile.toFixed(0)}</div>
              <div>{fmtTime(popup.stop.start)}</div>
              <div className="text-muted-foreground">Duration: {fmtHours(popup.stop.duration_min)}</div>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
}
