import { useCallback, useEffect, useMemo, useState } from "react";

import "./App.css";

import {
  fetchRecentPositions,
  fetchVesselAnomalies,
  fetchVesselTrajectory,
} from "./api/client";

import type { Anomaly, RecentPosition, VesselTrajectory } from "./api/types";

import { VesselMap } from "./components/VesselMap";

function formatMeasurement(value: number | null, unit: string): string {
  if (value === null || !Number.isFinite(value)) {
    return "Not available";
  }

  return `${value.toFixed(1)} ${unit}`;
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return date.toLocaleString();
}

function displayVesselName(position: RecentPosition): string {
  const name = position.vessel_name?.trim();

  return name || "Unknown vessel";
}

function App() {
  const [positions, setPositions] = useState<RecentPosition[]>([]);

  const [isLoading, setIsLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const [severityFilter, setSeverityFilter] = useState("all");

  const [anomalyTypeFilter, setAnomalyTypeFilter] = useState("all");

  const [selectedAnomalyId, setSelectedAnomalyId] = useState<number | null>(
    null,
  );

  const [searchQuery, setSearchQuery] = useState("");

  const [selectedMmsi, setSelectedMmsi] = useState<string | null>(null);

  const [selectedTrajectory, setSelectedTrajectory] =
    useState<VesselTrajectory | null>(null);

  const [selectedAnomalies, setSelectedAnomalies] = useState<Anomaly[]>([]);

  const [selectionLoading, setSelectionLoading] = useState(false);

  const [selectionError, setSelectionError] = useState<string | null>(null);

  const loadPositions = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchRecentPositions(500);

      setPositions(response.items);
    } catch (caughtError) {
      console.error("Failed to load positions:", caughtError);

      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "An unknown API error occurred.";

      setError(message);
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
      setSelectedAnomalyId(null);

      setSeverityFilter("all");
      setAnomalyTypeFilter("all");

      setSelectionError(null);
      setSelectionLoading(false);

      return;
    }

    const controller = new AbortController();

    const loadSelectedVessel = async () => {
      setSelectionLoading(true);
      setSelectionError(null);

      setSelectedTrajectory(null);
      setSelectedAnomalies([]);
      setSelectedAnomalyId(null);

      try {
        const [trajectory, anomalyResponse] = await Promise.all([
          fetchVesselTrajectory(selectedMmsi, controller.signal),

          fetchVesselAnomalies(selectedMmsi, controller.signal),
        ]);

        setSelectedTrajectory(trajectory);

        setSelectedAnomalies(anomalyResponse.items);
      } catch (caughtError) {
        if (
          caughtError instanceof DOMException &&
          caughtError.name === "AbortError"
        ) {
          return;
        }

        const message =
          caughtError instanceof Error
            ? caughtError.message
            : "Could not load vessel data.";

        setSelectionError(message);
      } finally {
        if (!controller.signal.aborted) {
          setSelectionLoading(false);
        }
      }
    };

    void loadSelectedVessel();

    return () => {
      controller.abort();
    };
  }, [selectedMmsi]);

  const filteredPositions = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    if (normalizedQuery === "") {
      return positions;
    }

    return positions.filter((position) => {
      const vesselName = position.vessel_name?.toLowerCase() ?? "";

      return (
        position.mmsi.includes(normalizedQuery) ||
        vesselName.includes(normalizedQuery)
      );
    });
  }, [positions, searchQuery]);

  const selectedPosition = useMemo(
    () => positions.find((position) => position.mmsi === selectedMmsi) ?? null,
    [positions, selectedMmsi],
  );
  const anomalyTypes = useMemo(() => {
    const types = new Set(
      selectedAnomalies.map((anomaly) => anomaly.anomaly_type),
    );

    return Array.from(types).sort();
  }, [selectedAnomalies]);

  const filteredAnomalies = useMemo(() => {
    return selectedAnomalies.filter((anomaly) => {
      const severityMatches =
        severityFilter === "all" ||
        anomaly.severity.toLowerCase() === severityFilter;

      const typeMatches =
        anomalyTypeFilter === "all" ||
        anomaly.anomaly_type === anomalyTypeFilter;

      return severityMatches && typeMatches;
    });
  }, [selectedAnomalies, severityFilter, anomalyTypeFilter]);

  const selectedAnomaly = useMemo(
    () =>
      selectedAnomalies.find((anomaly) => anomaly.id === selectedAnomalyId) ??
      null,
    [selectedAnomalies, selectedAnomalyId],
  );
  const movingVesselCount = useMemo(
    () =>
      positions.filter(
        (position) => position.sog !== null && position.sog >= 0.5,
      ).length,
    [positions],
  );

  const handleSelectVessel = useCallback((mmsi: string) => {
    setSelectedMmsi(mmsi);
  }, []);

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Maritime decision support</p>

          <h1>SeaGuard AI</h1>

          <p className="subtitle">
            Vessel monitoring and explainable AIS anomaly detection.
          </p>
        </div>

        <button
          type="button"
          className="refresh-button"
          onClick={() => void loadPositions()}
          disabled={isLoading}
        >
          {isLoading ? "Loading…" : "Refresh positions"}
        </button>
      </header>

      <section className="summary-grid" aria-label="Vessel position summary">
        <article className="summary-card">
          <span>Displayed vessels</span>
          <strong>{positions.length}</strong>
        </article>

        <article className="summary-card">
          <span>Moving vessels</span>
          <strong>{movingVesselCount}</strong>
        </article>

        <article className="summary-card">
          <span>API status</span>
          <strong>{error === null ? "Connected" : "Unavailable"}</strong>
        </article>
      </section>

      {error !== null && (
        <div className="error-banner" role="alert">
          <strong>Could not load vessel positions.</strong>

          <span>{error}</span>
        </div>
      )}

      <section className="workspace">
        <aside className="vessel-sidebar">
          <div className="panel-heading">
            <div>
              <h2>Vessels</h2>

              <p>Select a recent AIS position.</p>
            </div>
          </div>

          <label className="search-field" htmlFor="vessel-search">
            <span>Search vessel</span>

            <input
              id="vessel-search"
              type="search"
              value={searchQuery}
              placeholder="Name or MMSI"
              onChange={(event) => {
                setSearchQuery(event.target.value);
              }}
            />
          </label>

          <p className="result-count">
            {filteredPositions.length} result
            {filteredPositions.length === 1 ? "" : "s"}
          </p>

          <div className="vessel-list">
            {filteredPositions.map((position) => {
              const isSelected = selectedMmsi === position.mmsi;

              return (
                <button
                  key={position.mmsi}
                  type="button"
                  className={
                    isSelected
                      ? "vessel-list-item selected"
                      : "vessel-list-item"
                  }
                  onClick={() => {
                    handleSelectVessel(position.mmsi);
                  }}
                >
                  <span className="vessel-list-name">
                    {displayVesselName(position)}
                  </span>

                  <span className="vessel-list-mmsi">MMSI {position.mmsi}</span>

                  <span className="vessel-list-speed">
                    {formatMeasurement(position.sog, "kn")}
                  </span>
                </button>
              );
            })}

            {!isLoading && filteredPositions.length === 0 && (
              <div className="empty-list">No matching vessels found.</div>
            )}
          </div>
        </aside>

        <section className="map-panel">
          <div className="map-panel-header">
            <div>
              <h2>Vessel map</h2>

              <p>Click a marker to select its latest AIS report.</p>
            </div>
          </div>

          <VesselMap
            positions={positions}
            selectedMmsi={selectedMmsi}
            trajectory={selectedTrajectory}
            anomalies={selectedAnomalies}
            onSelectVessel={handleSelectVessel} selectedAnomalyId={null} onSelectAnomaly={function (): void {
              throw new Error("Function not implemented.");
            } }          />
        </section>

        <aside className="details-panel">
          <div className="panel-heading">
            <div>
              <h2>Vessel details</h2>

              <p>Latest imported AIS report.</p>
            </div>

            {selectedPosition !== null && (
              <button
                type="button"
                className="clear-selection"
                onClick={() => {
                  setSelectedMmsi(null);
                }}
              >
                Clear
              </button>
            )}
          </div>

          {selectedPosition === null ? (
            <div className="empty-details">
              Select a vessel from the map or vessel list.
            </div>
          ) : (
            <div className="vessel-details">
              <div className="selected-vessel-title">
                <span className="status-dot" />

                <div>
                  <strong>{displayVesselName(selectedPosition)}</strong>

                  <span>MMSI {selectedPosition.mmsi}</span>
                </div>
              </div>

              <div className="selected-data-summary">
                {selectionLoading ? (
                  <span>Loading trajectory and anomalies…</span>
                ) : selectionError !== null ? (
                  <span className="selection-error">{selectionError}</span>
                ) : (
                  <>
                    <div>
                      <span>Anomalies</span>
                      <strong>{selectedAnomalies.length}</strong>
                    </div>

                    <div>
                      <span>Trajectory</span>
                      <strong>
                        {selectedTrajectory === null ? "Unavailable" : "Loaded"}
                      </strong>
                    </div>
                  </>
                )}
              </div>

              <section className="anomaly-investigation">
                <div className="anomaly-section-heading">
                  <div>
                    <h3>Anomaly investigation</h3>

                    <span>
                      {filteredAnomalies.length} of {selectedAnomalies.length}{" "}
                      alerts
                    </span>
                  </div>
                </div>

                {!selectionLoading && selectedAnomalies.length > 0 && (
                  <>
                    <div className="anomaly-filters">
                      <label>
                        <span>Severity</span>

                        <select
                          value={severityFilter}
                          onChange={(event) => {
                            setSeverityFilter(event.target.value);
                            setSelectedAnomalyId(null);
                          }}
                        >
                          <option value="all">All severities</option>
                          <option value="critical">Critical</option>
                          <option value="high">High</option>
                          <option value="warning">Warning</option>
                          <option value="medium">Medium</option>
                          <option value="low">Low</option>
                        </select>
                      </label>

                      <label>
                        <span>Type</span>

                        <select
                          value={anomalyTypeFilter}
                          onChange={(event) => {
                            setAnomalyTypeFilter(event.target.value);
                            setSelectedAnomalyId(null);
                          }}
                        >
                          <option value="all">All anomaly types</option>

                          {anomalyTypes.map((type) => (
                            <option key={type} value={type}>
                              {type.replaceAll("_", " ")}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <div className="anomaly-list">
                      {filteredAnomalies.map((anomaly) => {
                        const isSelected = anomaly.id === selectedAnomalyId;

                        return (
                          <button
                            key={anomaly.id}
                            type="button"
                            className={
                              isSelected
                                ? "anomaly-list-item selected"
                                : "anomaly-list-item"
                            }
                            onClick={() => {
                              setSelectedAnomalyId(anomaly.id);
                            }}
                          >
                            <div className="anomaly-list-header">
                              <strong>
                                {anomaly.anomaly_type.replaceAll("_", " ")}
                              </strong>

                              <span
                                className={`severity-badge severity-${anomaly.severity.toLowerCase()}`}
                              >
                                {anomaly.severity}
                              </span>
                            </div>

                            <span className="anomaly-time">
                              {formatTimestamp(anomaly.observed_at)}
                            </span>

                            <span className="anomaly-message">
                              {anomaly.message}
                            </span>
                          </button>
                        );
                      })}

                      {filteredAnomalies.length === 0 && (
                        <div className="empty-anomalies">
                          No anomalies match these filters.
                        </div>
                      )}
                    </div>

                    {selectedAnomaly !== null && (
                      <div className="selected-anomaly-details">
                        <div className="selected-anomaly-heading">
                          <strong>
                            {selectedAnomaly.anomaly_type.replaceAll("_", " ")}
                          </strong>

                          <span
                            className={`severity-badge severity-${selectedAnomaly.severity.toLowerCase()}`}
                          >
                            {selectedAnomaly.severity}
                          </span>
                        </div>

                        <dl>
                          <dt>Observed</dt>
                          <dd>
                            {formatTimestamp(selectedAnomaly.observed_at)}
                          </dd>

                          <dt>Metric</dt>
                          <dd>{selectedAnomaly.metric_name}</dd>

                          <dt>Value</dt>
                          <dd>
                            {selectedAnomaly.metric_value ?? "Not available"}
                          </dd>

                          <dt>Threshold</dt>
                          <dd>
                            {selectedAnomaly.threshold ?? "Not available"}
                          </dd>

                          <dt>Latitude</dt>
                          <dd>{selectedAnomaly.latitude.toFixed(5)}</dd>

                          <dt>Longitude</dt>
                          <dd>{selectedAnomaly.longitude.toFixed(5)}</dd>
                        </dl>

                        <p>{selectedAnomaly.message}</p>
                      </div>
                    )}
                  </>
                )}

                {!selectionLoading && selectedAnomalies.length === 0 && (
                  <div className="empty-anomalies">
                    No anomaly alerts were recorded for this vessel.
                  </div>
                )}
              </section>

              <dl className="details-list">
                <dt>Timestamp</dt>
                <dd>{formatTimestamp(selectedPosition.timestamp)}</dd>

                <dt>Latitude</dt>
                <dd>{selectedPosition.latitude.toFixed(5)}</dd>

                <dt>Longitude</dt>
                <dd>{selectedPosition.longitude.toFixed(5)}</dd>

                <dt>Speed over ground</dt>
                <dd>{formatMeasurement(selectedPosition.sog, "kn")}</dd>

                <dt>Course over ground</dt>
                <dd>{formatMeasurement(selectedPosition.cog, "°")}</dd>

                <dt>Heading</dt>
                <dd>{formatMeasurement(selectedPosition.heading, "°")}</dd>

                <dt>Navigation status</dt>
                <dd>{selectedPosition.navigation_status ?? "Not available"}</dd>

                <dt>Vessel type code</dt>
                <dd>{selectedPosition.vessel_type ?? "Not available"}</dd>
              </dl>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

export default App;
