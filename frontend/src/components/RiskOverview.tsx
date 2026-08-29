import {
  type FormEvent,
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
  RiskLevel,
  RiskSummaryResponse,
} from "../api/types";

import {
  buildRiskExplanation,
} from "../utils/riskExplanation";

interface RiskOverviewProps {
  onSelectRisk: (
    assessment: RiskAssessment,
  ) => void;
}

type RiskFilter =
  | "all"
  | RiskLevel;

type AgreementFilter =
  | "all"
  | "yes"
  | "no";

type MlFilter =
  | "all"
  | "95"
  | "98"
  | "99"
  | "99.5";

const PAGE_SIZE = 25;
const ACTIVE_WINDOW_MINUTES = 15;

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
    queueTotal,
    setQueueTotal,
  ] = useState(0);

  const [
    offset,
    setOffset,
  ] = useState(0);

  const [
    selectedQueueRiskId,
    setSelectedQueueRiskId,
  ] = useState<number | null>(
    null,
  );

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

  const [
    riskFilter,
    setRiskFilter,
  ] = useState<RiskFilter>(
    "all",
  );

  const [
    agreementFilter,
    setAgreementFilter,
  ] = useState<AgreementFilter>(
    "all",
  );

  const [
    mlFilter,
    setMlFilter,
  ] = useState<MlFilter>(
    "all",
  );

  const [
    mmsiInput,
    setMmsiInput,
  ] = useState("");

  const [
    mmsiFilter,
    setMmsiFilter,
  ] = useState("");

  const [
    validationError,
    setValidationError,
  ] = useState<string | null>(
    null,
  );

  const loadSummary =
    useCallback(
      async (
        signal?: AbortSignal,
      ) => {
        try {
          const response =
            await fetchRiskSummary(
              signal,
              {
                currentOnly: true,
                activeWindowMinutes:
                  ACTIVE_WINDOW_MINUTES,
              },
            );

          setSummary(
            response,
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
            "Failed to load risk summary:",
            caughtError,
          );
        }
      },
      [],
    );

  const loadQueue =
    useCallback(
      async (
        signal?: AbortSignal,
      ) => {
        setIsLoading(true);
        setError(null);

        try {
          const response =
            await fetchGlobalRiskQueue(
              {
                mmsi:
                  mmsiFilter
                  || undefined,

                riskLevel:
                  riskFilter === "all"
                    ? undefined
                    : riskFilter,

                minimumMlPercentile:
                  mlFilter === "all"
                    ? undefined
                    : Number(
                        mlFilter,
                      ),

                detectorAgreement:
                  agreementFilter
                    === "all"
                    ? undefined
                    : agreementFilter
                        === "yes",

                limit:
                  PAGE_SIZE,

                offset,

                currentOnly: true,

                activeWindowMinutes:
                  ACTIVE_WINDOW_MINUTES,
              },
              signal,
            );

          setQueue(
            response.items,
          );

          setQueueTotal(
            response.total,
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
            "Failed to load investigation queue:",
            caughtError,
          );

          setError(
            caughtError instanceof Error
              ? caughtError.message
              : "Could not load investigation queue.",
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
      [
        agreementFilter,
        mlFilter,
        mmsiFilter,
        offset,
        riskFilter,
      ],
    );

  useEffect(() => {
    const controller =
      new AbortController();

    void loadSummary(
      controller.signal,
    );

    return () => {
      controller.abort();
    };
  }, [loadSummary]);

  useEffect(() => {
    const controller =
      new AbortController();

    void loadQueue(
      controller.signal,
    );

    return () => {
      controller.abort();
    };
  }, [loadQueue]);

  const handleMmsiSubmit = (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    const value =
      mmsiInput.trim();

    if (
      value !== ""
      && !/^\d{9}$/.test(value)
    ) {
      setValidationError(
        "MMSI must contain exactly 9 digits.",
      );

      return;
    }

    setValidationError(
      null,
    );

    setOffset(0);
    setSelectedQueueRiskId(null);

    setMmsiFilter(
      value,
    );
  };

  const clearFilters = () => {
    setRiskFilter(
      "all",
    );

    setAgreementFilter(
      "all",
    );

    setMlFilter(
      "all",
    );

    setMmsiInput("");
    setMmsiFilter("");

    setOffset(0);

    setSelectedQueueRiskId(
      null,
    );

    setValidationError(
      null,
    );
  };

  const hasActiveFilters =
    riskFilter !== "all"
    || agreementFilter !== "all"
    || mlFilter !== "all"
    || mmsiFilter !== "";

  const firstVisible =
    queueTotal === 0
      ? 0
      : offset + 1;

  const lastVisible =
    Math.min(
      offset + queue.length,
      queueTotal,
    );

  const currentPage =
    Math.floor(
      offset / PAGE_SIZE,
    ) + 1;

  const totalPages =
    Math.max(
      1,
      Math.ceil(
        queueTotal / PAGE_SIZE,
      ),
    );

  const canGoPrevious =
    offset > 0;

  const canGoNext =
    offset + PAGE_SIZE
    < queueTotal;

  const handlePreviousPage = () => {
    setSelectedQueueRiskId(
      null,
    );

    setOffset(
      (current) =>
        Math.max(
          0,
          current - PAGE_SIZE,
        ),
    );
  };

  const handleNextPage = () => {
    if (!canGoNext) {
      return;
    }

    setSelectedQueueRiskId(
      null,
    );

    setOffset(
      (current) =>
        current + PAGE_SIZE,
    );
  };

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
            Highest-priority AIS observations
            inside the current 15-minute active
            window.
          </p>
        </div>

        <button
          type="button"
          className="risk-overview-refresh"
          disabled={isLoading}
          onClick={() => {
            void loadQueue();
            void loadSummary();
          }}
        >
          {isLoading
            ? "Loading…"
            : "Refresh risk"}
        </button>
      </div>

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
              Immediate investigation
              priority
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
              Rules and ML both detected
              evidence
            </small>
          </article>
        </div>
      )}

      <div className="global-risk-filters">
        <label>
          <span>
            Priority
          </span>

          <select
            value={riskFilter}
            onChange={(event) => {
              const value =
                event.target.value;

              if (
                value === "all"
                || value === "critical"
                || value === "high"
                || value === "medium"
                || value === "low"
              ) {
                setRiskFilter(
                  value,
                );

                setOffset(0);

                setSelectedQueueRiskId(
                  null,
                );
              }
            }}
          >
            <option value="all">
              All priorities
            </option>

            <option value="critical">
              Critical
            </option>

            <option value="high">
              High
            </option>

            <option value="medium">
              Medium
            </option>

            <option value="low">
              Low
            </option>
          </select>
        </label>

        <label>
          <span>
            ML percentile
          </span>

          <select
            value={mlFilter}
            onChange={(event) => {
              const value =
                event.target.value;

              if (
                value === "all"
                || value === "95"
                || value === "98"
                || value === "99"
                || value === "99.5"
              ) {
                setMlFilter(
                  value,
                );

                setOffset(0);

                setSelectedQueueRiskId(
                  null,
                );
              }
            }}
          >
            <option value="all">
              Any ML score
            </option>

            <option value="95">
              ≥ 95th
            </option>

            <option value="98">
              ≥ 98th
            </option>

            <option value="99">
              ≥ 99th
            </option>

            <option value="99.5">
              ≥ 99.5th
            </option>
          </select>
        </label>

        <label>
          <span>
            Detector agreement
          </span>

          <select
            value={
              agreementFilter
            }
            onChange={(event) => {
              const value =
                event.target.value;

              if (
                value === "all"
                || value === "yes"
                || value === "no"
              ) {
                setAgreementFilter(
                  value,
                );

                setOffset(0);

                setSelectedQueueRiskId(
                  null,
                );
              }
            }}
          >
            <option value="all">
              Any
            </option>

            <option value="yes">
              Rules + ML agree
            </option>

            <option value="no">
              No agreement
            </option>
          </select>
        </label>

        <form
          className="global-risk-mmsi-filter"
          onSubmit={
            handleMmsiSubmit
          }
        >
          <label>
            <span>
              MMSI
            </span>

            <input
              type="search"
              inputMode="numeric"
              maxLength={9}
              placeholder="9-digit MMSI"
              value={mmsiInput}
              onChange={(event) => {
                setMmsiInput(
                  event.target.value,
                );
              }}
            />
          </label>

          <button type="submit">
            Apply
          </button>
        </form>

        {hasActiveFilters && (
          <button
            type="button"
            className="global-risk-clear"
            onClick={
              clearFilters
            }
          >
            Clear filters
          </button>
        )}
      </div>

      {validationError !== null && (
        <div
          className="risk-filter-error"
          role="alert"
        >
          {validationError}
        </div>
      )}

      {error !== null && (
        <div
          className="risk-overview-error"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="global-risk-queue-heading">
        <div>
          <h3>
            Investigation queue
          </h3>

          <span>
            Showing{" "}
            {firstVisible}
            {"–"}
            {lastVisible}
            {" "}
            of{" "}
            {queueTotal.toLocaleString()}
            {" "}
            matching assessments
          </span>
        </div>

        {summary !== null && (
          <span className="risk-total-label">
            {summary.total.toLocaleString()}
            {" "}
            assessments in current window
          </span>
        )}
      </div>

      {isLoading
        && queue.length === 0 ? (
          <div className="global-risk-empty">
            Loading investigation
            queue…
          </div>
        ) : queue.length === 0 ? (
          <div className="global-risk-empty">
            No risk assessments match
            these filters.
          </div>
        ) : (
          <>
            <div className="global-risk-queue">
              {queue.map(
                (
                  assessment,
                  index,
                ) => {
                  const isSelected =
                    assessment.id
                    === selectedQueueRiskId;

                  return (
                    <button
                      key={
                        assessment.id
                      }
                      type="button"
                      className={
                        isSelected
                          ? "global-risk-item selected"
                          : "global-risk-item"
                      }
                      onClick={() => {
                        setSelectedQueueRiskId(
                          assessment.id,
                        );

                        onSelectRisk(
                          assessment,
                        );
                      }}
                    >
                      <span className="global-risk-rank">
                        #
                        {offset
                          + index
                          + 1}
                      </span>

                      <div className="global-risk-main">
                        <div className="global-risk-item-heading">
                          <strong>
                            MMSI{" "}
                            {
                              assessment.mmsi
                            }
                          </strong>

                          <span
                            className={
                              `risk-badge risk-${assessment.risk_level}`
                            }
                          >
                            {
                              assessment.risk_level
                            }
                          </span>
                        </div>

                        <span className="global-risk-time">
                          {formatTimestamp(
                            assessment
                              .observed_at,
                          )}
                        </span>

                        <span className="global-risk-metrics">
                          ML{" "}
                          {formatPercentile(
                            assessment
                              .ml_anomaly_percentile,
                          )}

                          {" · "}

                          {
                            assessment
                              .rule_flag_count
                          }{" "}
                          rule flag
                          {
                            assessment
                              .rule_flag_count
                              === 1
                              ? ""
                              : "s"
                          }

                          {" · "}

                          {
                            assessment
                              .detector_agreement
                              ? "detectors agree"
                              : "single-source evidence"
                          }
                        </span>

                        <span className="global-risk-explanation">
                          {buildRiskExplanation(
                            assessment,
                          )}
                        </span>
                      </div>
                    </button>
                  );
                },
              )}
            </div>

            <div className="global-risk-pagination">
              <button
                type="button"
                disabled={
                  !canGoPrevious
                  || isLoading
                }
                onClick={
                  handlePreviousPage
                }
              >
                ← Previous
              </button>

              <span>
                Page{" "}
                {currentPage}
                {" "}
                of{" "}
                {totalPages}
              </span>

              <button
                type="button"
                disabled={
                  !canGoNext
                  || isLoading
                }
                onClick={
                  handleNextPage
                }
              >
                Next →
              </button>
            </div>
          </>
        )}
    </section>
  );
}