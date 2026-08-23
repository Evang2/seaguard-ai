import { useEffect, useRef } from "react";

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
  CollisionEncounter,
  RecentPosition,
  RiskAssessment,
  VesselTrajectory,
} from "../api/types";

interface VesselMapProps {
  positions: RecentPosition[];
  selectedMmsi: string | null;
  trajectory: VesselTrajectory | null;
  anomalies: Anomaly[];
  riskAssessments: RiskAssessment[];
  collisionEncounters: CollisionEncounter[];
  selectedAnomalyId: number | null;
  selectedRiskId: number | null;
  selectedCollisionId: number | null;
  onSelectVessel: (mmsi: string) => void;
  onSelectAnomaly: (anomalyId: number) => void;
  onSelectRisk: (riskId: number) => void;
  onSelectCollision: (collisionId: number) => void;
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

interface RiskProperties {
  id: number;
  riskLevel: string;
  mlPercentile: number;
  ruleSeverity: string;
  ruleFlagCount: number;
  detectorAgreement: boolean;
  observedAt: string;
  reasons: string;
}

interface CollisionProperties {
  id: number;
  riskLevel: string;
  vesselAMmsi: string;
  vesselAName: string;
  vesselBMmsi: string;
  vesselBName: string;
  currentDistanceNm: number;
  cpaDistanceNm: number;
  tcpaMinutes: number | null;
  relativeSpeedKnots: number;
  closingSpeedKnots: number;
  observedAt: string;
}

interface BackendTrajectoryResponse {
  geometry?: {
    type?: string;
    coordinates?: [number, number][];
  };
  points?: Array<{
    longitude: number;
    latitude: number;
  }>;
}

const VESSEL_SOURCE_ID = "recent-vessels";
const VESSEL_LAYER_ID = "recent-vessel-points";
const SELECTED_VESSEL_LAYER_ID = "selected-vessel-point";

const TRAJECTORY_SOURCE_ID = "selected-trajectory";
const TRAJECTORY_LAYER_ID = "selected-trajectory-line";

const COLLISION_SOURCE_ID = "collision-encounters";
const COLLISION_LAYER_ID = "collision-encounter-lines";
const SELECTED_COLLISION_LAYER_ID = "selected-collision-encounter";
const COLLISION_HITBOX_LAYER_ID = "collision-encounter-hitbox";

const COLLISION_MARKER_SOURCE_ID = "collision-encounter-markers";
const COLLISION_MARKER_LAYER_ID = "collision-encounter-markers-visible";
const SELECTED_COLLISION_MARKER_LAYER_ID =
  "selected-collision-encounter-marker";
const COLLISION_MARKER_HITBOX_LAYER_ID =
  "collision-encounter-marker-hitbox";

const RISK_SOURCE_ID = "selected-risk-assessments";
const RISK_LAYER_ID = "selected-risk-points";
const SELECTED_RISK_LAYER_ID = "selected-risk-highlight";

const ANOMALY_SOURCE_ID = "selected-anomalies";
const ANOMALY_LAYER_ID = "selected-anomaly-points";
const SELECTED_ANOMALY_LAYER_ID = "selected-anomaly-highlight";

const NO_SELECTED_VESSEL = "__no_selected_vessel__";
const NO_SELECTED_ANOMALY = -1;
const NO_SELECTED_RISK = -1;
const NO_SELECTED_COLLISION = -1;

const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    openStreetMap: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
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

function emptyPointCollection<T extends object>(): FeatureCollection<Point, T> {
  return {
    type: "FeatureCollection",
    features: [],
  };
}

function emptyLineCollection(): FeatureCollection<LineString> {
  return {
    type: "FeatureCollection",
    features: [],
  };
}

function emptyCollisionCollection(): FeatureCollection<
  LineString,
  CollisionProperties
> {
  return {
    type: "FeatureCollection",
    features: [],
  };
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
        coordinates: [position.longitude, position.latitude],
      },
      properties: {
        id: position.id,
        mmsi: position.mmsi,
        vesselName: position.vessel_name ?? "Unknown vessel",
        timestamp: position.timestamp,
        sog: position.sog ?? -1,
        cog: position.cog ?? -1,
        heading: position.heading ?? -1,
        navigationStatus: position.navigation_status ?? -1,
      },
    })),
  };
}

