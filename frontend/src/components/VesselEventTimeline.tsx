import {
  useMemo,
  useState,
} from "react";

import type {
  Anomaly,
  RiskAssessment,
} from "../api/types";

interface VesselEventTimelineProps {
  anomalies: Anomaly[];
  risks: RiskAssessment[];

  selectedAnomalyId: number | null;
  selectedRiskId: number | null;

  onSelectAnomaly: (
    anomalyId: number,
  ) => void;

  onSelectRisk: (
    riskId: number,
  ) => void;
}

type TimelineFilter =
  | "all"
  | "risk"
  | "anomaly";

type TimelineOrder =
  | "newest"
  | "oldest";

type TimelineIncident = {
  timestamp: string;
  sortTimestamp: number;
  risk: RiskAssessment | null;
  anomalies: Anomaly[];
};

function parseTimestamp(
  timestamp: string,
): number {
  const value =
    new Date(timestamp).getTime();

  return Number.isNaN(value)
    ? 0
    : value;
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
  value: number,
): string {
  return `${value.toFixed(2)}th`;
}

function humanize(
  value: string,
): string {
  const cleaned =
    value
      .replaceAll("_", " ")
      .trim();

  if (!cleaned) {
    return cleaned;
  }

  return (
    cleaned.charAt(0).toUpperCase()
    + cleaned.slice(1)
  );
}

function createIncidentKey(
  timestamp: string,
): string {
  /*
   * Risk assessments and anomaly alerts
   * generated from the same AIS message
   * currently share the same observation
   * timestamp.
   *
   * Grouping by ISO timestamp therefore
   * reconstructs the original observation.
   */
  const date =
    new Date(timestamp);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return timestamp;
  }

  return date.toISOString();
}

