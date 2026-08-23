import type {
  CollisionEncounter,
  CollisionVesselState,
} from "../api/types";

interface VesselCollisionListProps {
  mmsi: string;
  encounters: CollisionEncounter[];
  loading: boolean;
  onSelectCollision: (
    collisionId: number,
  ) => void;
}

function vesselName(
  vessel: CollisionVesselState,
): string {
  return (
    vessel.name?.trim() ||
    `MMSI ${vessel.mmsi}`
  );
}

function counterpartFor(
  encounter: CollisionEncounter,
  mmsi: string,
): CollisionVesselState {
  return encounter.vessel_a.mmsi === mmsi
    ? encounter.vessel_b
    : encounter.vessel_a;
}

function formatDistance(
  value: number,
): string {
  return Number.isFinite(value)
    ? `${value.toFixed(3)} NM`
    : "Not available";
}

function formatTcpa(
  value: number | null,
): string {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "Not available";
  }

  if (value < 0) {
    return `${Math.abs(value).toFixed(1)} min ago`;
  }

  return `${value.toFixed(1)} min`;
}

function formatTimestamp(
  timestamp: string,
): string {
  const date = new Date(timestamp);

  return Number.isNaN(date.getTime())
    ? timestamp
    : date.toLocaleString();
}

export function VesselCollisionList({
  mmsi,
  encounters,
  loading,
  onSelectCollision,
}: VesselCollisionListProps) {
  return (
    <section className="vessel-collision-section">
      <div className="vessel-collision-heading">
        <div>
          <h3>Collision encounters</h3>

          <span>
            CPA/TCPA encounters involving
            this vessel.
          </span>
        </div>

        <strong className="vessel-collision-count">
          {encounters.length}
        </strong>
      </div>

      {loading ? (
        <div className="vessel-collision-empty">
          Loading collision encounters…
        </div>
      ) : encounters.length === 0 ? (
        <div className="vessel-collision-empty">
          No persisted collision encounters
          involve this vessel.
        </div>
      ) : (
        <div className="vessel-collision-list">
          {encounters.map(
            (encounter) => {
              const counterpart =
                counterpartFor(
                  encounter,
                  mmsi,
                );

              return (
                <button
                  key={encounter.id}
                  type="button"
                  className="vessel-collision-item"
                  onClick={() =>
                    onSelectCollision(
                      encounter.id,
                    )
                  }
                >
                  <div className="vessel-collision-item-header">
                    <div>
                      <strong>
                        {vesselName(
                          counterpart,
                        )}
                      </strong>

                      <span>
                        MMSI{" "}
                        {
                          counterpart.mmsi
                        }
                      </span>
                    </div>

                    <span
                      className={`risk-badge risk-${encounter.risk_level}`}
                    >
                      {
                        encounter.risk_level
                      }
                    </span>
                  </div>

                  <div className="vessel-collision-metrics">
                    <div>
                      <span>
                        Separation
                      </span>

                      <strong>
                        {formatDistance(
                          encounter.current_distance_nm,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>CPA</span>

                      <strong>
                        {formatDistance(
                          encounter.cpa_distance_nm,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>TCPA</span>

                      <strong>
                        {formatTcpa(
                          encounter.tcpa_minutes,
                        )}
                      </strong>
                    </div>
                  </div>

                  <div className="vessel-collision-footer">
                    <span>
                      {formatTimestamp(
                        encounter.observed_at,
                      )}
                    </span>

                    <strong>
                      Investigate →
                    </strong>
                  </div>
                </button>
              );
            },
          )}
        </div>
      )}

      <small className="vessel-collision-note">
        CPA/TCPA assumes constant course
        and speed. Priority levels are
        investigation heuristics, not
        collision probabilities.
      </small>
    </section>
  );
}