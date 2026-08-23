import type { CollisionEncounter } from "../api/types";

interface CollisionInvestigationProps {
  encounter: CollisionEncounter;
  onSelectVessel: (mmsi: string) => void;
}

function formatTimestamp(
  timestamp: string,
): string {
  const date = new Date(timestamp);

  return Number.isNaN(date.getTime())
    ? timestamp
    : date.toLocaleString();
}

function formatDistance(
  value: number,
): string {
  if (!Number.isFinite(value)) {
    return "Not available";
  }

  return `${value.toFixed(3)} NM`;
}

function formatSpeed(
  value: number | null,
): string {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "Not available";
  }

  return `${value.toFixed(1)} kn`;
}

function formatCourse(
  value: number | null,
): string {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "Not available";
  }

  return `${value.toFixed(1)}°`;
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

function displayVesselName(
  name: string | null,
): string {
  return name?.trim() || "Unknown vessel";
}

export function CollisionInvestigation({
  encounter,
  onSelectVessel,
}: CollisionInvestigationProps) {
  return (
    <section className="collision-investigation">
      <div className="collision-investigation-header">
        <div>
          <span className="collision-kicker">
            CPA/TCPA encounter
          </span>

          <h3>
            {displayVesselName(
              encounter.vessel_a.name,
            )}
            {" ↔ "}
            {displayVesselName(
              encounter.vessel_b.name,
            )}
          </h3>
        </div>

        <span
          className={`risk-badge risk-${encounter.risk_level}`}
        >
          {encounter.risk_level}
        </span>
      </div>

      <div className="collision-primary-metrics">
        <div>
          <span>Current separation</span>

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

        <div>
          <span>Closing speed</span>

          <strong>
            {formatSpeed(
              encounter.closing_speed_knots,
            )}
          </strong>
        </div>
      </div>

      <div className="collision-vessel-grid">
        <article className="collision-vessel-card">
          <div className="collision-vessel-heading">
            <div>
              <span>Vessel A</span>

              <strong>
                {displayVesselName(
                  encounter.vessel_a.name,
                )}
              </strong>

              <small>
                MMSI {encounter.vessel_a.mmsi}
              </small>
            </div>
          </div>

          <dl>
            <dt>Observed</dt>
            <dd>
              {formatTimestamp(
                encounter.vessel_a.observed_at,
              )}
            </dd>

            <dt>Latitude</dt>
            <dd>
              {encounter.vessel_a.latitude.toFixed(
                5,
              )}
            </dd>

            <dt>Longitude</dt>
            <dd>
              {encounter.vessel_a.longitude.toFixed(
                5,
              )}
            </dd>

            <dt>SOG</dt>
            <dd>
              {formatSpeed(
                encounter.vessel_a.sog,
              )}
            </dd>

            <dt>COG</dt>
            <dd>
              {formatCourse(
                encounter.vessel_a.cog,
              )}
            </dd>
          </dl>

          <button
            type="button"
            className="collision-vessel-button"
            onClick={() =>
              onSelectVessel(
                encounter.vessel_a.mmsi,
              )
            }
          >
            Investigate vessel
          </button>
        </article>

        <article className="collision-vessel-card">
          <div className="collision-vessel-heading">
            <div>
              <span>Vessel B</span>

              <strong>
                {displayVesselName(
                  encounter.vessel_b.name,
                )}
              </strong>

              <small>
                MMSI {encounter.vessel_b.mmsi}
              </small>
            </div>
          </div>

          <dl>
            <dt>Observed</dt>
            <dd>
              {formatTimestamp(
                encounter.vessel_b.observed_at,
              )}
            </dd>

            <dt>Latitude</dt>
            <dd>
              {encounter.vessel_b.latitude.toFixed(
                5,
              )}
            </dd>

            <dt>Longitude</dt>
            <dd>
              {encounter.vessel_b.longitude.toFixed(
                5,
              )}
            </dd>

            <dt>SOG</dt>
            <dd>
              {formatSpeed(
                encounter.vessel_b.sog,
              )}
            </dd>

            <dt>COG</dt>
            <dd>
              {formatCourse(
                encounter.vessel_b.cog,
              )}
            </dd>
          </dl>

          <button
            type="button"
            className="collision-vessel-button"
            onClick={() =>
              onSelectVessel(
                encounter.vessel_b.mmsi,
              )
            }
          >
            Investigate vessel
          </button>
        </article>
      </div>

      <section className="collision-geometry">
        <h4>Encounter geometry</h4>

        <dl>
          <dt>Current separation</dt>
          <dd>
            {formatDistance(
              encounter.current_distance_nm,
            )}
          </dd>

          <dt>Closest point of approach</dt>
          <dd>
            {formatDistance(
              encounter.cpa_distance_nm,
            )}
          </dd>

          <dt>Time to CPA</dt>
          <dd>
            {formatTcpa(
              encounter.tcpa_minutes,
            )}
          </dd>

          <dt>Relative speed</dt>
          <dd>
            {formatSpeed(
              encounter.relative_speed_knots,
            )}
          </dd>

          <dt>Closing speed</dt>
          <dd>
            {formatSpeed(
              encounter.closing_speed_knots,
            )}
          </dd>

          <dt>Bearing A → B</dt>
          <dd>
            {encounter.bearing_from_a_to_b_degrees.toFixed(
              1,
            )}
            °
          </dd>

          <dt>Encounter observed</dt>
          <dd>
            {formatTimestamp(
              encounter.observed_at,
            )}
          </dd>

          <dt>Assessment engine</dt>
          <dd>
            {encounter.assessment_version}
          </dd>
        </dl>
      </section>

      <section className="collision-reasons">
        <h4>Why SeaGuard flagged this encounter</h4>

        {encounter.reasons.length > 0 ? (
          <ul>
            {encounter.reasons.map(
              (reason, index) => (
                <li
                  key={`${encounter.id}-${index}`}
                >
                  {reason}
                </li>
              ),
            )}
          </ul>
        ) : (
          <p>
            The encounter exceeded the configured
            CPA/TCPA investigation thresholds.
          </p>
        )}
      </section>

      <small className="collision-disclaimer">
        CPA and TCPA are projections based on the
        vessels maintaining their observed course and
        speed. The priority level is an engineering
        investigation heuristic, not a probability of
        collision and not a COLREGS determination.
      </small>
    </section>
  );
}