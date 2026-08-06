import {
  useEffect,
  useRef,
} from "react";

import type {
  FeatureCollection,
  Point,
} from "geojson";

import * as maplibregl from "maplibre-gl";
import type {
  GeoJSONSource,
  Map,
  MapLayerMouseEvent,
} from "maplibre-gl";

import "maplibre-gl/dist/maplibre-gl.css";

import type {
  RecentPosition,
} from "../api/types";


interface VesselMapProps {
  positions: RecentPosition[];
}


interface VesselProperties {
  id: number;
  mmsi: string;
  vesselName: string;
  timestamp: string;
  sog: number;
  cog: number;
  heading: number;
}


const SOURCE_ID = "recent-vessels";
const LAYER_ID = "recent-vessel-points";


function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function displayMeasurement(
  value: number,
  unit: string,
): string {
  if (value < 0) {
    return "Not available";
  }

  return `${value.toFixed(1)} ${unit}`;
}


function positionsToGeoJSON(
  positions: RecentPosition[],
): FeatureCollection<Point, VesselProperties> {
  return {
    type: "FeatureCollection",
    features: positions.map((position) => ({
      type: "Feature",
      id: position.id,
      geometry: {
        type: "Point",
        coordinates: [
          position.longitude,
          position.latitude,
        ],
      },
      properties: {
        id: position.id,
        mmsi: position.mmsi,
        vesselName:
          position.vessel_name
          ?? "Unknown vessel",
        timestamp: position.timestamp,
        sog: position.sog ?? -1,
        cog: position.cog ?? -1,
        heading: position.heading ?? -1,
      },
    })),
  };
}


function showVesselPopup(
  map: Map,
  event: MapLayerMouseEvent,
): void {
  const feature = event.features?.[0];

  if (
    feature === undefined
    || feature.geometry.type !== "Point"
  ) {
    return;
  }

  const properties =
    feature.properties as VesselProperties;

  const coordinates = (
    feature.geometry.coordinates.slice()
  ) as [number, number];

  const popupHtml = `
    <div class="vessel-popup">
      <strong>
        ${escapeHtml(properties.vesselName)}
      </strong>

      <dl>
        <dt>MMSI</dt>
        <dd>${escapeHtml(properties.mmsi)}</dd>

        <dt>Reported speed</dt>
        <dd>
          ${escapeHtml(
            displayMeasurement(
              Number(properties.sog),
              "kn",
            ),
          )}
        </dd>

        <dt>Course</dt>
        <dd>
          ${escapeHtml(
            displayMeasurement(
              Number(properties.cog),
              "°",
            ),
          )}
        </dd>

        <dt>Heading</dt>
        <dd>
          ${escapeHtml(
            displayMeasurement(
              Number(properties.heading),
              "°",
            ),
          )}
        </dd>

        <dt>Timestamp</dt>
        <dd>
          ${escapeHtml(
            new Date(
              properties.timestamp,
            ).toLocaleString(),
          )}
        </dd>
      </dl>
    </div>
  `;

  new maplibregl.Popup({
    closeButton: true,
    maxWidth: "320px",
  })
    .setLngLat(coordinates)
    .setHTML(popupHtml)
    .addTo(map);
}


export function VesselMap({
  positions,
}: VesselMapProps) {
  const containerRef =
    useRef<HTMLDivElement | null>(null);

  const mapRef = useRef<Map | null>(null);
  const hasFittedBounds = useRef(false);

  useEffect(() => {
    if (
      containerRef.current === null
      || mapRef.current !== null
    ) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style:
        "https://demotiles.maplibre.org/style.json",
      center: [0, 20],
      zoom: 1.5,
    });

    map.addControl(
      new maplibregl.NavigationControl(),
      "top-right",
    );

    map.addControl(
      new maplibregl.FullscreenControl(),
      "top-right",
    );

    map.on("load", () => {
      map.addSource(
        SOURCE_ID,
        {
          type: "geojson",
          data: positionsToGeoJSON([]),
        },
      );

      map.addLayer({
        id: LAYER_ID,
        type: "circle",
        source: SOURCE_ID,
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            2,
            4,
            12,
            8,
          ],
          "circle-color": "#22d3ee",
          "circle-stroke-color": "#083344",
          "circle-stroke-width": 2,
          "circle-opacity": 0.9,
        },
      });

      map.on(
        "click",
        LAYER_ID,
        (event: MapLayerMouseEvent) => {
          showVesselPopup(map, event);
        },
      );

      map.on(
        "mouseenter",
        LAYER_ID,
        () => {
          map.getCanvas().style.cursor =
            "pointer";
        },
      );

      map.on(
        "mouseleave",
        LAYER_ID,
        () => {
          map.getCanvas().style.cursor = "";
        },
      );
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const updateSource = () => {
      const source = map.getSource(
        SOURCE_ID,
      ) as GeoJSONSource | undefined;

      if (source === undefined) {
        return;
      }

      source.setData(
        positionsToGeoJSON(positions),
      );

      if (
        positions.length === 0
        || hasFittedBounds.current
      ) {
        return;
      }

      if (positions.length === 1) {
        map.flyTo({
          center: [
            positions[0].longitude,
            positions[0].latitude,
          ],
          zoom: 10,
        });

        hasFittedBounds.current = true;
        return;
      }

      const bounds =
        new maplibregl.LngLatBounds();

      for (const position of positions) {
        bounds.extend([
          position.longitude,
          position.latitude,
        ]);
      }

      map.fitBounds(bounds, {
        padding: 70,
        maxZoom: 11,
        duration: 800,
      });

      hasFittedBounds.current = true;
    };

    if (
      map.isStyleLoaded()
      && map.getSource(SOURCE_ID)
    ) {
      updateSource();
      return;
    }

    map.once("load", updateSource);

    return () => {
      map.off("load", updateSource);
    };
  }, [positions]);

  return (
    <div
      ref={containerRef}
      className="vessel-map"
      aria-label="Map of recent vessel positions"
    />
  );
}