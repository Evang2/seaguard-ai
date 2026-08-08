import type {
  AnomalyListResponse,
  RecentPositionsResponse,
  VesselTrajectory,
} from "./types";


const DEFAULT_API_BASE_URL =
  "http://127.0.0.1:8000";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL
  ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");


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
): Promise<RecentPositionsResponse> {
  const url = new URL(
    `${API_BASE_URL}/api/v1/positions/recent`,
  );

  url.searchParams.set(
    "limit",
    String(limit),
  );

  return requestJson<
    RecentPositionsResponse
  >(
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
): Promise<AnomalyListResponse> {
  const url = new URL(
    `${API_BASE_URL}/api/v1/anomalies`,
  );

  url.searchParams.set("mmsi", mmsi);
  url.searchParams.set("limit", "500");

  return requestJson<AnomalyListResponse>(
    url.toString(),
    signal,
  );
}