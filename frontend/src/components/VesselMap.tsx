import {
  useEffect,
  useRef,
} from "react";

import type {
  FeatureCollection,
  LineString,
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
  Anomaly,
  RecentPosition,
  VesselTrajectory,
} from "../api/types";


interface VesselMapProps {
  positions: RecentPosition[];
  selectedMmsi: string | null;

  trajectory: VesselTrajectory | null;

  anomalies: Anomaly[];

  selectedAnomalyId: number | null;

  onSelectVessel: (mmsi: string) => void;

  onSelectAnomaly: (anomalyId: number) => void;
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


interface AnomalyProperties {
  id: number;
  anomalyType: string;
  severity: string;
  message: string;
  observedAt: string;
}


const VESSEL_SOURCE_ID =
  "recent-vessels";

const VESSEL_LAYER_ID =
  "recent-vessel-points";

const SELECTED_LAYER_ID =
  "selected-vessel-point";

const TRAJECTORY_SOURCE_ID =
  "selected-trajectory";

const TRAJECTORY_LAYER_ID =
  "selected-trajectory-line";

const ANOMALY_SOURCE_ID =
  "selected-anomalies";

const ANOMALY_LAYER_ID =
  "selected-anomaly-points";

const SELECTED_ANOMALY_LAYER_ID =
  "selected-anomaly-highlight";

const NO_SELECTED_ANOMALY = -1;

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


function emptyPointCollection<
  T extends object,
>(): FeatureCollection<Point, T> {
  return {
    type: "FeatureCollection",
    features: [],
  };
}


function emptyLineCollection():
FeatureCollection<LineString> {
  return {
    type: "FeatureCollection",
    features: [],
  };
}


function positionsToGeoJSON(
  positions: RecentPosition[],
): FeatureCollection<
  Point,
  VesselProperties
> {
  return {
    type: "FeatureCollection",

    features: positions.map(
      (position) => ({
        type: "Feature" as const,

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

          timestamp:
            position.timestamp,

          sog:
            position.sog ?? -1,

          cog:
            position.cog ?? -1,

          heading:
            position.heading ?? -1,

          navigationStatus:
            position.navigation_status
            ?? -1,
        },
      }),
    ),
  };
}


interface BackendTrajectoryGeometry {
  type: "Point" | "LineString";
  coordinates: [number, number] | [number, number][];
}

interface BackendTrajectoryResponse {
  geometry: BackendTrajectoryGeometry;
  points?: Array<{
    latitude: number;
    longitude: number;
  }>;
}

function trajectoryToLine(
  trajectory: VesselTrajectory | null,
): FeatureCollection<LineString> {
  if (trajectory === null) {
    return emptyLineCollection();
  }

  const response =
    trajectory as unknown as BackendTrajectoryResponse;

  const geometry = response.geometry;

  if (geometry === undefined || geometry === null) {
    return emptyLineCollection();
  }

  if (geometry.type === "LineString") {
    const coordinates =
      geometry.coordinates as [number, number][];

    const validCoordinates =
      coordinates.filter(
        ([longitude, latitude]) =>
          Number.isFinite(longitude)
          && Number.isFinite(latitude),
      );

    if (validCoordinates.length < 2) {
      return emptyLineCollection();
    }

    return {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: validCoordinates,
          },
        },
      ],
    };
  }

  if (Array.isArray(response.points)) {
    const pointCoordinates =
      response.points
        .map(
          (point) =>
            [
              Number(point.longitude),
              Number(point.latitude),
            ] as [number, number],
        )
        .filter(
          ([longitude, latitude]) =>
            Number.isFinite(longitude)
            && Number.isFinite(latitude),
        );

    if (pointCoordinates.length >= 2) {
      return {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: pointCoordinates,
            },
          },
        ],
      };
    }
  }

  return emptyLineCollection();
}


function anomaliesToGeoJSON(
  anomalies: Anomaly[],
): FeatureCollection<
  Point,
  AnomalyProperties