function trajectoryToLine(
  trajectory: VesselTrajectory | null,
): FeatureCollection<LineString> {
  if (trajectory === null) {
    return emptyLineCollection();
  }

  const response = trajectory as unknown as BackendTrajectoryResponse;
  let coordinates: [number, number][] = [];

  if (response.geometry?.type === "LineString") {
    coordinates = (response.geometry.coordinates ?? []) as [number, number][];
  } else if (Array.isArray(response.points)) {
    coordinates = response.points.map((point) => [
      point.longitude,
      point.latitude,
    ]);
  }

  coordinates = coordinates.filter(
    ([longitude, latitude]) =>
      Number.isFinite(longitude) && Number.isFinite(latitude),
  );

  if (coordinates.length < 2) {
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
          coordinates,
        },
      },
    ],
  };
}

function anomaliesToGeoJSON(
  anomalies: Anomaly[],
): FeatureCollection<Point, AnomalyProperties> {
  return {
    type: "FeatureCollection",
    features: anomalies
      .filter(
        (anomaly) =>
          Number.isFinite(anomaly.longitude) &&
          Number.isFinite(anomaly.latitude),
      )
      .map((anomaly) => ({
        type: "Feature",
        id: anomaly.id,
        geometry: {
          type: "Point",
          coordinates: [anomaly.longitude, anomaly.latitude],
        },
        properties: {
          id: anomaly.id,
          anomalyType: anomaly.anomaly_type,
          severity: anomaly.severity,
          message: anomaly.message,
          observedAt: anomaly.observed_at,
        },
      })),
  };
}

function risksToGeoJSON(
  assessments: RiskAssessment[],
): FeatureCollection<Point, RiskProperties> {
  return {
    type: "FeatureCollection",
    features: assessments
      .filter(
        (assessment) =>
          Number.isFinite(assessment.longitude) &&
          Number.isFinite(assessment.latitude),
      )
      .map((assessment) => ({
        type: "Feature",
        id: assessment.id,
        geometry: {
          type: "Point",
          coordinates: [assessment.longitude, assessment.latitude],
        },
        properties: {
          id: assessment.id,
          riskLevel: assessment.risk_level,
          mlPercentile: assessment.ml_anomaly_percentile,
          ruleSeverity: assessment.rule_severity,
          ruleFlagCount: assessment.rule_flag_count,
          detectorAgreement: assessment.detector_agreement,
          observedAt: assessment.observed_at,
          reasons: assessment.risk_reasons,
        },
      })),
  };
}

function collisionsToGeoJSON(
  encounters: CollisionEncounter[],
): FeatureCollection<LineString, CollisionProperties> {
  return {
    type: "FeatureCollection",
    features: encounters
      .filter(
        (encounter) =>
          Number.isFinite(encounter.vessel_a.longitude) &&
          Number.isFinite(encounter.vessel_a.latitude) &&
          Number.isFinite(encounter.vessel_b.longitude) &&
          Number.isFinite(encounter.vessel_b.latitude),
      )
      .map((encounter) => ({
        type: "Feature",
        id: encounter.id,
        geometry: {
          type: "LineString",
          coordinates: [
            [encounter.vessel_a.longitude, encounter.vessel_a.latitude],
            [encounter.vessel_b.longitude, encounter.vessel_b.latitude],
          ],
        },
        properties: {
          id: encounter.id,
          riskLevel: encounter.risk_level,
          vesselAMmsi: encounter.vessel_a.mmsi,
          vesselAName: encounter.vessel_a.name ?? "Unknown vessel",
          vesselBMmsi: encounter.vessel_b.mmsi,
          vesselBName: encounter.vessel_b.name ?? "Unknown vessel",
          currentDistanceNm: encounter.current_distance_nm,
          cpaDistanceNm: encounter.cpa_distance_nm,
          tcpaMinutes: encounter.tcpa_minutes,
          relativeSpeedKnots: encounter.relative_speed_knots,
          closingSpeedKnots: encounter.closing_speed_knots,
          observedAt: encounter.observed_at,
        },
      })),
  };
}

