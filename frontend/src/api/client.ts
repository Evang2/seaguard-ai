import type {
  AnomalyListResponse,
  RecentPositionsResponse,
  RiskAssessmentListResponse,
  RiskLevel,
  RiskSummaryResponse,
  VesselTrajectory,
} from "./types";

const DEFAULT_API_BASE_URL =
  "http://127.0.0.1:8000";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL
  ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");

export interface RecentPositionQuery {
  activeOnly?: boolean;
  activeWindowMinutes?: number;
  maximumAgeMinutes?: number;
}

export interface CurrentWindowQuery {
  currentOnly?: boolean;
  activeWindowMinutes?: number;
}

export type CurrentRiskQuery =
  CurrentWindowQuery;

async function requestJson<T>(
  url: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(
    url,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(
      `API request failed with status `
      + `${response.status}.`,
    );
  }

  return response.json() as Promise<T>;
}

export function fetchRecentPositions(
  limit = 500,
  signal?: AbortSignal,
  query: RecentPositionQuery = {},
): Promise<RecentPositionsResponse> {
  const url = new URL(
    `${API_BASE_URL}/api/v1/positions/recent`,
  );

  url.searchParams.set(
    "limit",
    String(limit),
  );

  if (query.activeOnly !== undefined) {
    url.searchParams.set(
      "active_only",
      String(query.activeOnly),
    );
  }

  if (
    query.activeWindowMinutes
    !== undefined
  ) {
    url.searchParams.set(
      "active_window_minutes",
      String(
        query.activeWindowMinutes,
      ),
    );
  }

  if (
    query.maximumAgeMinutes
    !== undefined
  ) {
    url.searchParams.set(
      "maximum_age_minutes",
      String(
        query.maximumAgeMinutes,
      ),
    );
  }

  return requestJson<RecentPositionsResponse>(
    url.toString(),
    signal,
  );
}

export function fetchVesselTrajectory(
  mmsi: string,
  signal?: AbortSignal,
): Promise<VesselTrajectory> {
  const encodedMmsi =
    encodeURIComponent(mmsi);

  return requestJson<VesselTrajectory>(
    `${API_BASE_URL}/api/v1/vessels/`
      + `${encodedMmsi}/trajectory`,
    signal,
  );
}

export function fetchVesselAnomalies(
  mmsi: string,
  signal?: AbortSignal,
  query: CurrentWindowQuery = {},
): Promise<AnomalyListResponse> {
  const url = new URL(
    `${API_BASE_URL}/api/v1/anomalies`,
  );

  url.searchParams.set("mmsi", mmsi);
  url.searchParams.set("limit", "500");

  if (query.currentOnly !== undefined) {
    url.searchParams.set(
      "current_only",
      String(query.currentOnly),
    );
  }

  if (
    query.activeWindowMinutes
    !== undefined
  ) {
    url.searchParams.set(
      "active_window_minutes",
      String(
        query.activeWindowMinutes,
      ),
    );
  }

  return requestJson<AnomalyListResponse>(
    url.toString(),
    signal,
  );
}

export function fetchVesselRiskAssessments(
  mmsi: string,
  signal?: AbortSignal,
  query: CurrentRiskQuery = {},
): Promise<RiskAssessmentListResponse> {
  const encodedMmsi =
    encodeURIComponent(mmsi);

  const url = new URL(
    `${API_BASE_URL}/api/v1/risk/${encodedMmsi}`,
  );

  url.searchParams.set("limit", "500");

  if (query.currentOnly !== undefined) {
    url.searchParams.set(
      "current_only",
      String(query.currentOnly),
    );
  }

  if (
    query.activeWindowMinutes
    !== undefined
  ) {
    url.searchParams.set(
      "active_window_minutes",
      String(
        query.activeWindowMinutes,
      ),
    );
  }

  return requestJson<RiskAssessmentListResponse>(
    url.toString(),
    signal,
  );
}

export function fetchRiskSummary(
  signal?: AbortSignal,
  query: CurrentRiskQuery = {},
): Promise<RiskSummaryResponse> {
  const url = new URL(
    `${API_BASE_URL}/api/v1/risk/summary`,
  );

  if (query.currentOnly !== undefined) {
    url.searchParams.set(
      "current_only",
      String(query.currentOnly),
    );
  }

  if (
    query.activeWindowMinutes
    !== undefined
  ) {
    url.searchParams.set(
      "active_window_minutes",
      String(
        query.activeWindowMinutes,
      ),
    );
  }

  return requestJson<RiskSummaryResponse>(
    url.toString(),
    signal,
  );
}

export interface GlobalRiskQueueFilters
  extends CurrentRiskQuery {
  mmsi?: string;
  riskLevel?: RiskLevel;
  minimumMlPercentile?: number;
  detectorAgreement?: boolean;
  limit?: number;
  offset?: number;
}

export function fetchGlobalRiskQueue(
  filters: GlobalRiskQueueFilters = {},
  signal?: AbortSignal,
): Promise<RiskAssessmentListResponse> {
  const url = new URL(
    `${API_BASE_URL}/api/v1/risk`,
  );

  if (filters.mmsi) {
    url.searchParams.set(
      "mmsi",
      filters.mmsi,
    );
  }

  if (filters.riskLevel) {
    url.searchParams.set(
      "risk_level",
      filters.riskLevel,
    );
  }

  if (
    filters.minimumMlPercentile
    !== undefined
  ) {
    url.searchParams.set(
      "minimum_ml_percentile",
      String(
        filters.minimumMlPercentile,
      ),
    );
  }

  if (
    filters.detectorAgreement
    !== undefined
  ) {
    url.searchParams.set(
      "detector_agreement",
      String(
        filters.detectorAgreement,
      ),
    );
  }

  if (
    filters.currentOnly
    !== undefined
  ) {
    url.searchParams.set(
      "current_only",
      String(
        filters.currentOnly,
      ),
    );
  }

  if (
    filters.activeWindowMinutes
    !== undefined
  ) {
    url.searchParams.set(
      "active_window_minutes",
      String(
        filters.activeWindowMinutes,
      ),
    );
  }

  url.searchParams.set(
    "limit",
    String(filters.limit ?? 100),
  );

  url.searchParams.set(
    "offset",
    String(filters.offset ?? 0),
  );

  return requestJson<RiskAssessmentListResponse>(
    url.toString(),
    signal,
  );
}