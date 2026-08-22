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