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
  StyleSpecification,
} from "maplibre-gl";

import "maplibre-gl/dist/maplibre-gl.css";

import type {
  RecentPosition,
} from "../api/types";


interface VesselMapProps {
  positions: RecentPosition[];
  selectedMmsi: string | null;
  onSelectVessel: (mmsi: string) => void;
}


interface VesselProperties {
  id: number;
  mmsi: string;
  vesselName: string;
  timestamp: string;
  sog: number;
  cog: number;
  heading: number;
  navigationStatus: number;
}


const SOURCE_ID = "recent-vessels";
const VESSEL_LAYER_ID = "recent-vessel-points";
const SELECTED_LAYER_ID = "selected-vessel-point";

const NO_SELECTED_VESSEL =
  "__no_selected_vessel__";


const MAP_STYLE: StyleSpecification = {
  version: 8,

  sources: {
    openStreetMap: {
      type: "raster",
      tiles: [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution:
        "© OpenStreetMap contributors",
    },
  },

  layers: [
    {
      id: "openstreetmap",
      type: "raster",
      source: "openStreetMap",
    },
  ],
};


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
        navigationStatus:
          position.navigation_status ?? -1,
      },
    })),
  };
}


function formatMeasurement(
  value: number,
  unit: string,
): string {
  if (
    !Number.isFinite(value)
    || value < 0
  ) {
    return "Not available";
  }

  return `${value.toFixed(1)} ${unit}`;
}


function formatTimestamp(
  timestamp: string,
): string {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return date.toLocaleString();
}


function addDetailRow(
  list: HTMLDListElement,
  label: string,
  value: string,
): void {
  const term = document.createElement("dt");
  term.textContent = label;

  const description =
    document.createElement("dd");

  description.textContent = value;

  list.append(term, description);
}


function showVesselPopup(
  map: Map,
  event: MapLayerMouseEvent,
  onSelectVessel: (mmsi: string) => void,
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

  const mmsi = String(properties.mmsi);

  onSelectVessel(mmsi);

  const coordinates = [
    Number(feature.geometry.coordinates[0]),
    Number(feature.geometry.coordinates[1]),
  ] as [number, number];

  const container =
    document.createElement("div");

  container.className = "vessel-popup";

  const title = document.createElement("strong");

  title.textContent =
    properties.vesselName
    || "Unknown vessel";

  const details = document.createElement("dl");

  addDetailRow(
    details,
    "MMSI",
    mmsi,
  );

  addDetailRow(
    details,
    "Speed",
    formatMeasurement(
      Number(properties.sog),
      "kn",
    ),
  );

  addDetailRow(
    details,
    "Course",
    formatMeasurement(
      Number(properties.cog),
      "°",
    ),
  );

  addDetailRow(
    details,
    "Heading",
    formatMeasurement(
      Number(properties.heading),
      "°",
    ),
  );

  addDetailRow(
    details,
    "Timestamp",
    formatTimestamp(properties.timestamp),
  );

  container.append(title, details);

  new maplibregl.Popup({
    closeButton: true,
    maxWidth: "320px",
  })
    .setLngLat(coordinates)
    .setDOMContent(container)
    .addTo(map);
}


export function VesselMap({
  positions,
  selectedMmsi,
  onSelectVessel,
}: VesselMapProps) {
  const containerRef =
    useRef<HTMLDivElement | null>(null);

  const mapRef = useRef<Map | null>(null);

  const onSelectVesselRef = useRef(
    onSelectVessel,
  );

  const hasFittedBoundsRef =
    useRef(false);


  useEffect(() => {
    onSelectVesselRef.current =
      onSelectVessel;
  }, [onSelectVessel]);


  useEffect(() => {
    if (
      containerRef.current === null
      || mapRef.current !== null
    ) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [23.72, 37.98],
      zoom: 5,
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
        id: VESSEL_LAYER_ID,
        type: "circle",
        source: SOURCE_ID,

        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            3,
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


      map.addLayer({
        id: SELECTED_LAYER_ID,
        type: "circle",
        source: SOURCE_ID,

        filter: [
          "==",
          ["get", "mmsi"],
          NO_SELECTED_VESSEL,
        ],

        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            3,
            8,
            12,
            14,
          ],

          "circle-color": "#f59e0b",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 3,
          "circle-opacity": 1,
        },
      });


      map.on(
        "click",
        VESSEL_LAYER_ID,
        (event: MapLayerMouseEvent) => {
          showVesselPopup(
            map,
            event,
            onSelectVesselRef.current,
          );
        },
      );


      map.on(
        "mouseenter",
        VESSEL_LAYER_ID,
        () => {
          map.getCanvas().style.cursor =
            "pointer";
        },
      );


      map.on(
        "mouseleave",
        VESSEL_LAYER_ID,
        () => {
          map.getCanvas().style.cursor = "";
        },
      );
    });


    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      hasFittedBoundsRef.current = false;
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
        || hasFittedBoundsRef.current
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

        hasFittedBoundsRef.current = true;
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

      hasFittedBoundsRef.current = true;
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


  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }


    const updateSelection = () => {
      if (
        map.getLayer(SELECTED_LAYER_ID)
        === undefined
      ) {
        return;
      }

      map.setFilter(
        SELECTED_LAYER_ID,
        [
          "==",
          ["get", "mmsi"],
          selectedMmsi
          ?? NO_SELECTED_VESSEL,
        ],
      );


      if (selectedMmsi === null) {
        return;
      }

      const selectedPosition =
        positions.find(
          (position) =>
            position.mmsi
            === selectedMmsi,
        );

      if (selectedPosition === undefined) {
        return;
      }

      map.easeTo({
        center: [
          selectedPosition.longitude,
          selectedPosition.latitude,
        ],
        zoom: Math.max(
          map.getZoom(),
          9,
        ),
        duration: 700,
      });
    };


    if (
      map.isStyleLoaded()
      && map.getLayer(SELECTED_LAYER_ID)
    ) {
      updateSelection();
      return;
    }

    map.once("load", updateSelection);

    return () => {
      map.off("load", updateSelection);
    };
  }, [
    positions,
    selectedMmsi,
  ]);


  return (
    <div
      ref={containerRef}
      className="vessel-map"
      aria-label="Map of recent vessel positions"
    />
  );
}