function collisionMarkersToGeoJSON(
  encounters: CollisionEncounter[],
): FeatureCollection<Point, CollisionProperties> {
  return {
    type: "FeatureCollection",
    features: encounters
      .filter(
        (encounter) =>
          Number.isFinite(encounter.vessel_a.longitude) &&
          Number.isFinite(encounter.vessel_a.latitude) &&
          Number.isFinite(encounter.vessel_b.longitude) &&
          Number.isFinite(encounter.vessel_b.latitude),
      )
      .map((encounter) => ({
        type: "Feature",
        id: encounter.id,
        geometry: {
          type: "Point",
          coordinates: [
            (encounter.vessel_a.longitude +
              encounter.vessel_b.longitude) /
              2,
            (encounter.vessel_a.latitude +
              encounter.vessel_b.latitude) /
              2,
          ],
        },
        properties: {
          id: encounter.id,
          riskLevel: encounter.risk_level,
          vesselAMmsi: encounter.vessel_a.mmsi,
          vesselAName:
            encounter.vessel_a.name ?? "Unknown vessel",
          vesselBMmsi: encounter.vessel_b.mmsi,
          vesselBName:
            encounter.vessel_b.name ?? "Unknown vessel",
          currentDistanceNm:
            encounter.current_distance_nm,
          cpaDistanceNm:
            encounter.cpa_distance_nm,
          tcpaMinutes:
            encounter.tcpa_minutes,
          relativeSpeedKnots:
            encounter.relative_speed_knots,
          closingSpeedKnots:
            encounter.closing_speed_knots,
          observedAt:
            encounter.observed_at,
        },
      })),
  };
}


function formatMeasurement(value: number, unit: string): string {
  if (!Number.isFinite(value) || value < 0) {
    return "Not available";
  }

  return `${value.toFixed(1)} ${unit}`;
}

function formatSignedMeasurement(value: number, unit: string): string {
  if (!Number.isFinite(value)) {
    return "Not available";
  }

  return `${value.toFixed(1)} ${unit}`;
}

function formatDistance(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return "Not available";
  }

  return `${value.toFixed(3)} NM`;
}

function formatTcpa(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "Not available";
  }

  return `${value.toFixed(1)} min`;
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);

  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleString();
}

function addDetailRow(
  list: HTMLDListElement,
  label: string,
  value: string,
): void {
  const term = document.createElement("dt");
  term.textContent = label;

  const description = document.createElement("dd");
  description.textContent = value;

  list.append(term, description);
}

function featureCoordinates(
  event: MapLayerMouseEvent,
): [number, number] | null {
  const feature = event.features?.[0];

  if (feature === undefined || feature.geometry.type !== "Point") {
    return null;
  }

  return [
    Number(feature.geometry.coordinates[0]),
    Number(feature.geometry.coordinates[1]),
  ];
}

function showVesselPopup(
  map: Map,
  event: MapLayerMouseEvent,
  onSelectVessel: (mmsi: string) => void,
): void {
  const feature = event.features?.[0];
  const coordinates = featureCoordinates(event);

  if (feature === undefined || coordinates === null) {
    return;
  }

  const properties = feature.properties as unknown as VesselProperties;
  const mmsi = String(properties.mmsi);

  onSelectVessel(mmsi);

  const container = document.createElement("div");
  container.className = "vessel-popup";

  const title = document.createElement("strong");
  title.textContent = properties.vesselName || "Unknown vessel";

  const details = document.createElement("dl");

  addDetailRow(details, "MMSI", mmsi);
  addDetailRow(
    details,
    "Speed",
    formatMeasurement(Number(properties.sog), "kn"),
  );
  addDetailRow(
    details,
    "Course",
    formatMeasurement(Number(properties.cog), "°"),
  );
  addDetailRow(
    details,
    "Heading",
    formatMeasurement(Number(properties.heading), "°"),
  );
  addDetailRow(details, "Timestamp", formatTimestamp(properties.timestamp));

  container.append(title, details);

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
  const feature = event.features?.[0];
  const coordinates = featureCoordinates(event);

  if (feature === undefined || coordinates === null) {
    return;
  }

  const properties = feature.properties as unknown as AnomalyProperties;

  const container = document.createElement("div");
  container.className = "anomaly-popup";

  const title = document.createElement("strong");
  title.textContent = properties.anomalyType.replaceAll("_", " ");

  const severity = document.createElement("span");
  severity.textContent = `Severity: ${properties.severity}`;

  const timestamp = document.createElement("span");
  timestamp.textContent = formatTimestamp(properties.observedAt);

  const message = document.createElement("p");
  message.textContent = properties.message;

  container.append(title, severity, timestamp, message);

  new maplibregl.Popup({
    closeButton: true,
    maxWidth: "360px",
  })
    .setLngLat(coordinates)
    .setDOMContent(container)
    .addTo(map);
}

