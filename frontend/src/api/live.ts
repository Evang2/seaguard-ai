const API_BASE_URL =
  "http://127.0.0.1:8000";

export interface LiveImportStatus {
  job_id: number;
  source_file: string;
  status: string;

  rows_read: number;
  rows_imported: number;
  rows_rejected: number;
  duplicates_skipped: number;

  started_at: string;
  finished_at: string | null;
}

export interface LiveStatus {
  server_time: string;
  latest_ais_timestamp:
    | string
    | null;

  vessel_count: number;
  message_count: number;

  ingestion_active: boolean;

  latest_import:
    | LiveImportStatus
    | null;
}

export async function fetchLiveStatus(
  signal?: AbortSignal,
): Promise<LiveStatus> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/live/status`,
    {
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(
      `Live status request failed: ${response.status}`,
    );
  }

  return response.json() as Promise<LiveStatus>;
}