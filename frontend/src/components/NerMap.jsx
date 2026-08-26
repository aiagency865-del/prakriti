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
  LOCAL: "#64748B",
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

function circlePolygon(lng, lat, radiusKm, points = 72) {
  const coords = [];
  for (let i = 0; i <= points; i++) {
    const angle = (i / points) * 2 * Math.PI;
    const dx = radiusKm * Math.cos(angle);
    const dy = radiusKm * Math.sin(angle);
    coords.push([lng + dx / (111.32 * Math.cos((lat * Math.PI) / 180)), lat + dy / 110.574]);
  }
  return { type: "Feature", geometry: { type: "Polygon", coordinates: [coords] }, properties: {} };
}

export default function NerMap({ roads, vehicles, incidents, layers = {}, onRoadClick, center, zoom, route, zones, environment, endpoints }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const loadedRef = useRef(false);
  const roadsRef = useRef(null);
  const routeRef = useRef(null);
  const zonesRef = useRef(null);
  const envRef = useRef(null);
  const vehMarkersRef = useRef([]);
  const incMarkersRef = useRef([]);
  const envMarkersRef = useRef([]);
  const endMarkersRef = useRef([]);
  const clickRef = useRef(null);
  clickRef.current = onRoadClick;

  useEffect(() => {
    const map = new MLMap({
      container: containerRef.current,
      style: baseStyle,
      center: center || [92.9, 25.8],
      zoom: zoom || 6.2,
      attributionControl: { compact: true },
    });
    map.addControl(new NavigationControl({ showCompass: false }), "bottom-right");
    map.on("load", () => {
      loadedRef.current = true;
      map.addSource("roads", { type: "geojson", data: roadsRef.current || { type: "FeatureCollection", features: [] } });
      map.addSource("route", { type: "geojson", data: routeRef.current || { type: "FeatureCollection", features: [] } });
      map.addSource("zones", { type: "geojson", data: zonesRef.current || { type: "FeatureCollection", features: [] } });
      map.addSource("env", { type: "geojson", data: envRef.current || { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "env-rain-fill", type: "fill", source: "env",
        paint: { "fill-color": "#2563EB", "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "env-rain-line", type: "line", source: "env",
        paint: { "line-color": "#2563EB", "line-opacity": 0.5, "line-width": 1.5, "line-dasharray": [2, 2] },
      });
      map.addLayer({
        id: "zones-fill", type: "fill", source: "zones",
        paint: { "fill-color": "#C4281C", "fill-opacity": 0.10 },
      });
      map.addLayer({
        id: "zones-line", type: "line", source: "zones",
        paint: { "line-color": "#C4281C", "line-opacity": 0.6, "line-width": 1.5, "line-dasharray": [3, 2] },
      });
      map.addLayer({
        id: "route-casing",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#FFFFFF", "line-width": ["interpolate", ["linear"], ["zoom"], 5, 7, 10, 13], "line-opacity": 0.95 },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": [
            "match", ["get", "status"],
            "BLOCKED", STATUS_COLORS.BLOCKED,
            "GOVERNMENT_CLOSED", STATUS_COLORS.GOVERNMENT_CLOSED,
            "AT_RISK", STATUS_COLORS.AT_RISK,
            "RESTRICTED", STATUS_COLORS.RESTRICTED,
            "LOCAL", STATUS_COLORS.LOCAL,
            "#1A73E8",
          ],
          "line-width": ["interpolate", ["linear"], ["zoom"], 5, 4, 10, 8],
          "line-opacity": 1,
        },
      });
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
      map.on("click", "roads-line", (e) => {
        const f = e.features && e.features[0];
        if (f && clickRef.current) clickRef.current(f.properties);
      });
      map.on("mouseenter", "roads-line", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "roads-line", () => { map.getCanvas().style.cursor = ""; });
    });
    mapRef.current = map;
    return () => map.remove();
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (map && loadedRef.current && center) map.jumpTo({ center, zoom: zoom ?? map.getZoom() });
  }, [center, zoom]);

  useEffect(() => {
    roadsRef.current = roads;
    const map = mapRef.current;
    if (!map || !loadedRef.current || !roads) return;
    const src = map.getSource("roads");
    if (src) src.setData(roads);
  }, [roads]);

  useEffect(() => {
    routeRef.current = route;
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const src = map.getSource("route");
    if (src) src.setData(route || { type: "FeatureCollection", features: [] });
  }, [route]);

  useEffect(() => {
    const fc = { type: "FeatureCollection", features: (zones || []).map((z) => circlePolygon(z.lng, z.lat, z.radius_km)) };
    zonesRef.current = fc;
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const src = map.getSource("zones");
    if (src) src.setData(fc);
  }, [zones]);

  useEffect(() => {
    const map = mapRef.current;
    const rain = (environment?.rain || []).map((r) => ({
      ...circlePolygon(r.lng, r.lat, r.radius_km),
      properties: { kind: "RAIN", name: r.name },
    }));
    const fc = { type: "FeatureCollection", features: rain };
    envRef.current = fc;
    if (map && loadedRef.current) {
      const src = map.getSource("env");
      if (src) src.setData(fc);
    }
    if (!map) return;
    envMarkersRef.current.forEach((m) => m.remove());
    envMarkersRef.current = [];
    (environment?.rain || []).forEach((r) => {
      const el = document.createElement("div");
      el.setAttribute("data-testid", `map-rain-${r.id}`);
      el.style.cssText = "padding:2px 7px;border-radius:999px;background:#2563EB;color:#fff;font-size:10px;font-weight:600;font-family:'IBM Plex Mono',monospace;box-shadow:0 1px 4px rgba(0,0,0,.3);display:flex;align-items:center;gap:4px;white-space:nowrap;";
      el.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M16 14v6"/><path d="M8 14v6"/><path d="M12 16v6"/></svg>${r.intensity_mm_h} mm/h`;
      el.title = `${r.name} · ${r.level}`;
      envMarkersRef.current.push(new Marker({ element: el }).setLngLat([r.lng, r.lat]).addTo(map));
    });
    (environment?.landslides || []).forEach((l) => {
      const el = document.createElement("div");
      el.setAttribute("data-testid", `map-landslide-${l.id}`);
      const c = l.probability >= 0.7 ? "#C4281C" : l.probability >= 0.6 ? "#D9622B" : "#C77C00";
      el.style.cssText = `width:0;height:0;border-left:8px solid transparent;border-right:8px solid transparent;border-bottom:14px solid ${c};filter:drop-shadow(0 1px 2px rgba(0,0,0,.4));cursor:pointer;`;
      el.title = `${l.name} · ${l.slide_type.replace("_", " ")} · ${Math.round(l.probability * 100)}%`;
      envMarkersRef.current.push(new Marker({ element: el }).setLngLat([l.lng, l.lat]).addTo(map));
    });
  }, [environment]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    endMarkersRef.current.forEach((m) => m.remove());
    endMarkersRef.current = [];
    (endpoints || []).forEach((p, i) => {
      const el = document.createElement("div");
      el.setAttribute("data-testid", `map-endpoint-${p.label}`);
      const color = i === 0 ? "#1E8E3E" : "#C4281C";
      el.style.cssText = `width:24px;height:24px;border-radius:9999px 9999px 9999px 0;transform:rotate(-45deg);background:${color};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;`;
      el.innerHTML = `<span style="transform:rotate(45deg);color:#fff;font-size:11px;font-weight:700;">${p.label}</span>`;
      endMarkersRef.current.push(new Marker({ element: el, anchor: "bottom" }).setLngLat([p.lng, p.lat]).addTo(map));
    });
  }, [endpoints]);

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
