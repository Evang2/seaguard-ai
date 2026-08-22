import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import "./App.css";
import "./components/risk.css";

import {
  fetchRecentPositions,
  fetchVesselAnomalies,
  fetchVesselRiskAssessments,
  fetchVesselTrajectory,
} from "./api/client";

import type {
  Anomaly,
  RecentPosition,
  RiskAssessment,
  RiskLevel,
  VesselTrajectory,
} from "./api/types";

import { RiskOverview } from "./components/RiskOverview";
import { VesselMap as VesselMapComponent } from "./components/VesselMap";

type VesselMapProps = {
  positions: RecentPosition[];
  selectedMmsi: string | null;
  trajectory: VesselTrajectory | null;
  anomalies: Anomaly[];
  riskAssessments: RiskAssessment[];
  selectedAnomalyId: number | null;
  selectedRiskId: number | null;
  onSelectVessel: (mmsi: string) => void;
  onSelectAnomaly: (anomalyId: number) => void;
  onSelectRisk: (riskId: number) => void;
};

const VesselMap = (
  props: VesselMapProps,
) => <VesselMapComponent {...props} />;

type RiskDisplayFilter =
  | "elevated"
  | "all"
  | RiskLevel;

function formatMeasurement(
  value: number | null,
  unit: string,
): string {
  if (
    value === null
    || !Number.isFinite(value)
  ) {
    return "Not available";
  }

  return `${value.toFixed(1)} ${unit}`;
}

function formatTimestamp(
  timestamp: string,
): string {
  const date = new Date(timestamp);

  return Number.isNaN(date.getTime())
    ? timestamp
    : date.toLocaleString();
}

function formatPercentile(
  value: number,
): string {
  return `${value.toFixed(2)}th`;
}

function displayVesselName(
  position: RecentPosition,
): string {
  return (
    position.vessel_name?.trim()
    || "Unknown vessel"
  );
}