function showRiskPopup(
  map: Map,
  event: MapLayerMouseEvent,
): void {
  const feature = event.features?.[0];
  const coordinates = featureCoordinates(event);

  if (feature === undefined || coordinates === null) {
    return;
  }

  const properties = feature.properties as unknown as RiskProperties;

  const container = document.createElement("div");
  container.className = "risk-popup";

  const title = document.createElement("strong");
  title.textContent =
    `${properties.riskLevel.toUpperCase()} investigation priority`;

  const percentile = document.createElement("span");
  percentile.textContent =
    `ML percentile: ${Number(properties.mlPercentile).toFixed(2)}th`;

  const evidence = document.createElement("span");
  evidence.textContent =
    `Rules: ${properties.ruleFlagCount}` +
    ` · severity ${properties.ruleSeverity}` +
    " · " +
    (properties.detectorAgreement
      ? "detectors agree"
      : "single-source evidence");

  const timestamp = document.createElement("span");
  timestamp.textContent = formatTimestamp(properties.observedAt);

  const reasons = document.createElement("p");
  reasons.textContent = properties.reasons;

  container.append(title, percentile, evidence, timestamp, reasons);

  new maplibregl.Popup({
    closeButton: true,
    maxWidth: "380px",
  })
    .setLngLat(coordinates)
    .setDOMContent(container)
    .addTo(map);
}

function showCollisionPopup(
  map: Map,
  event: MapLayerMouseEvent,
): void {
  const feature = event.features?.[0];

  if (feature === undefined) {
    return;
  }

  const properties = feature.properties as unknown as CollisionProperties;

  const container = document.createElement("div");
  container.className = "risk-popup";

  const title = document.createElement("strong");
  title.textContent =
    `${properties.riskLevel.toUpperCase()} collision encounter`;

  const vessels = document.createElement("span");
  vessels.textContent =
    `${properties.vesselAName} (${properties.vesselAMmsi})` +
    " ↔ " +
    `${properties.vesselBName} (${properties.vesselBMmsi})`;

  const details = document.createElement("dl");

  addDetailRow(
    details,
    "Current separation",
    formatDistance(Number(properties.currentDistanceNm)),
  );
  addDetailRow(
    details,
    "CPA",
    formatDistance(Number(properties.cpaDistanceNm)),
  );
  addDetailRow(
    details,
    "TCPA",
    formatTcpa(
      properties.tcpaMinutes === null
        ? null
        : Number(properties.tcpaMinutes),
    ),
  );
  addDetailRow(
    details,
    "Closing speed",
    formatSignedMeasurement(Number(properties.closingSpeedKnots), "kn"),
  );
  addDetailRow(
    details,
    "Relative speed",
    formatMeasurement(Number(properties.relativeSpeedKnots), "kn"),
  );
  addDetailRow(
    details,
    "Observed",
    formatTimestamp(properties.observedAt),
  );

  const note = document.createElement("p");
  note.textContent =
    "CPA/TCPA assumes constant course and speed. " +
    "This is an encounter-priority indicator, not a collision probability.";

  container.append(title, vessels, details, note);

  new maplibregl.Popup({
    closeButton: true,
    maxWidth: "420px",
  })
    .setLngLat(event.lngLat)
    .setDOMContent(container)
    .addTo(map);
}

