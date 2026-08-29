import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import "./App.css";
import "./components/risk.css";
import "./components/collision.css";

import {
  fetchCollisionEncounters,
  fetchVesselCollisionEncounters,
} from "./api/collisions";

import {
  fetchRecentPositions,
  fetchVesselAnomalies,
  fetchVesselRiskAssessments,
  fetchVesselTrajectory,
} from "./api/client";

import type {
  Anomaly,
  CollisionEncounter,
  RecentPosition,
  RiskAssessment,
  RiskLevel,
  VesselTrajectory,
} from "./api/types";

import { LiveStatusBar } from "./components/LiveStatusBar";
import { CollisionInvestigation } from "./components/CollisionInvestigation";
import { CollisionQueue } from "./components/CollisionQueue";
import { PlaybackControls } from "./components/PlaybackControls";
import { RiskOverview } from "./components/RiskOverview";
import { VesselCollisionList } from "./components/VesselCollisionList";
import { VesselEventTimeline } from "./components/VesselEventTimeline";
import { VesselMap } from "./components/VesselMap";

import {
  buildRiskExplanation,
  formatEngineReasons,
} from "./utils/riskExplanation";

type RiskDisplayFilter =
  | "elevated"
  | "all"
  | RiskLevel;

const PLAYBACK_EVENT_WINDOW_MS =
  15 * 60 * 1000;

const LIVE_POSITION_POLL_MS =
  5_000;
/*
 * Structural representation of the trajectory
 * returned by the FastAPI backend.
 *
 * We keep the public VesselTrajectory type used
 * throughout the application while allowing the
 * playback layer to safely rebuild its geometry.
 */
interface PlaybackTrajectoryPoint {
  timestamp: string;
  latitude: number;
  longitude: number;
  [key: string]: unknown;
}

interface PlaybackTrajectoryShape {
  mmsi: string;
  point_count: number;
  start_time: string | null;
  end_time: string | null;

  geometry: {
    type: "Point" | "LineString";

    coordinates:
      | [number, number]
      | [number, number][];
  };

  points: PlaybackTrajectoryPoint[];

  [key: string]: unknown;
}

