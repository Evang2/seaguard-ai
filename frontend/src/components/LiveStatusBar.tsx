import {
  useEffect,
  useState,
} from "react";

import {
  fetchLiveStatus,
} from "../api/live";

import type {
  LiveStatus,
} from "../api/live";

import "./live-status.css";


const LIVE_STATUS_POLL_MS =
  5_000;


interface LiveStatusBarProps {
  historical: boolean;
}


function formatTimestamp(
  timestamp: string | null,
): string {
  if (timestamp === null) {
    return "No AIS data";
  }

  const value =
    new Date(timestamp);

  if (
    Number.isNaN(
      value.getTime(),
    )
  ) {
    return timestamp;
  }

  return value.toLocaleString();
}


function fileName(
  path: string,
): string {
  const normalized =
    path.replaceAll("\\", "/");

  return (
    normalized
      .split("/")
      .at(-1)
    ?? path
  );
}


export function LiveStatusBar({
  historical,
}: LiveStatusBarProps) {
  const [
    status,
    setStatus,
  ] =
    useState<LiveStatus | null>(
      null,
    );

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null,
    );

  const [
    lastUpdated,
    setLastUpdated,
  ] =
    useState<Date | null>(
      null,
    );

  useEffect(() => {
    if (historical) {
      return;
    }

    let stopped = false;

    let controller:
      | AbortController
      | null = null;

    let requestInFlight =
      false;

    const loadStatus =
      async () => {
        if (
          requestInFlight
        ) {
          return;
        }

        requestInFlight =
          true;

        controller =
          new AbortController();

        try {
          const response =
            await fetchLiveStatus(
              controller.signal,
            );

          if (stopped) {
            return;
          }

          setStatus(
            response,
          );

          setError(
            null,
          );

          setLastUpdated(
            new Date(),
          );
        } catch (
          caughtError
        ) {
          if (
            stopped ||
            controller.signal
              .aborted
          ) {
            return;
          }

          console.error(
            "Failed to load live status:",
            caughtError,
          );

          setError(
            caughtError instanceof
              Error
              ? caughtError.message
              : "Live status unavailable.",
          );
        } finally {
          requestInFlight =
            false;
        }
      };

    void loadStatus();

    const interval =
      window.setInterval(
        () => {
          void loadStatus();
        },
        LIVE_STATUS_POLL_MS,
      );

    return () => {
      stopped = true;

      window.clearInterval(
        interval,
      );

      controller?.abort();
    };
  }, [
    historical,
  ]);

  if (historical) {
    return (
      <section
        className="live-status-bar historical"
        aria-label="Dashboard mode"
      >
        <div className="live-state">
          <span
            className="live-dot"
            aria-hidden="true"
          />

          <strong>
            HISTORICAL
          </strong>

          <span>
            Live polling paused during
            AIS playback
          </span>
        </div>
      </section>
    );
  }

  const stateClass =
    error !== null
      ? "offline"
      : status?.ingestion_active
        ? "ingesting"
        : "live";

  const stateLabel =
    error !== null
      ? "OFFLINE"
      : status?.ingestion_active
        ? "INGESTING"
        : "LIVE";

  return (
    <section
      className={`live-status-bar ${stateClass}`}
      aria-label="Live AIS status"
    >
      <div className="live-state">
        <span
          className="live-dot"
          aria-hidden="true"
        />

        <strong>
          {stateLabel}
        </strong>

        {error !== null ? (
          <span>
            {error}
          </span>
        ) : (
          <span>
            Automatic refresh every
            {" "}
            {LIVE_STATUS_POLL_MS /
              1_000}
            s
          </span>
        )}
      </div>

      {status !== null && (
        <div className="live-metrics">
          <div>
            <span>
              Latest AIS
            </span>

            <strong>
              {formatTimestamp(
                status
                  .latest_ais_timestamp,
              )}
            </strong>
          </div>

          <div>
            <span>
              Stored vessels
            </span>

            <strong>
              {
                status.vessel_count
              }
            </strong>
          </div>

          <div>
            <span>
              AIS messages
            </span>

            <strong>
              {
                status.message_count
              }
            </strong>
          </div>

          <div>
            <span>
              Last refresh
            </span>

            <strong>
              {lastUpdated === null
                ? "—"
                : lastUpdated
                    .toLocaleTimeString()}
            </strong>
          </div>

          <div>
            <span>
              Ingestion
            </span>

            <strong>
              {status
                .ingestion_active
                ? "Running"
                : "Idle"}
            </strong>
          </div>
        </div>
      )}

      {status?.latest_import !==
        null &&
        status?.latest_import !==
          undefined && (
          <div className="live-import">
            <span>
              Latest import:
            </span>

            <strong>
              {fileName(
                status
                  .latest_import
                  .source_file,
              )}
            </strong>

            <span>
              {
                status
                  .latest_import
                  .status
              }
            </span>

            <span>
              {
                status
                  .latest_import
                  .rows_imported
              }{" "}
              imported
            </span>

            {status
              .latest_import
              .rows_rejected >
              0 && (
              <span>
                {
                  status
                    .latest_import
                    .rows_rejected
                }{" "}
                rejected
              </span>
            )}
          </div>
        )}
    </section>
  );
}