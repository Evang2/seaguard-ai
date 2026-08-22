import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  fetchGlobalRiskQueue,
  fetchRiskSummary,
} from "../api/client";

import type {
  RiskAssessment,
  RiskSummaryResponse,
} from "../api/types";


interface RiskOverviewProps {
  onSelectRisk: (
    assessment: RiskAssessment,
  ) => void;
}


function formatTimestamp(
  timestamp: string,
): string {
  const date =
    new Date(timestamp);

  return Number.isNaN(
    date.getTime(),
  )
    ? timestamp
    : date.toLocaleString();
}


function formatPercentile(
  percentile: number,
): string {
  return `${percentile.toFixed(2)}th`;
}


export function RiskOverview({
  onSelectRisk,
}: RiskOverviewProps) {
  const [
    summary,
    setSummary,
  ] = useState<RiskSummaryResponse | null>(
    null,
  );

  const [
    queue,
    setQueue,
  ] = useState<RiskAssessment[]>([]);

  const [
    isLoading,
    setIsLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );


  const loadOverview =
    useCallback(
      async (
        signal?: AbortSignal,
      ) => {
        setIsLoading(true);
        setError(null);

        try {
          const [
            summaryResponse,
            queueResponse,
          ] = await Promise.all([
            fetchRiskSummary(
              signal,
            ),

            fetchGlobalRiskQueue(
              100,
              signal,
            ),
          ]);

          setSummary(
            summaryResponse,
          );

          setQueue(
            queueResponse.items,
          );
        } catch (caughtError) {
          if (
            caughtError
              instanceof DOMException
            && caughtError.name
              === "AbortError"
          ) {
            return;
          }

          console.error(
            "Failed to load risk overview:",
            caughtError,
          );

          setError(
            caughtError instanceof Error
              ? caughtError.message
              : "Could not load risk overview.",
          );
        } finally {
          if (
            signal?.aborted
            !== true
          ) {
            setIsLoading(
              false,
            );
          }
        }
      },
      [],
    );


  useEffect(() => {
    const controller =
      new AbortController();

    void loadOverview(
      controller.signal,
    );

    return () => {
      controller.abort();
    };
  }, [loadOverview]);


  return (
    <section className="risk-overview">
      <div className="risk-overview-heading">
        <div>
          <p className="eyebrow">
            Hybrid detection
          </p>

          <h2>
            Investigation overview
          </h2>

          <p>
            Highest-priority persisted AIS observations
            across all vessels.
          </p>
        </div>

        <button
          type="button"
          className="risk-overview-refresh"
          disabled={isLoading}
          onClick={() => {
            void loadOverview();
          }}
        >
          {isLoading
            ? "Loading…"
            : "Refresh risk"}
        </button>
      </div>


      {error !== null && (
        <div
          className="risk-overview-error"
          role="alert"
        >
          {error}
        </div>
      )}


      {summary !== null && (
        <div className="risk-overview-cards">
          <article className="risk-overview-card">
            <span>
              Critical
            </span>

            <strong className="risk-number-critical">
              {summary.critical}
            </strong>

            <small>
              Immediate investigation priority
            </small>
          </article>


          <article className="risk-overview-card">
            <span>
              High
            </span>

            <strong className="risk-number-high">
              {summary.high}
            </strong>

            <small>
              Strong rule or ML evidence
            </small>
          </article>


          <article className="risk-overview-card">
            <span>
              Elevated
            </span>

            <strong>
              {summary.elevated}
            </strong>

            <small>
              Medium + high + critical
            </small>
          </article>


          <article className="risk-overview-card">
            <span>
              Detector agreement
            </span>

            <strong>
              {summary.detector_agreement}
            </strong>

            <small>
              Rules and ML both detected evidence
            </small>
          </article>
        </div>
      )}


      <div className="global-risk-queue-heading">
        <div>
          <h3>
            Investigation queue
          </h3>

          <span>
            Top {queue.length} observations
          </span>
        </div>

        {summary !== null && (
          <span className="risk-total-label">
            {summary.total.toLocaleString()} total assessments
          </span>
        )}
      </div>


      {isLoading && queue.length === 0 ? (
        <div className="global-risk-empty">
          Loading investigation queue…
        </div>
      ) : queue.length === 0 ? (
        <div className="global-risk-empty">
          No persisted risk assessments found.
        </div>
      ) : (
        <div className="global-risk-queue">
          {queue.map(
            (
              assessment,
              index,
            ) => (
              <button
                key={assessment.id}
                type="button"
                className="global-risk-item"
                onClick={() => {
                  onSelectRisk(
                    assessment,
                  );
                }}
              >
                <span className="global-risk-rank">
                  #{index + 1}
                </span>

                <div className="global-risk-main">
                  <div className="global-risk-item-heading">
                    <strong>
                      MMSI{" "}
                      {assessment.mmsi}
                    </strong>

                    <span
                      className={
                        `risk-badge risk-${assessment.risk_level}`
                      }
                    >
                      {assessment.risk_level}
                    </span>
                  </div>

                  <span className="global-risk-time">
                    {formatTimestamp(
                      assessment.observed_at,
                    )}
                  </span>

                  <span className="global-risk-metrics">
                    ML{" "}
                    {formatPercentile(
                      assessment.ml_anomaly_percentile,
                    )}

                    {" · "}

                    {assessment.rule_flag_count}
                    {" "}
                    rule flag
                    {assessment.rule_flag_count === 1
                      ? ""
                      : "s"}

                    {" · "}

                    {assessment.detector_agreement
                      ? "detectors agree"
                      : "single-source evidence"}
                  </span>
                </div>
              </button>
            ),
          )}
        </div>
      )}
    </section>
  );
}