function App() {
  const [
    positions,
    setPositions,
  ] = useState<RecentPosition[]>([]);

  const [
    isLoading,
    setIsLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    searchQuery,
    setSearchQuery,
  ] = useState("");

  const [
    selectedMmsi,
    setSelectedMmsi,
  ] = useState<string | null>(null);

  const [
    selectedTrajectory,
    setSelectedTrajectory,
  ] = useState<VesselTrajectory | null>(
    null,
  );

  const [
    selectedAnomalies,
    setSelectedAnomalies,
  ] = useState<Anomaly[]>([]);

  const [
    selectedRisks,
    setSelectedRisks,
  ] = useState<RiskAssessment[]>([]);

  const [
    selectionLoading,
    setSelectionLoading,
  ] = useState(false);

  const [
    selectionError,
    setSelectionError,
  ] = useState<string | null>(null);

  const [
    severityFilter,
    setSeverityFilter,
  ] = useState("all");

  const [
    anomalyTypeFilter,
    setAnomalyTypeFilter,
  ] = useState("all");

  const [
    selectedAnomalyId,
    setSelectedAnomalyId,
  ] = useState<number | null>(null);

  const [
    riskLevelFilter,
    setRiskLevelFilter,
  ] = useState<RiskDisplayFilter>(
    "elevated",
  );

  const [
    selectedRiskId,
    setSelectedRiskId,
  ] = useState<number | null>(null);

  const pendingRiskIdRef =
    useRef<number | null>(null);

  const loadPositions =
    useCallback(async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response =
          await fetchRecentPositions(500);

        setPositions(response.items);
      } catch (caughtError) {
        console.error(
          "Failed to load positions:",
          caughtError,
        );

        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "An unknown API error occurred.",
        );
      } finally {
        setIsLoading(false);
      }
    }, []);

  useEffect(() => {
    void loadPositions();
  }, [loadPositions]);

  useEffect(() => {
    if (selectedMmsi === null) {
      setSelectedTrajectory(null);
      setSelectedAnomalies([]);
      setSelectedRisks([]);

      setSelectedAnomalyId(null);
      setSelectedRiskId(null);

      pendingRiskIdRef.current =
        null;

      setSeverityFilter("all");
      setAnomalyTypeFilter("all");
      setRiskLevelFilter("elevated");

      setSelectionError(null);
      setSelectionLoading(false);

      return;
    }

    const controller =
      new AbortController();

    const loadSelectedVessel =
      async () => {
        setSelectionLoading(true);
        setSelectionError(null);

        setSelectedTrajectory(null);
        setSelectedAnomalies([]);
        setSelectedRisks([]);

        setSelectedAnomalyId(null);
        setSelectedRiskId(null);

        try {
          const [
            trajectory,
            anomalyResponse,
            riskResponse,
          ] = await Promise.all([
            fetchVesselTrajectory(
              selectedMmsi,
              controller.signal,
            ),

            fetchVesselAnomalies(
              selectedMmsi,
              controller.signal,
            ),

            fetchVesselRiskAssessments(
              selectedMmsi,
              controller.signal,
            ),
          ]);

          setSelectedTrajectory(
            trajectory,
          );

          setSelectedAnomalies(
            anomalyResponse.items,
          );

          setSelectedRisks(
            riskResponse.items,
          );

          const pendingRiskId =
            pendingRiskIdRef.current;

          if (
            pendingRiskId !== null
            && riskResponse.items.some(
              (assessment) =>
                assessment.id
                === pendingRiskId,
            )
          ) {
            setSelectedRiskId(
              pendingRiskId,
            );

            pendingRiskIdRef.current =
              null;
          }
        } catch (caughtError) {
          if (
            caughtError
              instanceof DOMException
            && caughtError.name
              === "AbortError"
          ) {
            return;
          }

          pendingRiskIdRef.current =
            null;

          setSelectionError(
            caughtError instanceof Error
              ? caughtError.message
              : "Could not load vessel data.",
          );
        } finally {
          if (
            !controller.signal.aborted
          ) {
            setSelectionLoading(false);
          }
        }
      };

    void loadSelectedVessel();

    return () => {
      controller.abort();
    };
  }, [selectedMmsi]);

  const filteredPositions =
    useMemo(() => {
      const query =
        searchQuery
          .trim()
          .toLowerCase();

      if (!query) {
        return positions;
      }

      return positions.filter(
        (position) => {
          const vesselName =
            position.vessel_name
              ?.toLowerCase()
            ?? "";

          return (
            position.mmsi.includes(
              query,
            )
            || vesselName.includes(
              query,
            )
          );
        },
      );
    }, [
      positions,
      searchQuery,
    ]);

  const selectedPosition =
    useMemo(
      () =>
        positions.find(
          (position) =>
            position.mmsi
            === selectedMmsi,
        )
        ?? null,
      [
        positions,
        selectedMmsi,
      ],
    );

  const anomalyTypes =
    useMemo(
      () =>
        Array.from(
          new Set(
            selectedAnomalies.map(
              (item) =>
                item.anomaly_type,
            ),
          ),
        ).sort(),
      [selectedAnomalies],
    );

  const filteredAnomalies =
    useMemo(
      () =>
        selectedAnomalies.filter(
          (anomaly) => {
            const severityMatches =
              severityFilter === "all"
              || anomaly.severity
                .toLowerCase()
                === severityFilter;

            const typeMatches =
              anomalyTypeFilter
                === "all"
              || anomaly.anomaly_type
                === anomalyTypeFilter;

            return (
              severityMatches
              && typeMatches
            );
          },
        ),
      [
        selectedAnomalies,
        severityFilter,
        anomalyTypeFilter,
      ],
    );

  const filteredRisks =
    useMemo(
      () =>
        selectedRisks.filter(
          (assessment) => {
            if (
              riskLevelFilter
              === "all"
            ) {
              return true;
            }

            if (
              riskLevelFilter
              === "elevated"
            ) {
              return (
                assessment
                  .risk_level
                !== "low"
              );
            }

            return (
              assessment.risk_level
              === riskLevelFilter
            );
          },
        ),
      [
        selectedRisks,
        riskLevelFilter,
      ],
    );

  const selectedAnomaly =
    useMemo(
      () =>
        selectedAnomalies.find(
          (item) =>
            item.id
            === selectedAnomalyId,
        )
        ?? null,
      [
        selectedAnomalies,
        selectedAnomalyId,
      ],
    );

  const selectedRisk =
    useMemo(
      () =>
        selectedRisks.find(
          (item) =>
            item.id
            === selectedRiskId,
        )
        ?? null,
      [
        selectedRisks,
        selectedRiskId,
      ],
    );

  const movingVesselCount =
    useMemo(
      () =>
        positions.filter(
          (position) =>
            position.sog !== null
            && position.sog >= 0.5,
        ).length,
      [positions],
    );

  const elevatedRiskCount =
    useMemo(
      () =>
        selectedRisks.filter(
          (assessment) =>
            assessment.risk_level
            !== "low",
        ).length,
      [selectedRisks],
    );

  const handleSelectVessel =
    useCallback(
      (mmsi: string) => {
        pendingRiskIdRef.current =
          null;

        setSelectedMmsi(
          mmsi,
        );
      },
      [],
    );

  const handleSelectAnomaly =
    useCallback(
      (anomalyId: number) => {
        pendingRiskIdRef.current =
          null;

        setSelectedAnomalyId(
          anomalyId,
        );

        setSelectedRiskId(
          null,
        );
      },
      [],
    );

  const handleSelectRisk =
    useCallback(
      (riskId: number) => {
        pendingRiskIdRef.current =
          null;

        setSelectedRiskId(
          riskId,
        );

        setSelectedAnomalyId(
          null,
        );
      },
      [],
    );

  const handleSelectGlobalRisk =
    useCallback(
      (
        assessment:
          RiskAssessment,
      ) => {
        /*
         * Use the selected assessment's
         * exact priority as the filter.
         *
         * This guarantees the assessment
         * remains visible after its vessel
         * is loaded.
         */
        setRiskLevelFilter(
          assessment.risk_level,
        );

        setSelectedAnomalyId(
          null,
        );

        /*
         * If the vessel is already loaded,
         * there is no need to refetch it.
         */
        if (
          assessment.mmsi
          === selectedMmsi
        ) {
          pendingRiskIdRef.current =
            null;

          setSelectedRiskId(
            assessment.id,
          );

          return;
        }

        /*
         * The selected risk belongs to
         * another vessel.
         *
         * Remember its ID while the vessel
         * trajectory/anomaly/risk requests
         * are being loaded.
         */
        pendingRiskIdRef.current =
          assessment.id;

        setSelectedMmsi(
          assessment.mmsi,
        );
      },
      [selectedMmsi],
    );

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">
            Maritime decision support
          </p>

          <h1>
            SeaGuard AI
          </h1>

          <p className="subtitle">
            Vessel monitoring,
            explainable AIS anomaly
            detection, and hybrid
            investigation priority.
          </p>
        </div>

        <button
          type="button"
          className="refresh-button"
          onClick={() =>
            void loadPositions()
          }
          disabled={isLoading}
        >
          {isLoading
            ? "Loading…"
            : "Refresh positions"}
        </button>
      </header>

      <section
        className="summary-grid"
        aria-label={
          "Vessel position summary"
        }
      >
        <article className="summary-card">
          <span>
            Displayed vessels
          </span>

          <strong>
            {positions.length}
          </strong>
        </article>

        <article className="summary-card">
          <span>
            Moving vessels
          </span>

          <strong>
            {movingVesselCount}
          </strong>
        </article>

        <article className="summary-card">
          <span>
            API status
          </span>

          <strong>
            {error === null
              ? "Connected"
              : "Unavailable"}
          </strong>
        </article>
      </section>

      <RiskOverview
        onSelectRisk={
          handleSelectGlobalRisk
        }
      />

      {error !== null && (
        <div
          className="error-banner"
          role="alert"
        >
          <strong>
            Could not load vessel
            positions.
          </strong>

          <span>
            {error}
          </span>
        </div>
      )}

      <section className="workspace">
        <aside className="vessel-sidebar">
          <div className="panel-heading">
            <div>
              <h2>
                Vessels
              </h2>

              <p>
                Select a recent AIS
                position.
              </p>
            </div>
          </div>

          <label
            className="search-field"
            htmlFor="vessel-search"
          >
            <span>
              Search vessel
            </span>

            <input
              id="vessel-search"
              type="search"
              value={searchQuery}
              placeholder="Name or MMSI"
              onChange={(event) =>
                setSearchQuery(
                  event.target.value,
                )
              }
            />
          </label>

          <p className="result-count">
            {filteredPositions.length}
            {" "}
            result
            {filteredPositions.length
              === 1
              ? ""
              : "s"}
          </p>

          <div className="vessel-list">
            {filteredPositions.map(
              (position) => {
                const isSelected =
                  selectedMmsi
                  === position.mmsi;

                return (
                  <button
                    key={
                      position.mmsi
                    }
                    type="button"
                    className={
                      isSelected
                        ? "vessel-list-item selected"
                        : "vessel-list-item"
                    }
                    onClick={() =>
                      handleSelectVessel(
                        position.mmsi,
                      )
                    }
                  >
                    <span className="vessel-list-name">
                      {displayVesselName(
                        position,
                      )}
                    </span>

                    <span className="vessel-list-mmsi">
                      MMSI{" "}
                      {position.mmsi}
                    </span>

                    <span className="vessel-list-speed">
                      {formatMeasurement(
                        position.sog,
                        "kn",
                      )}
                    </span>
                  </button>
                );
              },
            )}

            {!isLoading
              && filteredPositions
                .length === 0 && (
                <div className="empty-list">
                  No matching vessels
                  found.
                </div>
              )}
          </div>
        </aside>

        <section className="map-panel">
          <div className="map-panel-header">
            <div>
              <h2>
                Vessel map
              </h2>

              <p>
                Click vessel, anomaly,
                or risk markers to
                investigate.
              </p>
            </div>
          </div>

          <VesselMap
            positions={positions}
            selectedMmsi={
              selectedMmsi
            }
            trajectory={
              selectedTrajectory
            }
            anomalies={
              filteredAnomalies
            }
            riskAssessments={
              filteredRisks
            }
            selectedAnomalyId={
              selectedAnomalyId
            }
            selectedRiskId={
              selectedRiskId
            }
            onSelectVessel={
              handleSelectVessel
            }
            onSelectAnomaly={
              handleSelectAnomaly
            }
            onSelectRisk={
              handleSelectRisk
            }
          />
        </section>

        <aside className="details-panel">
          <div className="panel-heading">
            <div>
              <h2>
                Vessel details
              </h2>

              <p>
                Latest imported AIS
                report.
              </p>
            </div>

            {selectedPosition
              !== null && (
                <button
                  type="button"
                  className="clear-selection"
                  onClick={() => {
                    pendingRiskIdRef.current =
                      null;

                    setSelectedMmsi(
                      null,
                    );
                  }}
                >
                  Clear
                </button>
              )}
          </div>

          {selectedPosition
            === null ? (
              <div className="empty-details">
                Select a vessel from
                the map or vessel
                list.
              </div>
            ) : (
              <div className="vessel-details">
                <div className="selected-vessel-title">
                  <span className="status-dot" />

                  <div>
                    <strong>
                      {displayVesselName(
                        selectedPosition,
                      )}
                    </strong>

                    <span>
                      MMSI{" "}
                      {
                        selectedPosition
                          .mmsi
                      }
                    </span>
                  </div>
                </div>

                <div className="selected-data-summary risk-summary-grid">
                  {selectionLoading ? (
                    <span>
                      Loading trajectory,
                      anomalies, and risk…
                    </span>
                  ) : selectionError
                    !== null ? (
                      <span className="selection-error">
                        {selectionError}
                      </span>
                    ) : (
                      <>
                        <div>
                          <span>
                            Anomalies
                          </span>

                          <strong>
                            {
                              selectedAnomalies
                                .length
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            Elevated risk
                          </span>

                          <strong>
                            {
                              elevatedRiskCount
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            Trajectory
                          </span>

                          <strong>
                            {selectedTrajectory
                              === null
                              ? "Unavailable"
                              : "Loaded"}
                          </strong>
                        </div>
                      </>
                    )}
                </div>

                <section className="risk-investigation">
                  <div className="risk-section-heading">
                    <div>
                      <h3>
                        Hybrid
                        investigation
                        priority
                      </h3>

                      <span>
                        {
                          filteredRisks.length
                        }{" "}
                        of{" "}
                        {
                          selectedRisks.length
                        }{" "}
                        assessments
                      </span>
                    </div>
                  </div>

                  {!selectionLoading
                    && selectedRisks.length
                      > 0 && (
                      <>
                        <div className="risk-filters">
                          <label>
                            <span>
                              Priority
                            </span>

                            <select
                              value={
                                riskLevelFilter
                              }
                              onChange={(
                                event,
                              ) => {
                                const value =
                                  event
                                    .target
                                    .value;

                                if (
                                  value
                                    === "elevated"
                                  || value
                                    === "all"
                                  || value
                                    === "critical"
                                  || value
                                    === "high"
                                  || value
                                    === "medium"
                                  || value
                                    === "low"
                                ) {
                                  setRiskLevelFilter(
                                    value,
                                  );

                                  setSelectedRiskId(
                                    null,
                                  );
                                }
                              }}
                            >
                              <option value="elevated">
                                Elevated only
                              </option>

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
                        </div>

                        <div className="risk-list">
                          {filteredRisks.map(
                            (
                              assessment,
                            ) => {
                              const isSelected =
                                assessment.id
                                === selectedRiskId;

                              return (
                                <button
                                  key={
                                    assessment.id
                                  }
                                  type="button"
                                  className={
                                    isSelected
                                      ? "risk-list-item selected"
                                      : "risk-list-item"
                                  }
                                  onClick={() =>
                                    handleSelectRisk(
                                      assessment.id,
                                    )
                                  }
                                >
                                  <div className="risk-list-header">
                                    <strong>
                                      ML{" "}
                                      {formatPercentile(
                                        assessment
                                          .ml_anomaly_percentile,
                                      )}
                                    </strong>

                                    <span
                                      className={
                                        `risk-badge risk-${assessment.risk_level}`
                                      }
                                    >
                                      {
                                        assessment
                                          .risk_level
                                      }
                                    </span>
                                  </div>

                                  <span className="risk-time">
                                    {formatTimestamp(
                                      assessment
                                        .observed_at,
                                    )}
                                  </span>

                                  <span className="risk-evidence">
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
                                </button>
                              );
                            },
                          )}

                          {filteredRisks.length
                            === 0 && (
                              <div className="empty-risks">
                                No risk
                                assessments
                                match this
                                filter.
                              </div>
                            )}
                        </div>

                        {selectedRisk
                          !== null && (
                            <div className="selected-risk-details">
                              <div className="selected-risk-heading">
                                <strong>
                                  Investigation
                                  priority
                                </strong>

                                <span
                                  className={
                                    `risk-badge risk-${selectedRisk.risk_level}`
                                  }
                                >
                                  {
                                    selectedRisk
                                      .risk_level
                                  }
                                </span>
                              </div>

                              <dl>
                                <dt>
                                  Observed
                                </dt>

                                <dd>
                                  {formatTimestamp(
                                    selectedRisk
                                      .observed_at,
                                  )}
                                </dd>

                                <dt>
                                  ML percentile
                                </dt>

                                <dd>
                                  {formatPercentile(
                                    selectedRisk
                                      .ml_anomaly_percentile,
                                  )}
                                </dd>

                                <dt>
                                  ML score
                                </dt>

                                <dd>
                                  {selectedRisk
                                    .ml_anomaly_score
                                    .toFixed(
                                      6,
                                    )}
                                </dd>

                                <dt>
                                  Rule severity
                                </dt>

                                <dd>
                                  {
                                    selectedRisk
                                      .rule_severity
                                  }
                                </dd>

                                <dt>
                                  Rule flags
                                </dt>

                                <dd>
                                  {
                                    selectedRisk
                                      .rule_flag_count
                                  }
                                </dd>

                                <dt>
                                  Detector
                                  agreement
                                </dt>

                                <dd>
                                  {
                                    selectedRisk
                                      .detector_agreement
                                      ? "Yes"
                                      : "No"
                                  }
                                </dd>

                                <dt>
                                  Latitude
                                </dt>

                                <dd>
                                  {selectedRisk
                                    .latitude
                                    .toFixed(
                                      5,
                                    )}
                                </dd>

                                <dt>
                                  Longitude
                                </dt>

                                <dd>
                                  {selectedRisk
                                    .longitude
                                    .toFixed(
                                      5,
                                    )}
                                </dd>

                                <dt>
                                  Model
                                </dt>

                                <dd>
                                  {
                                    selectedRisk
                                      .assessment_version
                                  }
                                </dd>
                              </dl>

                              <p>
                                {
                                  selectedRisk
                                    .risk_reasons
                                }
                              </p>

                              <small>
                                Priority is an
                                investigation
                                ranking, not a
                                probability of
                                danger.
                              </small>
                            </div>
                          )}
                      </>
                    )}

                  {!selectionLoading
                    && selectedRisks.length
                      === 0 && (
                      <div className="empty-risks">
                        No hybrid risk
                        assessments were
                        recorded for this
                        vessel.
                      </div>
                    )}
                </section>

                <section className="anomaly-investigation">
                  <div className="anomaly-section-heading">
                    <div>
                      <h3>
                        Anomaly
                        investigation
                      </h3>

                      <span>
                        {
                          filteredAnomalies
                            .length
                        }{" "}
                        of{" "}
                        {
                          selectedAnomalies
                            .length
                        }{" "}
                        alerts
                      </span>
                    </div>
                  </div>

                  {!selectionLoading
                    && selectedAnomalies
                      .length > 0 && (
                      <>
                        <div className="anomaly-filters">
                          <label>
                            <span>
                              Severity
                            </span>

                            <select
                              value={
                                severityFilter
                              }
                              onChange={(
                                event,
                              ) => {
                                setSeverityFilter(
                                  event
                                    .target
                                    .value,
                                );

                                setSelectedAnomalyId(
                                  null,
                                );
                              }}
                            >
                              <option value="all">
                                All severities
                              </option>

                              <option value="critical">
                                Critical
                              </option>

                              <option value="high">
                                High
                              </option>

                              <option value="warning">
                                Warning
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
                              Type
                            </span>

                            <select
                              value={
                                anomalyTypeFilter
                              }
                              onChange={(
                                event,
                              ) => {
                                setAnomalyTypeFilter(
                                  event
                                    .target
                                    .value,
                                );

                                setSelectedAnomalyId(
                                  null,
                                );
                              }}
                            >
                              <option value="all">
                                All anomaly
                                types
                              </option>

                              {anomalyTypes.map(
                                (type) => (
                                  <option
                                    key={type}
                                    value={
                                      type
                                    }
                                  >
                                    {type.replaceAll(
                                      "_",
                                      " ",
                                    )}
                                  </option>
                                ),
                              )}
                            </select>
                          </label>
                        </div>

                        <div className="anomaly-list">
                          {filteredAnomalies.map(
                            (
                              anomaly,
                            ) => {
                              const isSelected =
                                anomaly.id
                                === selectedAnomalyId;

                              return (
                                <button
                                  key={
                                    anomaly.id
                                  }
                                  type="button"
                                  className={
                                    isSelected
                                      ? "anomaly-list-item selected"
                                      : "anomaly-list-item"
                                  }
                                  onClick={() =>
                                    handleSelectAnomaly(
                                      anomaly.id,
                                    )
                                  }
                                >
                                  <div className="anomaly-list-header">
                                    <strong>
                                      {anomaly
                                        .anomaly_type
                                        .replaceAll(
                                          "_",
                                          " ",
                                        )}
                                    </strong>

                                    <span
                                      className={
                                        `severity-badge severity-${anomaly.severity.toLowerCase()}`
                                      }
                                    >
                                      {
                                        anomaly
                                          .severity
                                      }
                                    </span>
                                  </div>

                                  <span className="anomaly-time">
                                    {formatTimestamp(
                                      anomaly
                                        .observed_at,
                                    )}
                                  </span>

                                  <span className="anomaly-message">
                                    {
                                      anomaly
                                        .message
                                    }
                                  </span>
                                </button>
                              );
                            },
                          )}

                          {filteredAnomalies
                            .length
                            === 0 && (
                              <div className="empty-anomalies">
                                No anomalies
                                match these
                                filters.
                              </div>
                            )}
                        </div>

                        {selectedAnomaly
                          !== null && (
                            <div className="selected-anomaly-details">
                              <div className="selected-anomaly-heading">
                                <strong>
                                  {selectedAnomaly
                                    .anomaly_type
                                    .replaceAll(
                                      "_",
                                      " ",
                                    )}
                                </strong>

                                <span
                                  className={
                                    `severity-badge severity-${selectedAnomaly.severity.toLowerCase()}`
                                  }
                                >
                                  {
                                    selectedAnomaly
                                      .severity
                                  }
                                </span>
                              </div>

                              <dl>
                                <dt>
                                  Observed
                                </dt>

                                <dd>
                                  {formatTimestamp(
                                    selectedAnomaly
                                      .observed_at,
                                  )}
                                </dd>

                                <dt>
                                  Metric
                                </dt>

                                <dd>
                                  {
                                    selectedAnomaly
                                      .metric_name
                                  }
                                </dd>

                                <dt>
                                  Value
                                </dt>

                                <dd>
                                  {
                                    selectedAnomaly
                                      .metric_value
                                    ?? "Not available"
                                  }
                                </dd>

                                <dt>
                                  Threshold
                                </dt>

                                <dd>
                                  {
                                    selectedAnomaly
                                      .threshold
                                    ?? "Not available"
                                  }
                                </dd>

                                <dt>
                                  Latitude
                                </dt>

                                <dd>
                                  {selectedAnomaly
                                    .latitude
                                    .toFixed(
                                      5,
                                    )}
                                </dd>

                                <dt>
                                  Longitude
                                </dt>

                                <dd>
                                  {selectedAnomaly
                                    .longitude
                                    .toFixed(
                                      5,
                                    )}
                                </dd>
                              </dl>

                              <p>
                                {
                                  selectedAnomaly
                                    .message
                                }
                              </p>
                            </div>
                          )}
                      </>
                    )}

                  {!selectionLoading
                    && selectedAnomalies
                      .length === 0 && (
                      <div className="empty-anomalies">
                        No anomaly alerts
                        were recorded for
                        this vessel.
                      </div>
                    )}
                </section>

                <dl className="details-list">
                  <dt>
                    Timestamp
                  </dt>

                  <dd>
                    {formatTimestamp(
                      selectedPosition
                        .timestamp,
                    )}
                  </dd>

                  <dt>
                    Latitude
                  </dt>

                  <dd>
                    {selectedPosition
                      .latitude
                      .toFixed(
                        5,
                      )}
                  </dd>

                  <dt>
                    Longitude
                  </dt>

                  <dd>
                    {selectedPosition
                      .longitude
                      .toFixed(
                        5,
                      )}
                  </dd>

                  <dt>
                    Speed over ground
                  </dt>

                  <dd>
                    {formatMeasurement(
                      selectedPosition.sog,
                      "kn",
                    )}
                  </dd>

                  <dt>
                    Course over ground
                  </dt>

                  <dd>
                    {formatMeasurement(
                      selectedPosition.cog,
                      "°",
                    )}
                  </dd>

                  <dt>
                    Heading
                  </dt>

                  <dd>
                    {formatMeasurement(
                      selectedPosition
                        .heading,
                      "°",
                    )}
                  </dd>

                  <dt>
                    Navigation status
                  </dt>

                  <dd>
                    {
                      selectedPosition
                        .navigation_status
                      ?? "Not available"
                    }
                  </dd>

                  <dt>
                    Vessel type code
                  </dt>

                  <dd>
                    {
                      selectedPosition
                        .vessel_type
                      ?? "Not available"
                    }
                  </dd>
                </dl>
              </div>
            )}
        </aside>
      </section>
    </main>
  );
}

export default App;