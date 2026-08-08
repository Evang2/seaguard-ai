import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import "./App.css";

import {
  fetchRecentPositions,
} from "./api/client";

import type {
  RecentPosition,
} from "./api/types";

import {
  VesselMap,
} from "./components/VesselMap";


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

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return date.toLocaleString();
}


function displayVesselName(
  position: RecentPosition,
): string {
  const name = position.vessel_name?.trim();

  return name || "Unknown vessel";
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


  const loadPositions = useCallback(
    async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response =
          await fetchRecentPositions(500);

        setPositions(response.items);
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : "An unknown API error occurred.";

        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );


  useEffect(() => {
    const controller =
      new AbortController();

    const loadInitialPositions =
      async () => {
        setIsLoading(true);
        setError(null);

        try {
          const response =
            await fetchRecentPositions(
              500,
              controller.signal,
            );

          setPositions(response.items);
        } catch (caughtError) {
          if (
            caughtError instanceof DOMException
            && caughtError.name
              === "AbortError"
          ) {
            return;
          }

          const message =
            caughtError instanceof Error
              ? caughtError.message
              : "An unknown API error occurred.";

          setError(message);
        } finally {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        }
      };

    void loadInitialPositions();

    return () => {
      controller.abort();
    };
  }, []);


  const filteredPositions = useMemo(
    () => {
      const normalizedQuery =
        searchQuery.trim().toLowerCase();

      if (normalizedQuery === "") {
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
              normalizedQuery,
            )
            || vesselName.includes(
              normalizedQuery,
            )
          );
        },
      );
    },
    [
      positions,
      searchQuery,
    ],
  );


  const selectedPosition = useMemo(
    () => positions.find(
      (position) =>
        position.mmsi === selectedMmsi,
    ) ?? null,
    [
      positions,
      selectedMmsi,
    ],
  );


  const movingVesselCount = useMemo(
    () => positions.filter(
      (position) =>
        position.sog !== null
        && position.sog >= 0.5,
    ).length,
    [positions],
  );


  const handleSelectVessel = useCallback(
    (mmsi: string) => {
      setSelectedMmsi(mmsi);
    },
    [],
  );


  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">
            Maritime decision support
          </p>

          <h1>SeaGuard AI</h1>

          <p className="subtitle">
            Vessel monitoring and explainable
            AIS anomaly detection.
          </p>
        </div>

        <button
          type="button"
          className="refresh-button"
          onClick={() => void loadPositions()}
          disabled={isLoading}
        >
          {isLoading
            ? "Loading…"
            : "Refresh positions"}
        </button>
      </header>


      <section
        className="summary-grid"
        aria-label="Vessel position summary"
      >
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
          <strong>
            {error === null
              ? "Connected"
              : "Unavailable"}
          </strong>
        </article>
      </section>


      {error !== null && (
        <div
          className="error-banner"
          role="alert"
        >
          <strong>
            Could not load vessel positions.
          </strong>

          <span>{error}</span>
        </div>
      )}


      <section className="workspace">
        <aside className="vessel-sidebar">
          <div className="panel-heading">
            <div>
              <h2>Vessels</h2>

              <p>
                Select a recent AIS position.
              </p>
            </div>
          </div>


          <label
            className="search-field"
            htmlFor="vessel-search"
          >
            <span>Search vessel</span>

            <input
              id="vessel-search"
              type="search"
              value={searchQuery}
              placeholder="Name or MMSI"
              onChange={(event) => {
                setSearchQuery(
                  event.target.value,
                );
              }}
            />
          </label>


          <p className="result-count">
            {filteredPositions.length}
            {" "}
            result
            {filteredPositions.length === 1
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
                    key={position.mmsi}
                    type="button"
                    className={
                      isSelected
                        ? "vessel-list-item selected"
                        : "vessel-list-item"
                    }
                    onClick={() => {
                      handleSelectVessel(
                        position.mmsi,
                      );
                    }}
                  >
                    <span className="vessel-list-name">
                      {displayVesselName(
                        position,
                      )}
                    </span>

                    <span className="vessel-list-mmsi">
                      MMSI {position.mmsi}
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
              && filteredPositions.length === 0
              && (
                <div className="empty-list">
                  No matching vessels found.
                </div>
              )}
          </div>
        </aside>


        <section className="map-panel">
          <div className="map-panel-header">
            <div>
              <h2>Vessel map</h2>

              <p>
                Click a marker to select its
                latest AIS report.
              </p>
            </div>
          </div>

          <VesselMap
            positions={positions}
            selectedMmsi={selectedMmsi}
            onSelectVessel={
              handleSelectVessel
            }
          />
        </section>


        <aside className="details-panel">
          <div className="panel-heading">
            <div>
              <h2>Vessel details</h2>

              <p>
                Latest imported AIS report.
              </p>
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
              Select a vessel from the map or
              vessel list.
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
                    MMSI {selectedPosition.mmsi}
                  </span>
                </div>
              </div>


              <dl className="details-list">
                <dt>Timestamp</dt>
                <dd>
                  {formatTimestamp(
                    selectedPosition.timestamp,
                  )}
                </dd>

                <dt>Latitude</dt>
                <dd>
                  {selectedPosition.latitude
                    .toFixed(5)}
                </dd>

                <dt>Longitude</dt>
                <dd>
                  {selectedPosition.longitude
                    .toFixed(5)}
                </dd>

                <dt>Speed over ground</dt>
                <dd>
                  {formatMeasurement(
                    selectedPosition.sog,
                    "kn",
                  )}
                </dd>

                <dt>Course over ground</dt>
                <dd>
                  {formatMeasurement(
                    selectedPosition.cog,
                    "°",
                  )}
                </dd>

                <dt>Heading</dt>
                <dd>
                  {formatMeasurement(
                    selectedPosition.heading,
                    "°",
                  )}
                </dd>

                <dt>Navigation status</dt>
                <dd>
                  {selectedPosition
                    .navigation_status
                    ?? "Not available"}
                </dd>

                <dt>Vessel type code</dt>
                <dd>
                  {selectedPosition.vessel_type
                    ?? "Not available"}
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