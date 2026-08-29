import type {
  CollisionEncounterListResponse,
  CollisionRiskLevel,
  CollisionSummaryResponse,
} from "./types";

const API_BASE_URL =
  "http://127.0.0.1:8000";


export interface CollisionEncounterQuery {
  riskLevel?: CollisionRiskLevel;
  minimumTcpaMinutes?: number;
  maximumTcpaMinutes?: number;
  limit?: number;
  offset?: number;
  currentOnly?: boolean;
}


async function requestJson<T>(
  url: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(
    url,
    {
      signal,
    },
  );

  if (!response.ok) {
    let detail =
      `${response.status} ${response.statusText}`;

    try {
      const body =
        (await response.json()) as {
          detail?: unknown;
        };

      if (
        typeof body.detail ===
        "string"
      ) {
        detail = body.detail;
      }
    } catch {
      // Keep the HTTP status text when
      // the response body is not JSON.
    }

    throw new Error(
      `Collision API request failed: ${detail}`,
    );
  }

  return (await response.json()) as T;
}


function buildCollisionSearchParams(
  query: CollisionEncounterQuery,
): URLSearchParams {
  const params =
    new URLSearchParams();

  if (
    query.riskLevel !==
    undefined
  ) {
    params.set(
      "risk_level",
      query.riskLevel,
    );
  }

  if (
    query.minimumTcpaMinutes !==
    undefined
  ) {
    params.set(
      "minimum_tcpa_minutes",
      String(
        query.minimumTcpaMinutes,
      ),
    );
  }

  if (
    query.maximumTcpaMinutes !==
    undefined
  ) {
    params.set(
      "maximum_tcpa_minutes",
      String(
        query.maximumTcpaMinutes,
      ),
    );
  }

  if (
    query.limit !==
    undefined
  ) {
    params.set(
      "limit",
      String(
        query.limit,
      ),
    );
  }

  if (
    query.offset !==
    undefined
  ) {
    params.set(
      "offset",
      String(
        query.offset,
      ),
    );
  }

  if (
    query.currentOnly !==
    undefined
  ) {
    params.set(
      "current_only",
      String(
        query.currentOnly,
      ),
    );
  }

  return params;
}


export async function fetchCollisionEncounters(
  query: CollisionEncounterQuery = {},
  signal?: AbortSignal,
): Promise<CollisionEncounterListResponse> {
  const params =
    buildCollisionSearchParams(
      query,
    );

  const queryString =
    params.toString();

  const url =
    `${API_BASE_URL}/api/v1/collisions${
      queryString
        ? `?${queryString}`
        : ""
    }`;

  return requestJson<
    CollisionEncounterListResponse
  >(
    url,
    signal,
  );
}


export async function fetchVesselCollisionEncounters(
  mmsi: string,
  signal?: AbortSignal,
  options: {
    currentOnly?: boolean;
    limit?: number;
    offset?: number;
  } = {},
): Promise<CollisionEncounterListResponse> {
  const params =
    new URLSearchParams();

  if (
    options.currentOnly !==
    undefined
  ) {
    params.set(
      "current_only",
      String(
        options.currentOnly,
      ),
    );
  }

  if (
    options.limit !==
    undefined
  ) {
    params.set(
      "limit",
      String(
        options.limit,
      ),
    );
  }

  if (
    options.offset !==
    undefined
  ) {
    params.set(
      "offset",
      String(
        options.offset,
      ),
    );
  }

  const queryString =
    params.toString();

  const url =
    `${API_BASE_URL}/api/v1/collisions/${encodeURIComponent(
      mmsi,
    )}${
      queryString
        ? `?${queryString}`
        : ""
    }`;

  return requestJson<
    CollisionEncounterListResponse
  >(
    url,
    signal,
  );
}


export async function fetchCollisionSummary(
  options: {
    currentOnly?: boolean;
  } = {},
  signal?: AbortSignal,
): Promise<CollisionSummaryResponse> {
  const params =
    new URLSearchParams();

  if (
    options.currentOnly !==
    undefined
  ) {
    params.set(
      "current_only",
      String(
        options.currentOnly,
      ),
    );
  }

  const queryString =
    params.toString();

  const url =
    `${API_BASE_URL}/api/v1/collisions/summary${
      queryString
        ? `?${queryString}`
        : ""
    }`;

  return requestJson<
    CollisionSummaryResponse
  >(
    url,
    signal,
  );
}
