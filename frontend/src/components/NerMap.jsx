import { useEffect, useRef } from "react";
import { Map as MLMap, NavigationControl, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export const STATUS_COLORS = {
  OPEN: "#1E8E3E",
  AT_RISK: "#C77C00",
  RESTRICTED: "#D9622B",
  BLOCKED: "#C4281C",
  GOVERNMENT_CLOSED: "#8A1512",
  UNKNOWN: "#8A9099",
};

const baseStyle = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#EEF0F3" } },
    {
      id: "osm",
      type: "raster",
      source: "osm",
      paint: {
        "raster-opacity": 0.55,
        "raster-saturation": -0.75,
        "raster-brightness-min": 0.05,
        "raster-brightness-max": 1.0,
      },
    },
  ],
};

function vehicleColor(risk) {
  if (risk >= 60) return STATUS_COLORS.BLOCKED;
  if (risk >= 30) return STATUS_COLORS.AT_RISK;
  return STATUS_COLORS.OPEN;
}

export default function NerMap({ roads, vehicles, incidents, layers }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const loadedRef = useRef(false);
  const roadsRef = useRef(null);
  const vehMarkersRef = useRef([]);
  const incMarkersRef = useRef([]);

  useEffect(() => {
    const map = new MLMap({
      container: containerRef.current,
      style: baseStyle,
      center: [92.9, 25.8],
      zoom: 6.2,
      attributionControl: { compact: true },
    });
    map.addControl(new NavigationControl({ showCompass: false }), "bottom-right");
    map.on("load", () => {
      loadedRef.current = true;
      map.addSource("roads", { type: "geojson", data: roadsRef.current || { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "roads-casing",
        type: "line",
        source: "roads",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#FFFFFF",
          "line-width": ["interpolate", ["linear"], ["zoom"], 5, 4, 10, 9],
          "line-opacity": 0.9,
        },
      });
      map.addLayer({
        id: "roads-line",
        type: "line",
        source: "roads",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": [
            "match", ["get", "status"],
            "OPEN", STATUS_COLORS.OPEN,
            "AT_RISK", STATUS_COLORS.AT_RISK,
            "RESTRICTED", STATUS_COLORS.RESTRICTED,
            "BLOCKED", STATUS_COLORS.BLOCKED,
            "GOVERNMENT_CLOSED", STATUS_COLORS.GOVERNMENT_CLOSED,
            STATUS_COLORS.UNKNOWN,
          ],
          "line-width": ["interpolate", ["linear"], ["zoom"], 5, 2.2, 10, 5.5],
          "line-opacity": 0.95,
        },
      });
    });
    mapRef.current = map;
    return () => map.remove();
  }, []);

  useEffect(() => {
    roadsRef.current = roads;
    const map = mapRef.current;
    if (!map || !loadedRef.current || !roads) return;
    const src = map.getSource("roads");
    if (src) src.setData(roads);
  }, [roads]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    if (map.getLayer("roads-casing")) {
      const v = layers.roads ? "visible" : "none";
      map.setLayoutProperty("roads-casing", "visibility", v);
      map.setLayoutProperty("roads-line", "visibility", v);
    }
  }, [layers.roads]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    vehMarkersRef.current.forEach((m) => m.remove());
    vehMarkersRef.current = [];
    if (!layers.vehicles || !vehicles) return;
    vehicles.forEach((v) => {
      const el = document.createElement("div");
      el.setAttribute("data-testid", `map-vehicle-${v.id}`);
      el.style.cssText = `width:20px;height:20px;border-radius:9999px;background:${vehicleColor(v.risk)};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;cursor:pointer;`;
      el.innerHTML = `<div style="width:2.5px;height:9px;background:#fff;border-radius:2px;transform:rotate(${v.heading || 0}deg)"></div>`;
      el.title = `${v.number} · ${v.type} · risk ${v.risk}`;
      const m = new Marker({ element: el }).setLngLat([v.lng, v.lat]).addTo(map);
      vehMarkersRef.current.push(m);
    });
  }, [vehicles, layers.vehicles]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    incMarkersRef.current.forEach((m) => m.remove());
    incMarkersRef.current = [];
    if (!layers.incidents || !incidents) return;
    incidents.forEach((i) => {
      const el = document.createElement("div");
      el.setAttribute("data-testid", `map-incident-${i.id}`);
      el.style.cssText = `width:15px;height:15px;background:${SEVERITY[i.severity] || "#8A9099"};border:2px solid #fff;transform:rotate(45deg);border-radius:3px;box-shadow:0 1px 4px rgba(0,0,0,.35);cursor:pointer;`;
      el.title = `${i.id} · ${i.title}`;
      const m = new Marker({ element: el }).setLngLat([i.lng, i.lat]).addTo(map);
      incMarkersRef.current.push(m);
    });
  }, [incidents, layers.incidents]);

  return <div ref={containerRef} style={{ position: "absolute", top: 0, right: 0, bottom: 0, left: 0 }} data-testid="neris-map" />;
}

const SEVERITY = { INFO: "#4C7EA8", WARNING: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C" };