function formatMeasurement(
  value: number | null,
  unit: string,
): string {
  if (
    value === null ||
    !Number.isFinite(value)
  ) {
    return "Not available";
  }

  return `${value.toFixed(1)} ${unit}`;
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

function displayVesselName(
  position: RecentPosition,
): string {
  return (
    position.vessel_name?.trim() ||
    "Unknown vessel"
  );
}

/*
 * Prevent playback from showing the future
 * portion of a selected vessel's trajectory.
 *
 * Normal dashboard:
 *     full trajectory
 *
 * Historical playback:
 *     only points <= playback timestamp
 */
function clipTrajectoryToPlaybackTime(
  trajectory: VesselTrajectory | null,
  playbackTimeMs: number | null,
): VesselTrajectory | null {
  if (
    trajectory === null ||
    playbackTimeMs === null
  ) {
    return trajectory;
  }

  const source =
    trajectory as unknown as PlaybackTrajectoryShape;

  if (
    !Array.isArray(source.points)
  ) {
    /*
     * If a future backend version removes
     * timestamped trajectory points, hide the
     * trajectory rather than accidentally
     * exposing future movement.
     */
    return null;
  }

  const points =
    source.points.filter(
      (point) => {
        const timestamp =
          new Date(
            point.timestamp,
          ).getTime();

        return (
          Number.isFinite(
            timestamp,
          ) &&
          timestamp <=
            playbackTimeMs
        );
      },
    );

  const coordinates:
    [number, number][] =
    points
      .filter(
        (point) =>
          Number.isFinite(
            point.longitude,
          ) &&
          Number.isFinite(
            point.latitude,
          ),
      )
      .map(
        (point) => [
          point.longitude,
          point.latitude,
        ],
      );

  const geometry =
    coordinates.length === 1
      ? {
          type: "Point" as const,
          coordinates:
            coordinates[0],
        }
      : {
          type: "LineString" as const,
          coordinates,
        };

  const clipped = {
    ...source,

    point_count:
      points.length,

    start_time:
      points.length > 0
        ? points[0].timestamp
        : null,

    end_time:
      points.length > 0
        ? points[
            points.length - 1
          ].timestamp
        : null,

    geometry,

    points,
  };

  return clipped as unknown as VesselTrajectory;
}

function App() {
  const [
    collisionEncounters,
    setCollisionEncounters,
  ] =
    useState<
      CollisionEncounter[]
    >([]);

  const [
    selectedCollisionId,
    setSelectedCollisionId,
  ] =
    useState<number | null>(
      null,
    );

  const [
    collisionError,
    setCollisionError,
  ] =
    useState<string | null>(
      null,
    );

  const [
    positions,
    setPositions,
  ] =
    useState<
      RecentPosition[]
    >([]);

  const [
    isLoading,
    setIsLoading,
  ] =
    useState(true);

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null,
    );

  const [
    searchQuery,
    setSearchQuery,
  ] =
    useState("");

  const [
    selectedMmsi,
    setSelectedMmsi,
  ] =
    useState<string | null>(
      null,
    );

  const [
    selectedTrajectory,
    setSelectedTrajectory,
  ] =
    useState<
      VesselTrajectory | null
    >(null);

  const [
    selectedAnomalies,
    setSelectedAnomalies,
  ] =
    useState<Anomaly[]>(
      [],
    );

  const [
    selectedRisks,
    setSelectedRisks,
  ] =
    useState<
      RiskAssessment[]
    >([]);

  const [
    selectedVesselCollisions,
    setSelectedVesselCollisions,
  ] =
    useState<
      CollisionEncounter[]
    >([]);

  const [
    selectionLoading,
    setSelectionLoading,
  ] =
    useState(false);

  const [
    selectionError,
    setSelectionError,
  ] =
    useState<string | null>(
      null,
    );

  const [
    severityFilter,
    setSeverityFilter,
  ] =
    useState("all");

  const [
    anomalyTypeFilter,
    setAnomalyTypeFilter,
  ] =
    useState("all");

  const [
    selectedAnomalyId,
    setSelectedAnomalyId,
  ] =
    useState<number | null>(
      null,
    );

  const [
    riskLevelFilter,
    setRiskLevelFilter,
  ] =
    useState<RiskDisplayFilter>(
      "elevated",
    );

  const [
    selectedRiskId,
    setSelectedRiskId,
  ] =
    useState<number | null>(
      null,
    );

  const [
    playbackTime,
    setPlaybackTime,
  ] =
    useState<string | null>(
      null,
    );

  const pendingRiskIdRef =
    useRef<number | null>(
      null,
    );

  const loadPositions =
    useCallback(
      async () => {
        setIsLoading(
          true,
        );

        setError(
          null,
        );

        try {
          const response =
            await fetchRecentPositions(
              500,
            );

          setPositions(
            response.items,
          );
        } catch (
          caughtError
        ) {
          console.error(
            "Failed to load positions:",
            caughtError,
          );

          setError(
            caughtError instanceof
              Error
              ? caughtError.message
              : "An unknown API error occurred.",
          );
        } finally {
          setIsLoading(
            false,
          );
        }
      },
      [],
    );

  const loadCollisionEncounters =
    useCallback(
      async (
        signal?: AbortSignal,
      ) => {
        try {
          setCollisionError(
            null,
          );

          const response =
            await fetchCollisionEncounters(
              {
                limit: 500,
              },
              signal,
            );

          setCollisionEncounters(
            response.items,
          );
        } catch (
          caughtError
        ) {
          if (
            signal?.aborted
          ) {
            return;
          }

          console.error(
            "Failed to load collision encounters:",
            caughtError,
          );

          setCollisionError(
            caughtError instanceof
              Error
              ? caughtError.message
              : "Failed to load collision encounters.",
          );
        }
      },
      [],
    );

  useEffect(() => {
    void loadPositions();
  }, [
    loadPositions,
  ]);

  useEffect(() => {
    const controller =
      new AbortController();

    void loadCollisionEncounters(
      controller.signal,
    );

    return () => {
      controller.abort();
    };
  }, [
    loadCollisionEncounters,
  ]);

  /*
   * Keep the current dashboard synchronized
   * with newly ingested AIS data.
   *
   * Historical playback owns the map while
   * playbackTime is non-null, so live polling
   * is disabled in that mode.
   */
  useEffect(() => {
    if (
      playbackTime !== null
    ) {
      return;
    }

    let stopped = false;
    let requestInFlight = false;

    let collisionController:
      | AbortController
      | null = null;

    const pollLiveData =
      async () => {
        if (
          requestInFlight
        ) {
          return;
        }

        requestInFlight = true;

        collisionController =
          new AbortController();

        try {
          const positionPromise =
            fetchRecentPositions(
              500,
            );

          const collisionPromise =
            loadCollisionEncounters(
              collisionController
                .signal,
            );

          const response =
            await positionPromise;

          if (!stopped) {
            setPositions(
              response.items,
            );

            setError(
              null,
            );
          }

          await collisionPromise;
        } catch (
          caughtError
        ) {
          if (
            stopped ||
            collisionController
              ?.signal.aborted
          ) {
            return;
          }

          console.error(
            "Live position refresh failed:",
            caughtError,
          );

          setError(
            caughtError instanceof
              Error
              ? caughtError.message
              : "Live position refresh failed.",
          );
        } finally {
          requestInFlight =
            false;
        }
      };

    const interval =
      window.setInterval(
        () => {
          void pollLiveData();
        },
        LIVE_POSITION_POLL_MS,
      );

    return () => {
      stopped = true;

      window.clearInterval(
        interval,
      );

      collisionController?.abort();
    };
  }, [
    playbackTime,
    loadCollisionEncounters,
  ]);

  useEffect(() => {
    if (
      selectedMmsi === null
    ) {
      setSelectedTrajectory(
        null,
      );

      setSelectedAnomalies(
        [],
      );

      setSelectedRisks(
        [],
      );

      setSelectedVesselCollisions(
        [],
      );

      setSelectedAnomalyId(
        null,
      );

      setSelectedRiskId(
        null,
      );

      pendingRiskIdRef.current =
        null;

      setSeverityFilter(
        "all",
      );

      setAnomalyTypeFilter(
        "all",
      );

      setRiskLevelFilter(
        "elevated",
      );

      setSelectionError(
        null,
      );

      setSelectionLoading(
        false,
      );

      return;
    }

    const controller =
      new AbortController();

    const loadSelectedVessel =
      async () => {
        setSelectionLoading(
          true,
        );

        setSelectionError(
          null,
        );

        setSelectedTrajectory(
          null,
        );

        setSelectedAnomalies(
          [],
        );

        setSelectedRisks(
          [],
        );

        setSelectedVesselCollisions(
          [],
        );

        setSelectedAnomalyId(
          null,
        );

        setSelectedRiskId(
          null,
        );

        try {
          const [
            trajectory,
            anomalyResponse,
            riskResponse,
            collisionResponse,
          ] =
            await Promise.all([
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

              fetchVesselCollisionEncounters(
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

          setSelectedVesselCollisions(
            collisionResponse.items,
          );

          const pendingRiskId =
            pendingRiskIdRef.current;

          if (
            pendingRiskId !==
              null &&
            riskResponse.items.some(
              (
                assessment,
              ) =>
                assessment.id ===
                pendingRiskId,
            )
          ) {
            setSelectedRiskId(
              pendingRiskId,
            );

            pendingRiskIdRef.current =
              null;
          }
        } catch (
          caughtError
        ) {
          if (
            caughtError instanceof
              DOMException &&
            caughtError.name ===
              "AbortError"
          ) {
            return;
          }

          pendingRiskIdRef.current =
            null;

          setSelectionError(
            caughtError instanceof
              Error
              ? caughtError.message
              : "Could not load vessel data.",
          );
        } finally {
          if (
            !controller.signal
              .aborted
          ) {
            setSelectionLoading(
              false,
            );
          }
        }
      };

    void loadSelectedVessel();

    return () => {
      controller.abort();
    };
  }, [
    selectedMmsi,
  ]);

  /*
   * Silently keep the selected vessel investigation
   * synchronized while the dashboard is in live mode.
   *
   * The selectedMmsi effect above owns the initial load
   * and loading state. This background refresh keeps
   * already-visible data current without clearing the
   * panel or causing loading flicker every five seconds.
   */
  useEffect(() => {
    if (
      selectedMmsi === null ||
      playbackTime !== null
    ) {
      return;
    }

    let stopped = false;
    let requestInFlight = false;

    let controller:
      | AbortController
      | null = null;

    const refreshSelectedVessel =
      async () => {
        if (requestInFlight) {
          return;
        }

        requestInFlight = true;
        controller =
          new AbortController();

        try {
          const [
            trajectory,
            anomalyResponse,
            riskResponse,
            collisionResponse,
          ] =
            await Promise.all([
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

              fetchVesselCollisionEncounters(
                selectedMmsi,
                controller.signal,
              ),
            ]);

          /*
           * Cleanup sets stopped before aborting.
           * That prevents a request that finishes during
           * a vessel change or playback transition from
           * replacing the newer UI state.
           */
          if (stopped) {
            return;
          }

          setSelectedTrajectory(
            trajectory,
          );

          setSelectedAnomalies(
            anomalyResponse.items,
          );

          setSelectedRisks(
            riskResponse.items,
          );

          setSelectedVesselCollisions(
            collisionResponse.items,
          );

          setSelectionError(
            null,
          );
        } catch (
          caughtError
        ) {
          if (
            stopped ||
            controller.signal.aborted
          ) {
            return;
          }

          /*
           * A transient background failure should not
           * erase investigation data that is already on
           * screen. The next polling cycle can recover.
           */
          console.error(
            "Failed to refresh selected vessel:",
            caughtError,
          );
        } finally {
          requestInFlight = false;
        }
      };

    const interval =
      window.setInterval(
        () => {
          void refreshSelectedVessel();
        },
        LIVE_POSITION_POLL_MS,
      );

    return () => {
      stopped = true;

      window.clearInterval(
        interval,
      );

      controller?.abort();
    };
  }, [
    selectedMmsi,
    playbackTime,
  ]);

  const playbackTimeMs =
    useMemo(() => {
      if (
        playbackTime === null
      ) {
        return null;
      }

      const value =
        new Date(
          playbackTime,
        ).getTime();

      return Number.isFinite(
        value,
      )
        ? value
        : null;
    }, [
      playbackTime,
    ]);

  const isInsidePlaybackWindow =
    useCallback(
      (
        timestamp: string,
      ) => {
        if (
          playbackTimeMs ===
          null
        ) {
          return true;
        }

        const eventTime =
          new Date(
            timestamp,
          ).getTime();

        if (
          !Number.isFinite(
            eventTime,
          )
        ) {
          return false;
        }

        return (
          eventTime <=
            playbackTimeMs &&
          eventTime >=
            playbackTimeMs -
              PLAYBACK_EVENT_WINDOW_MS
        );
      },
      [
        playbackTimeMs,
      ],
    );

  /*
   * Critical 7C-B change:
   * the selected trajectory can no
   * longer reveal future movement.
   */
  const playbackTrajectory =
    useMemo(
      () =>
        clipTrajectoryToPlaybackTime(
          selectedTrajectory,
          playbackTimeMs,
        ),
      [
        selectedTrajectory,
        playbackTimeMs,
      ],
    );

  const filteredPositions =
    useMemo(() => {
      const query =
        searchQuery
          .trim()
          .toLowerCase();

      if (
        !query
      ) {
        return positions;
      }

      return positions.filter(
        (
          position,
        ) => {
          const vesselName =
            position.vessel_name
              ?.toLowerCase() ??
            "";

          return (
            position.mmsi.includes(
              query,
            ) ||
            vesselName.includes(
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
          (
            position,
          ) =>
            position.mmsi ===
            selectedMmsi,
        ) ?? null,
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
              (
                item,
              ) =>
                item.anomaly_type,
            ),
          ),
        ).sort(),
      [
        selectedAnomalies,
      ],
    );

  const filteredAnomalies =
    useMemo(
      () =>
        selectedAnomalies.filter(
          (
            anomaly,
          ) => {
            if (
              !isInsidePlaybackWindow(
                anomaly.observed_at,
              )
            ) {
              return false;
            }

            const severityMatches =
              severityFilter ===
                "all" ||
              anomaly.severity.toLowerCase() ===
                severityFilter;

            const typeMatches =
              anomalyTypeFilter ===
                "all" ||
              anomaly.anomaly_type ===
                anomalyTypeFilter;

            return (
              severityMatches &&
              typeMatches
            );
          },
        ),
      [
        selectedAnomalies,
        severityFilter,
        anomalyTypeFilter,
        isInsidePlaybackWindow,
      ],
    );

  const filteredRisks =
    useMemo(
      () =>
        selectedRisks.filter(
          (
            assessment,
          ) => {
            if (
              !isInsidePlaybackWindow(
                assessment.observed_at,
              )
            ) {
              return false;
            }

            if (
              riskLevelFilter ===
              "all"
            ) {
              return true;
            }

            if (
              riskLevelFilter ===
              "elevated"
            ) {
              return (
                assessment.risk_level !==
                "low"
              );
            }

            return (
              assessment.risk_level ===
              riskLevelFilter
            );
          },
        ),
      [
        selectedRisks,
        riskLevelFilter,
        isInsidePlaybackWindow,
      ],
    );

  const playbackCollisionEncounters =
    useMemo(
      () =>
        collisionEncounters.filter(
          (
            encounter,
          ) =>
            isInsidePlaybackWindow(
              encounter.observed_at,
            ),
        ),
      [
        collisionEncounters,
        isInsidePlaybackWindow,
      ],
    );

  const playbackVesselCollisions =
    useMemo(
      () =>
        selectedVesselCollisions.filter(
          (
            encounter,
          ) =>
            isInsidePlaybackWindow(
              encounter.observed_at,
            ),
        ),
      [
        selectedVesselCollisions,
        isInsidePlaybackWindow,
      ],
    );

  const selectedAnomaly =
    useMemo(
      () =>
        filteredAnomalies.find(
          (
            item,
          ) =>
            item.id ===
            selectedAnomalyId,
        ) ?? null,
      [
        filteredAnomalies,
        selectedAnomalyId,
      ],
    );

  const selectedRisk =
    useMemo(
      () =>
        filteredRisks.find(
          (
            item,
          ) =>
            item.id ===
            selectedRiskId,
        ) ?? null,
      [
        filteredRisks,
        selectedRiskId,
      ],
    );

  const selectedCollision =
    useMemo(
      () =>
        playbackCollisionEncounters.find(
          (
            encounter,
          ) =>
            encounter.id ===
            selectedCollisionId,
        ) ?? null,
      [
        playbackCollisionEncounters,
        selectedCollisionId,
      ],
    );

  const selectedRiskReasons =
    useMemo(
      () =>
        selectedRisk ===
        null
          ? []
          : formatEngineReasons(
              selectedRisk
                .risk_reasons,
            ),
      [
        selectedRisk,
      ],
    );

  const movingVesselCount =
    useMemo(
      () =>
        positions.filter(
          (
            position,
          ) =>
            position.sog !==
              null &&
            position.sog >=
              0.5,
        ).length,
      [
        positions,
      ],
    );

  const elevatedRiskCount =
    useMemo(
      () =>
        filteredRisks.filter(
          (
            assessment,
          ) =>
            assessment.risk_level !==
            "low",
        ).length,
      [
        filteredRisks,
      ],
    );

  const handleSelectVessel =
    useCallback(
      (
        mmsi: string,
      ) => {
        pendingRiskIdRef.current =
          null;

        setSelectedCollisionId(
          null,
        );

        setSelectedMmsi(
          mmsi,
        );
      },
      [],
    );

  const handleSelectAnomaly =
    useCallback(
      (
        anomalyId: number,
      ) => {
        pendingRiskIdRef.current =
          null;

        setSelectedCollisionId(
          null,
        );

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
      (
        riskId: number,
      ) => {
        pendingRiskIdRef.current =
          null;

        setSelectedCollisionId(
          null,
        );

        setSelectedRiskId(
          riskId,
        );

        setSelectedAnomalyId(
          null,
        );
      },
      [],
    );

  const handleSelectCollision =
    useCallback(
      (
        collisionId: number,
      ) => {
        const encounter =
          playbackCollisionEncounters.find(
            (
              item,
            ) =>
              item.id ===
              collisionId,
          );

        if (
          !encounter
        ) {
          return;
        }

        pendingRiskIdRef.current =
          null;

        setSelectedMmsi(
          null,
        );

        setSelectedRiskId(
          null,
        );

        setSelectedAnomalyId(
          null,
        );

        setSelectedCollisionId(
          collisionId,
        );
      },
      [
        playbackCollisionEncounters,
      ],
    );

  const handleSelectGlobalRisk =
    useCallback(
      (
        assessment:
          RiskAssessment,
      ) => {
        setSelectedCollisionId(
          null,
        );

        setRiskLevelFilter(
          assessment.risk_level,
        );

        setSelectedAnomalyId(
          null,
        );

        if (
          assessment.mmsi ===
          selectedMmsi
        ) {
          pendingRiskIdRef.current =
            null;

          setSelectedRiskId(
            assessment.id,
          );

          return;
        }

        pendingRiskIdRef.current =
          assessment.id;

        setSelectedMmsi(
          assessment.mmsi,
        );
      },
      [
        selectedMmsi,
      ],
    );

  const handleRefresh =
    useCallback(
      () => {
        setPlaybackTime(
          null,
        );

        setSelectedAnomalyId(
          null,
        );

        setSelectedRiskId(
          null,
        );

        setSelectedCollisionId(
          null,
        );

        void loadPositions();

        void loadCollisionEncounters();
      },
      [
        loadPositions,
        loadCollisionEncounters,
      ],
    );

  const handlePlaybackFrame =
    useCallback(
      (
        framePositions:
          RecentPosition[],
        requestedAt:
          string,
      ) => {
        setPlaybackTime(
          requestedAt,
        );

        pendingRiskIdRef.current =
          null;

        setSelectedMmsi(
          (
            currentMmsi,
          ) => {
            if (
              currentMmsi ===
              null
            ) {
              return null;
            }

            const stillVisible =
              framePositions.some(
                (
                  position,
                ) =>
                  position.mmsi ===
                  currentMmsi,
              );

            return stillVisible
              ? currentMmsi
              : null;
          },
        );

        setSelectedAnomalyId(
          null,
        );

        setSelectedRiskId(
          null,
        );

        setSelectedCollisionId(
          null,
        );

        setPositions(
          framePositions,
        );
      },
      [],
    );

  const handleExitPlayback =
    useCallback(
      () => {
        setPlaybackTime(
          null,
        );

        setSelectedAnomalyId(
          null,
        );

        setSelectedRiskId(
          null,
        );

        setSelectedCollisionId(
          null,
        );

        void loadPositions();
      },
      [
        loadPositions,
      ],
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
            detection, hybrid
            investigation priority, and
            CPA/TCPA collision analysis.
          </p>
        </div>

        <button
          type="button"
          className="refresh-button"
          onClick={
            handleRefresh
          }
          disabled={
            isLoading
          }
        >
          {isLoading
            ? "Loading…"
            : "Refresh positions"}
        </button>
      </header>

      <LiveStatusBar
        historical={
          playbackTime !== null
        }
      />

      <section
        className="summary-grid"
        aria-label="Vessel position summary"
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
            Collision encounters
          </span>

          <strong>
            {
              playbackCollisionEncounters.length
            }
          </strong>
        </article>

        <article className="summary-card">
          <span>
            Dashboard mode
          </span>

          <strong>
            {playbackTime !==
            null
              ? "Historical"
              : error === null
                ? "Current"
                : "Unavailable"}
          </strong>
        </article>
      </section>

      <PlaybackControls
        onFrameChange={
          handlePlaybackFrame
        }
        onExitPlayback={
          handleExitPlayback
        }
      />

      {/*
       * The current global RiskOverview
       * queries the complete persisted
       * risk dataset.
       *
       * Hide it during replay rather than
       * expose events from the future.
       */}
      {playbackTime ===
        null && (
        <RiskOverview
          onSelectRisk={
            handleSelectGlobalRisk
          }
        />
      )}

      <CollisionQueue
        encounters={
          playbackCollisionEncounters
        }
        selectedCollisionId={
          selectedCollisionId
        }
        onSelectCollision={
          handleSelectCollision
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

      {collisionError !==
        null && (
        <div
          className="error-banner"
          role="alert"
        >
          <strong>
            Could not load collision
            encounters.
          </strong>

          <span>
            {collisionError}
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
                {playbackTime !==
                null
                  ? "Select a vessel from this historical frame."
                  : "Select a recent AIS position."}
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
              value={
                searchQuery
              }
              placeholder="Name or MMSI"
              onChange={(
                event,
              ) =>
                setSearchQuery(
                  event.target
                    .value,
                )
              }
            />
          </label>

          <p className="result-count">
            {
              filteredPositions.length
            }{" "}
            result
            {filteredPositions.length ===
            1
              ? ""
              : "s"}
          </p>

          <div className="vessel-list">
            {filteredPositions.map(
              (
                position,
              ) => {
                const isSelected =
                  selectedMmsi ===
                  position.mmsi;

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
                      {
                        position.mmsi
                      }
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

            {!isLoading &&
              filteredPositions.length ===
                0 && (
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
                Click vessels,
                anomalies, risk
                markers, or collision
                encounter lines to
                investigate.
              </p>
            </div>
          </div>

          <VesselMap
            positions={
              positions
            }
            selectedMmsi={
              selectedMmsi
            }
            trajectory={
              playbackTrajectory
            }
            anomalies={
              filteredAnomalies
            }
            riskAssessments={
              filteredRisks
            }
            collisionEncounters={
              playbackCollisionEncounters
            }
            selectedAnomalyId={
              selectedAnomalyId
            }
            selectedRiskId={
              selectedRiskId
            }
            selectedCollisionId={
              selectedCollisionId
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
            onSelectCollision={
              handleSelectCollision
            }
          />
        </section>

        <aside className="details-panel">
          <div className="panel-heading">
            <div>
              <h2>
                {selectedCollision !==
                null
                  ? "Collision investigation"
                  : "Vessel details"}
              </h2>

              <p>
                {selectedCollision !==
                null
                  ? "CPA/TCPA encounter analysis."
                  : playbackTime !==
                      null
                    ? "Historical AIS report."
                    : "Latest imported AIS report."}
              </p>
            </div>

            {(selectedPosition !==
              null ||
              selectedCollision !==
                null) && (
              <button
                type="button"
                className="clear-selection"
                onClick={() => {
                  pendingRiskIdRef.current =
                    null;

                  setSelectedCollisionId(
                    null,
                  );

                  setSelectedMmsi(
                    null,
                  );
                }}
              >
                Clear
              </button>
            )}
          </div>

          {selectedCollision !==
          null ? (
            <CollisionInvestigation
              encounter={
                selectedCollision
              }
              onSelectVessel={
                handleSelectVessel
              }
            />
          ) : selectedPosition ===
            null ? (
            <div className="empty-details">
              Select a vessel,
              collision encounter,
              anomaly, or risk
              observation to
              investigate.
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
                      selectedPosition.mmsi
                    }
                  </span>
                </div>
              </div>

              <div className="selected-data-summary risk-summary-grid">
                {selectionLoading ? (
                  <span>
                    Loading trajectory,
                    collisions,
                    anomalies, and
                    risk…
                  </span>
                ) : selectionError !==
                  null ? (
                  <span className="selection-error">
                    {
                      selectionError
                    }
                  </span>
                ) : (
                  <>
                    <div>
                      <span>
                        Anomalies
                      </span>

                      <strong>
                        {
                          filteredAnomalies.length
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
                        Collisions
                      </span>

                      <strong>
                        {
                          playbackVesselCollisions.length
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        Trajectory
                      </span>

                      <strong>
                        {playbackTrajectory ===
                        null
                          ? "Unavailable"
                          : "Loaded"}
                      </strong>
                    </div>
                  </>
                )}
              </div>

              <VesselCollisionList
                mmsi={
                  selectedPosition.mmsi
                }
                encounters={
                  playbackVesselCollisions
                }
                loading={
                  selectionLoading
                }
                onSelectCollision={
                  handleSelectCollision
                }
              />

              <VesselEventTimeline
                anomalies={
                  filteredAnomalies
                }
                risks={
                  filteredRisks
                }
                selectedAnomalyId={
                  selectedAnomalyId
                }
                selectedRiskId={
                  selectedRiskId
                }
                onSelectAnomaly={
                  handleSelectAnomaly
                }
                onSelectRisk={
                  handleSelectRisk
                }
              />

              <section className="risk-investigation">
                <div className="risk-section-heading">
                  <div>
                    <h3>
                      Hybrid investigation
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

                {!selectionLoading &&
                  selectedRisks.length >
                    0 && (
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
                                value ===
                                  "elevated" ||
                                value ===
                                  "all" ||
                                value ===
                                  "critical" ||
                                value ===
                                  "high" ||
                                value ===
                                  "medium" ||
                                value ===
                                  "low"
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
                              assessment.id ===
                              selectedRiskId;

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
                                      assessment.ml_anomaly_percentile,
                                    )}
                                  </strong>

                                  <span
                                    className={`risk-badge risk-${assessment.risk_level}`}
                                  >
                                    {
                                      assessment.risk_level
                                    }
                                  </span>
                                </div>

                                <span className="risk-time">
                                  {formatTimestamp(
                                    assessment.observed_at,
                                  )}
                                </span>

                                <span className="risk-evidence">
                                  {
                                    assessment.rule_flag_count
                                  }{" "}
                                  rule flag
                                  {assessment.rule_flag_count ===
                                  1
                                    ? ""
                                    : "s"}
                                  {" · "}
                                  {assessment.detector_agreement
                                    ? "detectors agree"
                                    : "single-source evidence"}
                                </span>
                              </button>
                            );
                          },
                        )}

                        {filteredRisks.length ===
                          0 && (
                          <div className="empty-risks">
                            No risk
                            assessments match
                            this playback
                            frame and filter.
                          </div>
                        )}
                      </div>

                      {selectedRisk !==
                        null && (
                        <div className="selected-risk-details">
                          <div className="selected-risk-heading">
                            <strong>
                              Investigation
                              priority
                            </strong>

                            <span
                              className={`risk-badge risk-${selectedRisk.risk_level}`}
                            >
                              {
                                selectedRisk.risk_level
                              }
                            </span>
                          </div>

                          <dl>
                            <dt>
                              Observed
                            </dt>

                            <dd>
                              {formatTimestamp(
                                selectedRisk.observed_at,
                              )}
                            </dd>

                            <dt>
                              ML percentile
                            </dt>

                            <dd>
                              {formatPercentile(
                                selectedRisk.ml_anomaly_percentile,
                              )}
                            </dd>

                            <dt>
                              ML score
                            </dt>

                            <dd>
                              {selectedRisk.ml_anomaly_score.toFixed(
                                6,
                              )}
                            </dd>

                            <dt>
                              Rule severity
                            </dt>

                            <dd>
                              {
                                selectedRisk.rule_severity
                              }
                            </dd>

                            <dt>
                              Rule flags
                            </dt>

                            <dd>
                              {
                                selectedRisk.rule_flag_count
                              }
                            </dd>

                            <dt>
                              Detector agreement
                            </dt>

                            <dd>
                              {selectedRisk.detector_agreement
                                ? "Yes"
                                : "No"}
                            </dd>

                            <dt>
                              Latitude
                            </dt>

                            <dd>
                              {selectedRisk.latitude.toFixed(
                                5,
                              )}
                            </dd>

                            <dt>
                              Longitude
                            </dt>

                            <dd>
                              {selectedRisk.longitude.toFixed(
                                5,
                              )}
                            </dd>

                            <dt>
                              Model
                            </dt>

                            <dd>
                              {
                                selectedRisk.assessment_version
                              }
                            </dd>
                          </dl>

                          <div className="risk-explanation">
                            <strong>
                              Why SeaGuard
                              flagged this
                            </strong>

                            <p>
                              {buildRiskExplanation(
                                selectedRisk,
                              )}
                            </p>
                          </div>

                          {selectedRiskReasons.length >
                            0 && (
                            <details className="risk-engine-notes">
                              <summary>
                                Detection
                                engine notes
                              </summary>

                              <ul>
                                {selectedRiskReasons.map(
                                  (
                                    reason,
                                    index,
                                  ) => (
                                    <li
                                      key={`${reason}-${index}`}
                                    >
                                      {
                                        reason
                                      }
                                    </li>
                                  ),
                                )}
                              </ul>
                            </details>
                          )}

                          <small className="risk-disclaimer">
                            Investigation
                            priority ranks
                            observations for
                            review. It is not
                            the probability
                            that a vessel is
                            dangerous or
                            involved in
                            wrongdoing.
                          </small>
                        </div>
                      )}
                    </>
                  )}

                {!selectionLoading &&
                  selectedRisks.length ===
                    0 && (
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
                        filteredAnomalies.length
                      }{" "}
                      of{" "}
                      {
                        selectedAnomalies.length
                      }{" "}
                      alerts
                    </span>
                  </div>
                </div>

                {!selectionLoading &&
                  selectedAnomalies.length >
                    0 && (
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
                              All anomaly types
                            </option>

                            {anomalyTypes.map(
                              (
                                type,
                              ) => (
                                <option
                                  key={
                                    type
                                  }
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
                              anomaly.id ===
                              selectedAnomalyId;

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
                                    {anomaly.anomaly_type.replaceAll(
                                      "_",
                                      " ",
                                    )}
                                  </strong>

                                  <span
                                    className={`severity-badge severity-${anomaly.severity.toLowerCase()}`}
                                  >
                                    {
                                      anomaly.severity
                                    }
                                  </span>
                                </div>

                                <span className="anomaly-time">
                                  {formatTimestamp(
                                    anomaly.observed_at,
                                  )}
                                </span>

                                <span className="anomaly-message">
                                  {
                                    anomaly.message
                                  }
                                </span>
                              </button>
                            );
                          },
                        )}

                        {filteredAnomalies.length ===
                          0 && (
                          <div className="empty-anomalies">
                            No anomalies
                            match this
                            playback frame
                            and filter.
                          </div>
                        )}
                      </div>

                      {selectedAnomaly !==
                        null && (
                        <div className="selected-anomaly-details">
                          <div className="selected-anomaly-heading">
                            <strong>
                              {selectedAnomaly.anomaly_type.replaceAll(
                                "_",
                                " ",
                              )}
                            </strong>

                            <span
                              className={`severity-badge severity-${selectedAnomaly.severity.toLowerCase()}`}
                            >
                              {
                                selectedAnomaly.severity
                              }
                            </span>
                          </div>

                          <dl>
                            <dt>
                              Observed
                            </dt>

                            <dd>
                              {formatTimestamp(
                                selectedAnomaly.observed_at,
                              )}
                            </dd>

                            <dt>
                              Metric
                            </dt>

                            <dd>
                              {
                                selectedAnomaly.metric_name
                              }
                            </dd>

                            <dt>
                              Value
                            </dt>

                            <dd>
                              {selectedAnomaly.metric_value ??
                                "Not available"}
                            </dd>

                            <dt>
                              Threshold
                            </dt>

                            <dd>
                              {selectedAnomaly.threshold ??
                                "Not available"}
                            </dd>

                            <dt>
                              Latitude
                            </dt>

                            <dd>
                              {selectedAnomaly.latitude.toFixed(
                                5,
                              )}
                            </dd>

                            <dt>
                              Longitude
                            </dt>

                            <dd>
                              {selectedAnomaly.longitude.toFixed(
                                5,
                              )}
                            </dd>
                          </dl>

                          <p>
                            {
                              selectedAnomaly.message
                            }
                          </p>
                        </div>
                      )}
                    </>
                  )}

                {!selectionLoading &&
                  selectedAnomalies.length ===
                    0 && (
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
                    selectedPosition.timestamp,
                  )}
                </dd>

                <dt>
                  Latitude
                </dt>

                <dd>
                  {selectedPosition.latitude.toFixed(
                    5,
                  )}
                </dd>

                <dt>
                  Longitude
                </dt>

                <dd>
                  {selectedPosition.longitude.toFixed(
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
                    selectedPosition.heading,
                    "°",
                  )}
                </dd>

                <dt>
                  Navigation status
                </dt>

                <dd>
                  {selectedPosition.navigation_status ??
                    "Not available"}
                </dd>

                <dt>
                  Vessel type code
                </dt>

                <dd>
                  {selectedPosition.vessel_type ??
                    "Not available"}
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