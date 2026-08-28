import type { RecentPosition } from "./types";

const API_BASE_URL = "http://127.0.0.1:8000";

export interface PlaybackBounds {
  start_time: string | null;
  end_time: string | null;
  observation_count: number;
  vessel_count: number;
}

export interface PlaybackSnapshot {
  requested_at: string;
  window_start: string;
  tolerance_minutes: number;
  total: number;
  items: RecentPosition[];
}

async function requestJson<T>(
  url: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(url, {
    signal,
  });

  if (!response.ok) {
    const text = await response.text();

    throw new Error(
      text ||
        `Playback request failed with HTTP ${response.status}.`,
    );
  }

  return (await response.json()) as T;
}

export function fetchPlaybackBounds(
  signal?: AbortSignal,
): Promise<PlaybackBounds> {
  return requestJson<PlaybackBounds>(
    `${API_BASE_URL}/api/v1/playback/bounds`,
    signal,
  );
}

export function fetchPlaybackSnapshot(
  at: string,
  toleranceMinutes = 5,
  limit = 500,
  signal?: AbortSignal,
): Promise<PlaybackSnapshot> {
  const params = new URLSearchParams({
    at,
    tolerance_minutes: String(toleranceMinutes),
    limit: String(limit),
  });

  return requestJson<PlaybackSnapshot>(
    `${API_BASE_URL}/api/v1/playback/snapshot?${params.toString()}`,
    signal,
  );
}