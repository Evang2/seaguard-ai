import type {
  CollisionEncounterListResponse,
  CollisionRiskLevel,
  CollisionSummaryResponse,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000";

export interface CollisionQueueFilters {
  riskLevel?: CollisionRiskLevel;

  minimumTcpaMinutes?: number;
  maximumTcpaMinutes?: number;

  limit?: number;
  offset?: number;
}

async function parseResponse<T>(
  response: Response,
): Promise<T> {
  if (!response.ok) {
    let detail = "";

    try {
      const payload = await response.json();

      if (
        typeof payload === "object" &&
        payload !== null &&
        "detail" in payload
      ) {
        detail = String(payload.detail);
      }
    } catch {
      // Ignore JSON parsing errors and use HTTP status below.
    }

    throw new Error(
      detail ||
        `SeaGuard API request failed with HTTP ${response.status}.`,
    );
  }

  return (await response.json()) as T;
}

export async function fetchCollisionSummary(
  signal?: AbortSignal,
): Promise<CollisionSummaryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/collisions/summary`,
    {
      signal,
    },
  );

  return parseResponse<CollisionSummaryResponse>(
    response,
  );
}

export async function fetchCollisionEncounters(
  filters: CollisionQueueFilters = {},
  signal?: AbortSignal,
): Promise<CollisionEncounterListResponse> {
  const params = new URLSearchParams();

  if (filters.riskLevel !== undefined) {
    params.set(
      "risk_level",
      filters.riskLevel,
    );
  }

  if (
    filters.minimumTcpaMinutes !== undefined
  ) {
    params.set(
      "minimum_tcpa_minutes",
      String(filters.minimumTcpaMinutes),
    );
  }

  if (
    filters.maximumTcpaMinutes !== undefined
  ) {
    params.set(
      "maximum_tcpa_minutes",
      String(filters.maximumTcpaMinutes),
    );
  }

  if (filters.limit !== undefined) {
    params.set(
      "limit",
      String(filters.limit),
    );
  }

  if (filters.offset !== undefined) {
    params.set(
      "offset",
      String(filters.offset),
    );
  }

  const query = params.toString();

  const url = query
    ? `${API_BASE_URL}/api/v1/collisions?${query}`
    : `${API_BASE_URL}/api/v1/collisions`;

  const response = await fetch(
    url,
    {
      signal,
    },
  );

  return parseResponse<CollisionEncounterListResponse>(
    response,
  );
}

export async function fetchVesselCollisionEncounters(
  mmsi: string,
  signal?: AbortSignal,
): Promise<CollisionEncounterListResponse> {
  const params = new URLSearchParams({
    limit: "500",
  });

  const response = await fetch(
    `${API_BASE_URL}/api/v1/collisions/${encodeURIComponent(
      mmsi,
    )}?${params.toString()}`,
    {
      signal,
    },
  );

  return parseResponse<CollisionEncounterListResponse>(
    response,
  );
}