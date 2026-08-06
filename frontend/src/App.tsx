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
    void loadPositions();
  }, [loadPositions]);


  const movingVesselCount = useMemo(
    () => positions.filter(
      (position) =>
        position.sog !== null
        && position.sog >= 0.5,
    ).length,
    [positions],
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
            Recent vessel positions from the
            SeaGuard PostGIS database.
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

      <section className="map-panel">
        <div className="map-panel-header">
          <div>
            <h2>Vessel map</h2>
            <p>
              Click a marker to inspect its
              latest AIS report.
            </p>
          </div>
        </div>

        <VesselMap positions={positions} />
      </section>
    </main>
  );
}

export default App;