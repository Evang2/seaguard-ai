import type {
  RecentPositionsResponse,
} from "./types";

const DEFAULT_API_BASE_URL =
  "http://127.0.0.1:8000";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL
  ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");


export async function fetchRecentPositions(
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
      `Position request failed with status `
      + `${response.status}.`,
    );
  }

  const data: RecentPositionsResponse = await response.json();
  return data;
}