export function VesselEventTimeline({
  anomalies,
  risks,
  selectedAnomalyId,
  selectedRiskId,
  onSelectAnomaly,
  onSelectRisk,
}: VesselEventTimelineProps) {
  const [
    filter,
    setFilter,
  ] = useState<TimelineFilter>(
    "all",
  );

  const [
    order,
    setOrder,
  ] = useState<TimelineOrder>(
    "newest",
  );

  const incidents =
    useMemo<TimelineIncident[]>(() => {
      const grouped =
        new Map<
          string,
          TimelineIncident
        >();

      for (const risk of risks) {
        const key =
          createIncidentKey(
            risk.observed_at,
          );

        const existing =
          grouped.get(key);

        if (existing) {
          /*
           * There should normally be one
           * persisted risk assessment per
           * AIS observation.
           *
           * If duplicates somehow exist,
           * keep the first one rather than
           * silently replacing it.
           */
          if (
            existing.risk
            === null
          ) {
            existing.risk =
              risk;
          }

          continue;
        }

        grouped.set(
          key,
          {
            timestamp:
              risk.observed_at,

            sortTimestamp:
              parseTimestamp(
                risk.observed_at,
              ),

            risk,

            anomalies: [],
          },
        );
      }

      for (
        const anomaly
        of anomalies
      ) {
        const key =
          createIncidentKey(
            anomaly.observed_at,
          );

        const existing =
          grouped.get(key);

        if (existing) {
          existing.anomalies.push(
            anomaly,
          );

          continue;
        }

        grouped.set(
          key,
          {
            timestamp:
              anomaly.observed_at,

            sortTimestamp:
              parseTimestamp(
                anomaly.observed_at,
              ),

            risk: null,

            anomalies: [
              anomaly,
            ],
          },
        );
      }

      return Array.from(
        grouped.values(),
      );
    }, [
      anomalies,
      risks,
    ]);

  const visibleIncidents =
    useMemo(() => {
      const filtered =
        incidents.filter(
          (incident) => {
            if (
              filter === "risk"
            ) {
              return (
                incident.risk
                !== null
              );
            }

            if (
              filter === "anomaly"
            ) {
              return (
                incident.anomalies
                  .length > 0
              );
            }

            return true;
          },
        );

      return [
        ...filtered,
      ].sort(
        (
          left,
          right,
        ) =>
          order
            === "newest"
            ? right.sortTimestamp
              - left.sortTimestamp
            : left.sortTimestamp
              - right.sortTimestamp,
      );
    }, [
      filter,
      incidents,
      order,
    ]);

  const correlatedCount =
    useMemo(
      () =>
        incidents.filter(
          (incident) =>
            incident.risk
              !== null
            && incident.anomalies
              .length > 0,
        ).length,
      [incidents],
    );

  return (
    <section className="vessel-event-timeline">
      <div className="timeline-heading">
        <div>
          <h3>
            Vessel event timeline
          </h3>

          <span>
            {
              visibleIncidents.length
            }
            {" "}
            of
            {" "}
            {
              incidents.length
            }
            {" "}
            incidents
          </span>
        </div>

        {correlatedCount > 0 && (
          <span className="timeline-correlation-count">
            {correlatedCount}
            {" "}
            correlated
          </span>
        )}
      </div>

      <div className="timeline-controls">
        <label>
          <span>
            Events
          </span>

          <select
            value={filter}
            onChange={(event) => {
              const value =
                event.target.value;

              if (
                value === "all"
                || value === "risk"
                || value === "anomaly"
              ) {
                setFilter(
                  value,
                );
              }
            }}
          >
            <option value="all">
              All incidents
            </option>

            <option value="risk">
              Risk incidents
            </option>

            <option value="anomaly">
              Anomaly incidents
            </option>
          </select>
        </label>

        <label>
          <span>
            Order
          </span>

          <select
            value={order}
            onChange={(event) => {
              const value =
                event.target.value;

              if (
                value === "newest"
                || value === "oldest"
              ) {
                setOrder(
                  value,
                );
              }
            }}
          >
            <option value="newest">
              Newest first
            </option>

            <option value="oldest">
              Oldest first
            </option>
          </select>
        </label>
      </div>

      {visibleIncidents.length
        === 0 ? (
          <div className="timeline-empty">
            No matching vessel events
            were recorded.
          </div>
        ) : (
          <div className="timeline-list">
            {visibleIncidents.map(
              (
                incident,
              ) => {
                const {
                  risk,
                  anomalies:
                    incidentAnomalies,
                } = incident;

                const selectedRisk =
                  risk !== null
                  && risk.id
                    === selectedRiskId;

                const selectedAnomaly =
                  incidentAnomalies.some(
                    (anomaly) =>
                      anomaly.id
                      === selectedAnomalyId,
                  );

                const isSelected =
                  selectedRisk
                  || selectedAnomaly;

                const isCorrelated =
                  risk !== null
                  && incidentAnomalies
                    .length > 0;

                const primaryAnomaly =
                  incidentAnomalies[0]
                  ?? null;

                const handleClick =
                  () => {
                    /*
                     * Prefer the hybrid-risk
                     * assessment when the
                     * incident has one.
                     *
                     * It represents the
                     * combined investigation
                     * result for this AIS
                     * observation.
                     */
                    if (
                      risk !== null
                    ) {
                      onSelectRisk(
                        risk.id,
                      );

                      return;
                    }

                    if (
                      primaryAnomaly
                      !== null
                    ) {
                      onSelectAnomaly(
                        primaryAnomaly.id,
                      );
                    }
                  };

                return (
                  <button
                    key={
                      createIncidentKey(
                        incident.timestamp,
                      )
                    }
                    type="button"
                    className={
                      isSelected
                        ? "timeline-event timeline-incident selected"
                        : "timeline-event timeline-incident"
                    }
                    onClick={
                      handleClick
                    }
                  >
                    <span
                      className={
                        isCorrelated
                          ? "timeline-marker timeline-marker-correlated"
                          : risk !== null
                            ? "timeline-marker timeline-marker-risk"
                            : "timeline-marker timeline-marker-anomaly"
                      }
                    >
                      {isCorrelated
                        ? "C"
                        : risk !== null
                          ? "R"
                          : "A"}
                    </span>

                    <div className="timeline-event-content">
                      <div className="timeline-event-header">
                        <strong>
                          {isCorrelated
                            ? "Correlated incident"
                            : risk !== null
                              ? `${risk.risk_level.toUpperCase()} investigation priority`
                              : primaryAnomaly !== null
                                ? humanize(
                                    primaryAnomaly.anomaly_type,
                                  )
                                : "AIS event"}
                        </strong>

                        {risk !== null ? (
                          <span
                            className={
                              `risk-badge risk-${risk.risk_level}`
                            }
                          >
                            {
                              risk.risk_level
                            }
                          </span>
                        ) : primaryAnomaly
                          !== null ? (
                            <span
                              className={
                                `severity-badge severity-${primaryAnomaly.severity.toLowerCase()}`
                              }
                            >
                              {
                                primaryAnomaly.severity
                              }
                            </span>
                          ) : null}
                      </div>

                      <span className="timeline-event-time">
                        {formatTimestamp(
                          incident.timestamp,
                        )}
                      </span>

                      {risk !== null && (
                        <div className="timeline-risk-summary">
                          <span>
                            ML{" "}
                            {formatPercentile(
                              risk.ml_anomaly_percentile,
                            )}
                          </span>

                          <span>
                            {
                              risk.rule_flag_count
                            }
                            {" "}
                            rule flag
                            {
                              risk.rule_flag_count
                                === 1
                                ? ""
                                : "s"
                            }
                          </span>

                          <span>
                            {
                              risk.detector_agreement
                                ? "Detectors agree"
                                : "Single-source evidence"
                            }
                          </span>
                        </div>
                      )}

                      {incidentAnomalies.length
                        > 0 && (
                          <div className="timeline-anomaly-group">
                            <span className="timeline-anomaly-group-title">
                              {
                                incidentAnomalies
                                  .length
                              }
                              {" "}
                              anomaly
                              {
                                incidentAnomalies
                                  .length
                                  === 1
                                  ? ""
                                  : "ies"
                              }
                            </span>

                            <ul>
                              {incidentAnomalies.map(
                                (
                                  anomaly,
                                ) => (
                                  <li
                                    key={
                                      anomaly.id
                                    }
                                  >
                                    <span>
                                      {humanize(
                                        anomaly.anomaly_type,
                                      )}
                                    </span>

                                    <span
                                      className={
                                        `severity-badge severity-${anomaly.severity.toLowerCase()}`
                                      }
                                    >
                                      {
                                        anomaly.severity
                                      }
                                    </span>
                                  </li>
                                ),
                              )}
                            </ul>
                          </div>
                        )}

                      {risk === null
                        && primaryAnomaly
                          !== null && (
                          <span className="timeline-event-description">
                            {
                              primaryAnomaly.message
                            }
                          </span>
                        )}

                      {isCorrelated && (
                        <span className="timeline-correlation-note">
                          Rule anomaly and hybrid
                          risk assessment occurred
                          at the same AIS
                          observation.
                        </span>
                      )}
                    </div>
                  </button>
                );
              },
            )}
          </div>
        )}
    </section>
  );
}