export function VesselMap({
  positions,
  selectedMmsi,
  trajectory,
  anomalies,
  riskAssessments,
  collisionEncounters,
  selectedAnomalyId,
  selectedRiskId,
  selectedCollisionId,
  onSelectVessel,
  onSelectAnomaly,
  onSelectRisk,
  onSelectCollision,
}: VesselMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);

  const onSelectVesselRef = useRef(onSelectVessel);
  const onSelectAnomalyRef = useRef(onSelectAnomaly);
  const onSelectRiskRef = useRef(onSelectRisk);
  const onSelectCollisionRef = useRef(onSelectCollision);

  const hasFittedBoundsRef = useRef(false);

  useEffect(() => {
    onSelectVesselRef.current = onSelectVessel;
  }, [onSelectVessel]);

  useEffect(() => {
    onSelectAnomalyRef.current = onSelectAnomaly;
  }, [onSelectAnomaly]);

  useEffect(() => {
    onSelectRiskRef.current = onSelectRisk;
  }, [onSelectRisk]);

  useEffect(() => {
    onSelectCollisionRef.current = onSelectCollision;
  }, [onSelectCollision]);

  useEffect(() => {
    if (containerRef.current === null || mapRef.current !== null) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [23.72, 37.98],
      zoom: 5,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.FullscreenControl(), "top-right");

    map.on("load", () => {
      map.addSource(TRAJECTORY_SOURCE_ID, {
        type: "geojson",
        data: emptyLineCollection(),
      });

      map.addLayer({
        id: TRAJECTORY_LAYER_ID,
        type: "line",
        source: TRAJECTORY_SOURCE_ID,
        paint: {
          "line-color": "#f59e0b",
          "line-width": 4,
          "line-opacity": 0.85,
        },
      });

      map.addSource(COLLISION_SOURCE_ID, {
        type: "geojson",
        data: emptyCollisionCollection(),
      });

      map.addSource(COLLISION_MARKER_SOURCE_ID, {
        type: "geojson",
        data: emptyPointCollection<CollisionProperties>(),
      });

      map.addLayer({
        id: COLLISION_LAYER_ID,
        type: "line",
        source: COLLISION_SOURCE_ID,
        paint: {
          "line-color": [
            "match",
            ["get", "riskLevel"],
            "critical",
            "#dc2626",
            "high",
            "#f97316",
            "medium",
            "#eab308",
            "#64748b",
          ],
          "line-width": [
            "match",
            ["get", "riskLevel"],
            "critical",
            8,
            "high",
            6,
            "medium",
            5,
            4,
          ],
          "line-opacity": 1,
          "line-dasharray": [2, 1],
        },
      });

      map.addLayer({
        id: SELECTED_COLLISION_LAYER_ID,
        type: "line",
        source: COLLISION_SOURCE_ID,
        filter: [
          "==",
          ["get", "id"],
          NO_SELECTED_COLLISION,
        ],
        paint: {
          "line-color": "#22d3ee",
          "line-width": 7,
          "line-opacity": 1,
        },
      });

      map.addLayer({
        id: COLLISION_HITBOX_LAYER_ID,
        type: "line",
        source: COLLISION_SOURCE_ID,
        paint: {
          "line-color": "#000000",
          "line-width": 16,
          "line-opacity": 0,
        },
      });

      map.addSource(VESSEL_SOURCE_ID, {
        type: "geojson",
        data: positionsToGeoJSON([]),
      });

      map.addLayer({
        id: VESSEL_LAYER_ID,
        type: "circle",
        source: VESSEL_SOURCE_ID,
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
        id: SELECTED_VESSEL_LAYER_ID,
        type: "circle",
        source: VESSEL_SOURCE_ID,
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

      map.addSource(RISK_SOURCE_ID, {
        type: "geojson",
        data: emptyPointCollection<RiskProperties>(),
      });

      map.addLayer({
        id: RISK_LAYER_ID,
        type: "circle",
        source: RISK_SOURCE_ID,
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            3,
            7,
            12,
            11,
          ],
          "circle-color": [
            "match",
            ["get", "riskLevel"],
            "critical",
            "#dc2626",
            "high",
            "#f97316",
            "medium",
            "#eab308",
            "#64748b",
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
          "circle-opacity": 0.65,
        },
      });

      map.addLayer({
        id: SELECTED_RISK_LAYER_ID,
        type: "circle",
        source: RISK_SOURCE_ID,
        filter: [
          "==",
          ["get", "id"],
          NO_SELECTED_RISK,
        ],
        paint: {
          "circle-radius": 15,
          "circle-color": "rgba(0, 0, 0, 0)",
          "circle-stroke-color": "#22d3ee",
          "circle-stroke-width": 4,
          "circle-opacity": 1,
        },
      });

      map.addSource(ANOMALY_SOURCE_ID, {
        type: "geojson",
        data: emptyPointCollection<AnomalyProperties>(),
      });

      map.addLayer({
        id: ANOMALY_LAYER_ID,
        type: "circle",
        source: ANOMALY_SOURCE_ID,
        paint: {
          "circle-radius": 6,
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
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
          "circle-opacity": 0.95,
        },
      });

      map.addLayer({
        id: SELECTED_ANOMALY_LAYER_ID,
        type: "circle",
        source: ANOMALY_SOURCE_ID,
        filter: [
          "==",
          ["get", "id"],
          NO_SELECTED_ANOMALY,
        ],
        paint: {
          "circle-radius": 12,
          "circle-color": "rgba(0, 0, 0, 0)",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 4,
          "circle-opacity": 1,
        },
      });

      map.addLayer({
        id: COLLISION_MARKER_LAYER_ID,
        type: "circle",
        source: COLLISION_MARKER_SOURCE_ID,
        paint: {
          "circle-radius": [
            "match",
            ["get", "riskLevel"],
            "critical",
            11,
            "high",
            9,
            "medium",
            8,
            7,
          ],
          "circle-color": [
            "match",
            ["get", "riskLevel"],
            "critical",
            "#dc2626",
            "high",
            "#f97316",
            "medium",
            "#eab308",
            "#64748b",
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 3,
          "circle-opacity": 0.95,
        },
      });

      map.addLayer({
        id: SELECTED_COLLISION_MARKER_LAYER_ID,
        type: "circle",
        source: COLLISION_MARKER_SOURCE_ID,
        filter: [
          "==",
          ["get", "id"],
          NO_SELECTED_COLLISION,
        ],
        paint: {
          "circle-radius": 16,
          "circle-color": "rgba(0, 0, 0, 0)",
          "circle-stroke-color": "#22d3ee",
          "circle-stroke-width": 5,
          "circle-opacity": 1,
        },
      });

      map.addLayer({
        id: COLLISION_MARKER_HITBOX_LAYER_ID,
        type: "circle",
        source: COLLISION_MARKER_SOURCE_ID,
        paint: {
          "circle-radius": 18,
          "circle-color": "#000000",
          "circle-opacity": 0.001,
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
        "click",
        RISK_LAYER_ID,
        (event: MapLayerMouseEvent) => {
          const riskId = Number(
            event.features?.[0]?.properties?.id,
          );

          if (Number.isFinite(riskId)) {
            onSelectRiskRef.current(riskId);
          }

          showRiskPopup(map, event);
        },
      );

      map.on(
        "click",
        ANOMALY_LAYER_ID,
        (event: MapLayerMouseEvent) => {
          const anomalyId = Number(
            event.features?.[0]?.properties?.id,
          );

          if (Number.isFinite(anomalyId)) {
            onSelectAnomalyRef.current(anomalyId);
          }

          showAnomalyPopup(map, event);
        },
      );

      map.on(
        "click",
        COLLISION_HITBOX_LAYER_ID,
        (event: MapLayerMouseEvent) => {
          const collisionId = Number(
            event.features?.[0]?.properties?.id,
          );

          if (Number.isFinite(collisionId)) {
            onSelectCollisionRef.current(collisionId);
          }

          showCollisionPopup(map, event);
        },
      );

      map.on(
        "click",
        COLLISION_MARKER_HITBOX_LAYER_ID,
        (event: MapLayerMouseEvent) => {
          const collisionId = Number(
            event.features?.[0]?.properties?.id,
          );

          if (Number.isFinite(collisionId)) {
            onSelectCollisionRef.current(collisionId);
          }

          showCollisionPopup(map, event);
        },
      );

      for (const layerId of [
        VESSEL_LAYER_ID,
        RISK_LAYER_ID,
        ANOMALY_LAYER_ID,
        COLLISION_HITBOX_LAYER_ID,
        COLLISION_MARKER_HITBOX_LAYER_ID,
      ]) {
        map.on("mouseenter", layerId, () => {
          map.getCanvas().style.cursor = "pointer";
        });

        map.on("mouseleave", layerId, () => {
          map.getCanvas().style.cursor = "";
        });
      }
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

    const update = () => {
      const source = map.getSource(
        VESSEL_SOURCE_ID,
      ) as GeoJSONSource | undefined;

      if (source === undefined) {
        return;
      }

      source.setData(
        positionsToGeoJSON(positions),
      );

      if (
        positions.length === 0 ||
        hasFittedBoundsRef.current
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

      const bounds = new maplibregl.LngLatBounds();

      positions.forEach((position) =>
        bounds.extend([
          position.longitude,
          position.latitude,
        ]),
      );

      map.fitBounds(bounds, {
        padding: 70,
        maxZoom: 11,
        duration: 800,
      });

      hasFittedBoundsRef.current = true;
    };

    if (
      map.isStyleLoaded() &&
      map.getSource(VESSEL_SOURCE_ID)
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [positions]);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const update = () => {
      if (
        map.getLayer(
          SELECTED_VESSEL_LAYER_ID,
        ) === undefined
      ) {
        return;
      }

      map.setFilter(
        SELECTED_VESSEL_LAYER_ID,
        [
          "==",
          ["get", "mmsi"],
          selectedMmsi ??
            NO_SELECTED_VESSEL,
        ],
      );

      if (selectedMmsi === null) {
        return;
      }

      const position = positions.find(
        (item) =>
          item.mmsi === selectedMmsi,
      );

      if (position === undefined) {
        return;
      }

      map.easeTo({
        center: [
          position.longitude,
          position.latitude,
        ],
        zoom: Math.max(
          map.getZoom(),
          9,
        ),
        duration: 700,
      });
    };

    if (
      map.isStyleLoaded() &&
      map.getLayer(
        SELECTED_VESSEL_LAYER_ID,
      )
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [
    positions,
    selectedMmsi,
  ]);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const update = () => {
      const source = map.getSource(
        TRAJECTORY_SOURCE_ID,
      ) as GeoJSONSource | undefined;

      if (source === undefined) {
        return;
      }

      const line =
        trajectoryToLine(trajectory);

      source.setData(line);

      const coordinates =
        line.features[0]
          ?.geometry
          .coordinates;

      if (
        coordinates === undefined ||
        coordinates.length < 2
      ) {
        return;
      }

      const bounds =
        new maplibregl.LngLatBounds();

      coordinates.forEach(
        (coordinate) =>
          bounds.extend([
            coordinate[0],
            coordinate[1],
          ]),
      );

      map.fitBounds(bounds, {
        padding: 90,
        maxZoom: 12,
        duration: 700,
      });
    };

    if (
      map.isStyleLoaded() &&
      map.getSource(
        TRAJECTORY_SOURCE_ID,
      )
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [trajectory]);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const update = () => {
      const lineSource = map.getSource(
        COLLISION_SOURCE_ID,
      ) as GeoJSONSource | undefined;

      const markerSource = map.getSource(
        COLLISION_MARKER_SOURCE_ID,
      ) as GeoJSONSource | undefined;

      lineSource?.setData(
        collisionsToGeoJSON(
          collisionEncounters,
        ),
      );

      markerSource?.setData(
        collisionMarkersToGeoJSON(
          collisionEncounters,
        ),
      );
    };

    if (
      map.isStyleLoaded() &&
      map.getSource(
        COLLISION_SOURCE_ID,
      ) &&
      map.getSource(
        COLLISION_MARKER_SOURCE_ID,
      )
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [collisionEncounters]);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const update = () => {
      if (
        map.getLayer(
          SELECTED_COLLISION_LAYER_ID,
        ) === undefined ||
        map.getLayer(
          SELECTED_COLLISION_MARKER_LAYER_ID,
        ) === undefined
      ) {
        return;
      }

      map.setFilter(
        SELECTED_COLLISION_LAYER_ID,
        [
          "==",
          ["get", "id"],
          selectedCollisionId ??
            NO_SELECTED_COLLISION,
        ],
      );

      map.setFilter(
        SELECTED_COLLISION_MARKER_LAYER_ID,
        [
          "==",
          ["get", "id"],
          selectedCollisionId ??
            NO_SELECTED_COLLISION,
        ],
      );

      if (
        selectedCollisionId === null
      ) {
        return;
      }

      const encounter =
        collisionEncounters.find(
          (item) =>
            item.id ===
            selectedCollisionId,
        );

      if (encounter === undefined) {
        return;
      }

      const vesselA: [number, number] = [
        encounter.vessel_a.longitude,
        encounter.vessel_a.latitude,
      ];

      const vesselB: [number, number] = [
        encounter.vessel_b.longitude,
        encounter.vessel_b.latitude,
      ];

      if (
        vesselA[0] === vesselB[0] &&
        vesselA[1] === vesselB[1]
      ) {
        map.flyTo({
          center: vesselA,
          zoom: Math.max(
            map.getZoom(),
            13,
          ),
          duration: 700,
        });

        return;
      }

      const bounds =
        new maplibregl.LngLatBounds();

      bounds.extend(vesselA);
      bounds.extend(vesselB);

      map.fitBounds(bounds, {
        padding: 120,
        maxZoom: 13,
        duration: 800,
      });
    };

    if (
      map.isStyleLoaded() &&
      map.getLayer(
        SELECTED_COLLISION_LAYER_ID,
      )
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [
    collisionEncounters,
    selectedCollisionId,
  ]);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const update = () => {
      const source = map.getSource(
        RISK_SOURCE_ID,
      ) as GeoJSONSource | undefined;

      source?.setData(
        risksToGeoJSON(
          riskAssessments,
        ),
      );
    };

    if (
      map.isStyleLoaded() &&
      map.getSource(RISK_SOURCE_ID)
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [riskAssessments]);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const update = () => {
      if (
        map.getLayer(
          SELECTED_RISK_LAYER_ID,
        ) === undefined
      ) {
        return;
      }

      map.setFilter(
        SELECTED_RISK_LAYER_ID,
        [
          "==",
          ["get", "id"],
          selectedRiskId ??
            NO_SELECTED_RISK,
        ],
      );

      if (selectedRiskId === null) {
        return;
      }

      const assessment =
        riskAssessments.find(
          (item) =>
            item.id ===
            selectedRiskId,
        );

      if (assessment === undefined) {
        return;
      }

      map.flyTo({
        center: [
          assessment.longitude,
          assessment.latitude,
        ],
        zoom: Math.max(
          map.getZoom(),
          13,
        ),
        duration: 700,
      });
    };

    if (
      map.isStyleLoaded() &&
      map.getLayer(
        SELECTED_RISK_LAYER_ID,
      )
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [
    riskAssessments,
    selectedRiskId,
  ]);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const update = () => {
      const source = map.getSource(
        ANOMALY_SOURCE_ID,
      ) as GeoJSONSource | undefined;

      source?.setData(
        anomaliesToGeoJSON(
          anomalies,
        ),
      );
    };

    if (
      map.isStyleLoaded() &&
      map.getSource(
        ANOMALY_SOURCE_ID,
      )
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [anomalies]);

  useEffect(() => {
    const map = mapRef.current;

    if (map === null) {
      return;
    }

    const update = () => {
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
          selectedAnomalyId ??
            NO_SELECTED_ANOMALY,
        ],
      );

      if (
        selectedAnomalyId === null
      ) {
        return;
      }

      const anomaly =
        anomalies.find(
          (item) =>
            item.id ===
            selectedAnomalyId,
        );

      if (anomaly === undefined) {
        return;
      }

      map.flyTo({
        center: [
          anomaly.longitude,
          anomaly.latitude,
        ],
        zoom: Math.max(
          map.getZoom(),
          13,
        ),
        duration: 700,
      });
    };

    if (
      map.isStyleLoaded() &&
      map.getLayer(
        SELECTED_ANOMALY_LAYER_ID,
      )
    ) {
      update();
    } else {
      map.once("load", update);
    }
  }, [
    anomalies,
    selectedAnomalyId,
  ]);

  return (
    <div
      ref={containerRef}
      className="vessel-map"
      aria-label="Map of recent vessel positions and collision encounters"
    />
  );
}