> {
  const features =
    anomalies
      .filter((anomaly) =>
        Number.isFinite(anomaly.longitude) &&
        Number.isFinite(anomaly.latitude),
      )
      .map((anomaly) => ({
        type: "Feature" as const,

        id: anomaly.id,

        geometry: {
          type: "Point" as const,

          coordinates: [anomaly.longitude, anomaly.latitude],
        },

        properties: {
          id: anomaly.id,

          anomalyType: anomaly.anomaly_type,

          severity: anomaly.severity,

          message: anomaly.message,

          observedAt: anomaly.observed_at,
        },
      }));

  return {
    type: "FeatureCollection",
    features,
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
  const date =
    new Date(timestamp);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return timestamp;
  }

  return date.toLocaleString();
}


function addDetailRow(
  list: HTMLDListElement,
  label: string,
  value: string,
): void {
  const term =
    document.createElement("dt");

  term.textContent = label;


  const description =
    document.createElement("dd");

  description.textContent = value;


  list.append(
    term,
    description,
  );
}


function showVesselPopup(
  map: Map,
  event: MapLayerMouseEvent,
  onSelectVessel:
    (mmsi: string) => void,
): void {
  const feature =
    event.features?.[0];

  if (
    feature === undefined
    || feature.geometry.type
      !== "Point"
  ) {
    return;
  }


  const properties =
    feature.properties as {
      id: number;
      mmsi: string;
      vesselName: string;
      timestamp: string;
      sog: number;
      cog: number;
      heading: number;
      navigationStatus: number;
    };

  const mmsi =
    String(properties.mmsi);

  onSelectVessel(mmsi);


  const coordinates = [
    Number(
      feature.geometry
        .coordinates[0],
    ),

    Number(
      feature.geometry
        .coordinates[1],
    ),
  ] as [number, number];


  const container =
    document.createElement("div");

  container.className =
    "vessel-popup";


  const title =
    document.createElement(
      "strong",
    );

  title.textContent =
    properties.vesselName
    || "Unknown vessel";


  const details =
    document.createElement("dl");


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
    formatTimestamp(
      properties.timestamp,
    ),
  );


  container.append(
    title,
    details,
  );


  new maplibregl.Popup({
    closeButton: true,
    maxWidth: "320px",
  })
    .setLngLat(coordinates)
    .setDOMContent(container)
    .addTo(map);
}


function showAnomalyPopup(
  map: Map,
  event: MapLayerMouseEvent,
): void {
  const feature =
    event.features?.[0];

  if (
    feature === undefined
    || feature.geometry.type
      !== "Point"
  ) {
    return;
  }


  const properties =
    feature.properties as unknown as
      AnomalyProperties;


  const coordinates = [
    Number(
      feature.geometry
        .coordinates[0],
    ),

    Number(
      feature.geometry
        .coordinates[1],
    ),
  ] as [number, number];


  const container =
    document.createElement("div");

  container.className =
    "anomaly-popup";


  const title =
    document.createElement(
      "strong",
    );

  title.textContent =
    properties.anomalyType
      .replaceAll("_", " ");


  const severity =
    document.createElement("span");

  severity.textContent =
    `Severity: ${properties.severity}`;


  const timestamp =
    document.createElement("span");

  timestamp.textContent =
    formatTimestamp(
      properties.observedAt,
    );


  const message =
    document.createElement("p");

  message.textContent =
    properties.message;


  container.append(
    title,
    severity,
    timestamp,
    message,
  );


  new maplibregl.Popup({
    closeButton: true,
    maxWidth: "360px",
  })
    .setLngLat(coordinates)
    .setDOMContent(container)
    .addTo(map);
}


