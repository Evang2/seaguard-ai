import type {
  FeatureCollection,
  Geometry,
  GeoJsonProperties,
} from "geojson";


export interface RecentPosition {
  id: number;
  mmsi: string;
  vessel_name: string | null;
  vessel_type: number | null;
  timestamp: string;
  latitude: number;
  longitude: number;
  sog: number | null;
  cog: number | null;
  heading: number | null;
  navigation_status: number | null;
}


export interface RecentPositionsResponse {
  items: RecentPosition[];
  total: number;
}


export type VesselTrajectory =
  FeatureCollection<
    Geometry,
    GeoJsonProperties
  >;


export interface Anomaly {
  id: number;
  mmsi: string;
  observed_at: string;
  latitude: number;
  longitude: number;
  anomaly_type: string;
  severity: string;
  metric_name: string;
  metric_value: number | null;
  threshold: number | null;
  message: string;
}


export interface AnomalyListResponse {
  items: Anomaly[];
  total: number;
  limit: number;
  offset: number;
}


export type RiskLevel =
  | "low"
  | "medium"
  | "high"
  | "critical";


export type RuleSeverity =
  | "none"
  | "warning"
  | "high"
  | "critical";


export interface RiskAssessment {
  id: number;
  ais_message_id: number;
  mmsi: string;
  observed_at: string;
  latitude: number;
  longitude: number;
  ml_anomaly_score: number;
  ml_anomaly_percentile: number;
  rule_flag_count: number;
  rule_severity: RuleSeverity;
  detector_agreement: boolean;
  risk_level: RiskLevel;
  risk_reasons: string;
  assessment_version: string;
}


export interface RiskAssessmentListResponse {
  items: RiskAssessment[];
  total: number;
  limit: number;
  offset: number;
}

export interface RiskSummaryResponse {
  total: number;
  low: number;
  medium: number;
  high: number;
  critical: number;
  elevated: number;
  detector_agreement: number;
}

export type CollisionRiskLevel =
  | "low"
  | "medium"
  | "high"
  | "critical";

export interface CollisionVesselState {
  vessel_id: number;
  ais_message_id: number;

  mmsi: string;
  name: string | null;

  observed_at: string;

  latitude: number;
  longitude: number;

  sog: number | null;
  cog: number | null;
}

export interface CollisionEncounter {
  id: number;
  observed_at: string;

  vessel_a: CollisionVesselState;
  vessel_b: CollisionVesselState;

  current_distance_nm: number;
  cpa_distance_nm: number;
  tcpa_minutes: number | null;

  relative_speed_knots: number;
  closing_speed_knots: number;

  bearing_from_a_to_b_degrees: number;

  risk_level: CollisionRiskLevel;

  reasons: string[];

  assessment_version: string;
  created_at: string;
}

export interface CollisionEncounterListResponse {
  items: CollisionEncounter[];

  total: number;
  limit: number;
  offset: number;
}

export interface CollisionSummaryResponse {
  total: number;

  low: number;
  medium: number;
  high: number;
  critical: number;
}