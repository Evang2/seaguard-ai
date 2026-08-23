import {
  useMemo,
  useState,
} from "react";

import type {
  CollisionEncounter,
  CollisionRiskLevel,
} from "../api/types";

import "./collision-queue.css";


type CollisionQueueFilter =
  | "all"
  | CollisionRiskLevel;


interface CollisionQueueProps {
  encounters: CollisionEncounter[];
  selectedCollisionId: number | null;
  onSelectCollision: (
    collisionId: number,
  ) => void;
}


const RISK_ORDER: Record<
  CollisionRiskLevel,
  number
> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};


function vesselLabel(
  name: string | null,
  mmsi: string,
): string {
  return name?.trim() || `MMSI ${mmsi}`;
}


function formatDistance(
  value: number,
): string {
  return Number.isFinite(value)
    ? `${value.toFixed(3)} NM`
    : "N/A";
}


function formatTcpa(
  value: number | null,
): string {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "TCPA unavailable";
  }

  if (value < 0) {
    return `CPA passed ${Math.abs(value).toFixed(1)} min ago`;
  }

  return `TCPA ${value.toFixed(1)} min`;
}


function formatTimestamp(
  timestamp: string,
): string {
  const date = new Date(timestamp);

  return Number.isNaN(date.getTime())
    ? timestamp
    : date.toLocaleString();
}


export function CollisionQueue({
  encounters,
  selectedCollisionId,
  onSelectCollision,
}: CollisionQueueProps) {
  const [
    filter,
    setFilter,
  ] = useState<CollisionQueueFilter>(
    "all",
  );

  const filteredEncounters =
    useMemo(() => {
      const filtered =
        filter === "all"
          ? encounters
          : encounters.filter(
              (encounter) =>
                encounter.risk_level ===
                filter,
            );

      return [...filtered].sort(
        (left, right) => {
          const priorityDifference =
            RISK_ORDER[
              left.risk_level
            ] -
            RISK_ORDER[
              right.risk_level
            ];

          if (
            priorityDifference !== 0
          ) {
            return priorityDifference;
          }

          const leftTcpa =
            left.tcpa_minutes !== null &&
            left.tcpa_minutes >= 0
              ? left.tcpa_minutes
              : Number.POSITIVE_INFINITY;

          const rightTcpa =
            right.tcpa_minutes !== null &&
            right.tcpa_minutes >= 0
              ? right.tcpa_minutes
              : Number.POSITIVE_INFINITY;

          if (leftTcpa !== rightTcpa) {
            return leftTcpa - rightTcpa;
          }

          return (
            left.cpa_distance_nm -
            right.cpa_distance_nm
          );
        },
      );
    }, [
      encounters,
      filter,
    ]);

  return (
    <section className="collision-queue">
      <div className="risk-section-heading">
        <div>
          <h3>
            Collision investigation
            priority
          </h3>

          <span>
            {filteredEncounters.length} of{" "}
            {encounters.length} encounters
          </span>
        </div>
      </div>

      <div className="risk-filters">
        <label>
          <span>Priority</span>

          <select
            value={filter}
            onChange={(event) => {
              const value =
                event.target.value;

              if (
                value === "all" ||
                value === "critical" ||
                value === "high" ||
                value === "medium" ||
                value === "low"
              ) {
                setFilter(value);
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
      </div>

      <div className="collision-queue-list">
        {filteredEncounters.map(
          (encounter) => {
            const isSelected =
              encounter.id ===
              selectedCollisionId;

            return (
              <button
                key={encounter.id}
                type="button"
                className={
                  isSelected
                    ? "collision-queue-item selected"
                    : "collision-queue-item"
                }
                onClick={() =>
                  onSelectCollision(
                    encounter.id,
                  )
                }
              >
                <div className="collision-queue-item-header">
                  <strong>
                    {vesselLabel(
                      encounter.vessel_a
                        .name,
                      encounter.vessel_a
                        .mmsi,
                    )}
                    {" ↔ "}
                    {vesselLabel(
                      encounter.vessel_b
                        .name,
                      encounter.vessel_b
                        .mmsi,
                    )}
                  </strong>

                  <span
                    className={`risk-badge risk-${encounter.risk_level}`}
                  >
                    {
                      encounter.risk_level
                    }
                  </span>
                </div>

                <span className="collision-queue-time">
                  {formatTimestamp(
                    encounter.observed_at,
                  )}
                </span>

                <span className="collision-queue-evidence">
                  Separation{" "}
                  {formatDistance(
                    encounter.current_distance_nm,
                  )}
                  {" · "}
                  CPA{" "}
                  {formatDistance(
                    encounter.cpa_distance_nm,
                  )}
                  {" · "}
                  {formatTcpa(
                    encounter.tcpa_minutes,
                  )}
                </span>

                <span className="collision-queue-secondary">
                  Closing speed{" "}
                  {encounter.closing_speed_knots.toFixed(
                    1,
                  )}{" "}
                  kn
                  {" · "}
                  Relative speed{" "}
                  {encounter.relative_speed_knots.toFixed(
                    1,
                  )}{" "}
                  kn
                </span>
              </button>
            );
          },
        )}

        {filteredEncounters.length ===
          0 && (
          <div className="collision-queue-empty">
            No collision encounters
            match this filter.
          </div>
        )}
      </div>

      <small className="collision-queue-disclaimer">
        CPA/TCPA assumes constant course
        and speed. Priority levels rank
        encounters for investigation; they
        are not collision probabilities or
        COLREGS determinations.
      </small>
    </section>
  );
}