export function VesselMap({
  positions,
  selectedMmsi,
  trajectory,
  anomalies,
  selectedAnomalyId,
  onSelectVessel,
  onSelectAnomaly,
}: VesselMapProps) {
  const containerRef =
    useRef<HTMLDivElement | null>(
      null,
    );

  const mapRef =
    useRef<Map | null>(null);

  const onSelectVesselRef =
    useRef(onSelectVessel);

  const onSelectAnomalyRef =
  useRef(onSelectAnomaly);

  const hasFittedBoundsRef =
    useRef(false);


  useEffect(() => {
    onSelectVesselRef.current =
      onSelectVessel;
  }, [onSelectVessel]);

  useEffect(() => {
  onSelectAnomalyRef.current =
    onSelectAnomaly;
}, [onSelectAnomaly]);


  /*
   * Create the MapLibre map once.
   */
  useEffect(() => {
    if (
      containerRef.current
        === null
      || mapRef.current !== null
    ) {
      return;
    }


    const map =
      new maplibregl.Map({
        container:
          containerRef.current,

        style:
          MAP_STYLE,

        center: [
          23.72,
          37.98,
        ],

        zoom: 5,
      });


    map.addControl(
      new maplibregl
        .NavigationControl(),
      "top-right",
    );


    map.addControl(
      new maplibregl
        .FullscreenControl(),
      "top-right",
    );


    map.on("load", () => {
      /*
       * Selected vessel trajectory.
       * Added first so vessel/anomaly
       * markers remain above the line.
       */
      map.addSource(
        TRAJECTORY_SOURCE_ID,
        {
          type: "geojson",

          data:
            emptyLineCollection(),
        },
      );


      map.addLayer({
        id:
          TRAJECTORY_LAYER_ID,

        type: "line",

        source:
          TRAJECTORY_SOURCE_ID,

        paint: {
          "line-color":
            "#f59e0b",

          "line-width": 4,

          "line-opacity": 0.85,
        },
      });


      /*
       * Recent vessel positions.
       */
      map.addSource(
        VESSEL_SOURCE_ID,
        {
          type: "geojson",

          data:
            positionsToGeoJSON([]),
        },
      );


      map.addLayer({
        id: VESSEL_LAYER_ID,

        type: "circle",

        source:
          VESSEL_SOURCE_ID,

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

          "circle-color":
            "#22d3ee",

          "circle-stroke-color":
            "#083344",

          "circle-stroke-width":
            2,

          "circle-opacity":
            0.9,
        },
      });


      /*
       * Highlight selected vessel.
       */
      map.addLayer({
        id:
          SELECTED_LAYER_ID,

        type: "circle",

        source:
          VESSEL_SOURCE_ID,

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

          "circle-color":
            "#f59e0b",

          "circle-stroke-color":
            "#ffffff",

          "circle-stroke-width":
            3,

          "circle-opacity":
            1,
        },
      });


      /*
       * Anomaly positions.
       */
      map.addSource(
        ANOMALY_SOURCE_ID,
        {
          type: "geojson",

          data:
            emptyPointCollection<
              AnomalyProperties
            >(),
        },
      );


      map.addLayer({
        id:
          ANOMALY_LAYER_ID,

        type: "circle",

        source:
          ANOMALY_SOURCE_ID,

        paint: {
          "circle-radius": 7,

          "circle-color": [
            "match",

            [
              "downcase",
              [
                "to-string",
                ["get", "severity"],
              ],
            ],

            "critical",
            "#dc2626",

            "high",
            "#f97316",

            "warning",
            "#facc15",

            "#a855f7",
          ],

          "circle-stroke-color":
            "#ffffff",

          "circle-stroke-width":
            2,

          "circle-opacity":
            0.95,
        },
      });


      map.addLayer({
        id:
          SELECTED_ANOMALY_LAYER_ID,

        type: "circle",

        source:
          ANOMALY_SOURCE_ID,

        filter: [
          "==",
          ["get", "id"],
          NO_SELECTED_ANOMALY,
        ],

        paint: {
          "circle-radius": 12,

          "circle-color":
            "rgba(0, 0, 0, 0)",

          "circle-stroke-color":
            "#ffffff",

          "circle-stroke-width": 4,

          "circle-opacity": 1,
        },
      });


      /*
       * Vessel interactions.
       */
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
          map.getCanvas()
            .style.cursor =
            "pointer";
        },
      );


      map.on(
        "mouseleave",
        VESSEL_LAYER_ID,
        () => {
          map.getCanvas()
            .style.cursor = "";
        },
      );


      /*
       * Anomaly interactions.
       */
      map.on(
        "click",
        ANOMALY_LAYER_ID,
        (event: MapLayerMouseEvent) => {
          const feature =
            event.features?.[0];

          if (feature !== undefined) {
            const anomalyId =
              Number(
                feature.properties?.id,
              );

            if (Number.isFinite(anomalyId)) {
              onSelectAnomalyRef.current(
                anomalyId,
              );
            }
          }

          showAnomalyPopup(
            map,
            event,
          );
        },
      );


      map.on(
        "mouseenter",
        ANOMALY_LAYER_ID,
        () => {
          map.getCanvas()
            .style.cursor =
            "pointer";
        },
      );


      map.on(
        "mouseleave",
        ANOMALY_LAYER_ID,
        () => {
          map.getCanvas()
            .style.cursor = "";
        },
      );
    });


    mapRef.current = map;


    return () => {
      map.remove();

      mapRef.current = null;

      hasFittedBoundsRef.current =
        false;
    };
  }, []);


  /*
   * Update recent vessel positions.
   */
  useEffect(() => {
    const map =
      mapRef.current;

    if (map === null) {
      return;
    }


    const updateSource = () => {
      const source =
        map.getSource(
          VESSEL_SOURCE_ID,
        ) as
          | GeoJSONSource
          | undefined;


      if (source === undefined) {
        return;
      }


      source.setData(
        positionsToGeoJSON(
          positions,
        ),
      );


      if (
        positions.length === 0
        || hasFittedBoundsRef
          .current
      ) {
        return;
      }


      if (
        positions.length === 1
      ) {
        map.flyTo({
          center: [
            positions[0].longitude,
            positions[0].latitude,
          ],

          zoom: 10,
        });


        hasFittedBoundsRef.current =
          true;

        return;
      }


      const bounds =
        new maplibregl
          .LngLatBounds();


      for (
        const position
        of positions
      ) {
        bounds.extend([
          position.longitude,
          position.latitude,
        ]);
      }


      map.fitBounds(
        bounds,
        {
          padding: 70,
          maxZoom: 11,
          duration: 800,
        },
      );


      hasFittedBoundsRef.current =
        true;
    };


    if (
      map.isStyleLoaded()
      && map.getSource(
        VESSEL_SOURCE_ID,
      )
    ) {
      updateSource();

      return;
    }


    map.once(
      "load",
      updateSource,
    );


    return () => {
      map.off(
        "load",
        updateSource,
      );
    };
  }, [positions]);


  /*
   * Highlight selected vessel.
   */
  useEffect(() => {
    const map =
      mapRef.current;

    if (map === null) {
      return;
    }


    const updateSelection =
      () => {
        if (
          map.getLayer(
            SELECTED_LAYER_ID,
          ) === undefined
        ) {
          return;
        }


        map.setFilter(
          SELECTED_LAYER_ID,
          [
            "==",

            [
              "get",
              "mmsi",
            ],

            selectedMmsi
            ?? NO_SELECTED_VESSEL,
          ],
        );


        if (
          selectedMmsi === null
        ) {
          return;
        }


        const selectedPosition =
          positions.find(
            (position) =>
              position.mmsi
              === selectedMmsi,
          );


        if (
          selectedPosition
          === undefined
        ) {
          return;
        }


        map.easeTo({
          center: [
            selectedPosition
              .longitude,

            selectedPosition
              .latitude,
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
      && map.getLayer(
        SELECTED_LAYER_ID,
      )
    ) {
      updateSelection();

      return;
    }


    map.once(
      "load",
      updateSelection,
    );


    return () => {
      map.off(
        "load",
        updateSelection,
      );
    };
  }, [
    positions,
    selectedMmsi,
  ]);


  /*
   * Draw selected trajectory.
   */
  useEffect(() => {
    const map =
      mapRef.current;

    if (map === null) {
      return;
    }


    const updateTrajectory =
      () => {
        const source =
          map.getSource(
            TRAJECTORY_SOURCE_ID,
          ) as
            | GeoJSONSource
            | undefined;


        if (
          source === undefined
        ) {
          return;
        }


        const line =
          trajectoryToLine(
            trajectory,
          );


        source.setData(line);


        const coordinates =
          line.features[0]
            ?.geometry
            .coordinates;


        if (
          coordinates
            === undefined
          || coordinates.length < 2
        ) {
          return;
        }


        const bounds =
          new maplibregl
            .LngLatBounds();


        for (
          const coordinate
          of coordinates
        ) {
          bounds.extend([
            coordinate[0],
            coordinate[1],
          ]);
        }


        map.fitBounds(
          bounds,
          {
            padding: 90,
            maxZoom: 12,
            duration: 700,
          },
        );
      };


    if (
      map.isStyleLoaded()
      && map.getSource(
        TRAJECTORY_SOURCE_ID,
      )
    ) {
      updateTrajectory();

      return;
    }


    map.once(
      "load",
      updateTrajectory,
    );


    return () => {
      map.off(
        "load",
        updateTrajectory,
      );
    };
  }, [trajectory]);


  /*
   * Update anomaly markers.
   */
  useEffect(() => {
    const map =
      mapRef.current;

    if (map === null) {
      return;
    }


    const updateAnomalies =
      () => {
        const source =
          map.getSource(
            ANOMALY_SOURCE_ID,
          ) as
            | GeoJSONSource
            | undefined;


        if (
          source === undefined
        ) {
          return;
        }


        source.setData(
          anomaliesToGeoJSON(
            anomalies,
          ),
        );
      };


    if (
      map.isStyleLoaded()
      && map.getSource(
        ANOMALY_SOURCE_ID,
      )
    ) {
      updateAnomalies();

      return;
    }


    map.once(
      "load",
      updateAnomalies,
    );


    return () => {
      map.off(
        "load",
        updateAnomalies,
      );
    };
  }, [anomalies]);


  /*
   * Highlight and focus the selected anomaly.
   */
  useEffect(() => {
    const map =
      mapRef.current;

    if (map === null) {
      return;
    }


    const updateSelectedAnomaly = () => {
      if (
        map.getLayer(
          SELECTED_ANOMALY_LAYER_ID,
        ) === undefined
      ) {
        return;
      }


      map.setFilter(
        SELECTED_ANOMALY_LAYER_ID,
        [
          "==",
          ["get", "id"],
          selectedAnomalyId
          ?? NO_SELECTED_ANOMALY,
        ],
      );


      if (selectedAnomalyId === null) {
        return;
      }


      const selectedAnomaly =
        anomalies.find(
          (anomaly) =>
            anomaly.id
            === selectedAnomalyId,
        );

      if (selectedAnomaly === undefined) {
        return;
      }


      if (
        !Number.isFinite(
          selectedAnomaly.longitude,
        )
        || !Number.isFinite(
          selectedAnomaly.latitude,
        )
      ) {
        return;
      }


      map.flyTo({
        center: [
          selectedAnomaly.longitude,
          selectedAnomaly.latitude,
        ],

        zoom: Math.max(
          map.getZoom(),
          13,
        ),

        duration: 700,
      });
    };


    if (
      map.isStyleLoaded()
      && map.getLayer(
        SELECTED_ANOMALY_LAYER_ID,
      )
    ) {
      updateSelectedAnomaly();

      return;
    }


    map.once(
      "load",
      updateSelectedAnomaly,
    );


    return () => {
      map.off(
        "load",
        updateSelectedAnomaly,
      );
    };
  }, [
    anomalies,
    selectedAnomalyId,
  ]);


  return (
    <div
      ref={containerRef}
      className="vessel-map"
      aria-label={
        "Map of recent vessel positions"
      }
    />
  );
}