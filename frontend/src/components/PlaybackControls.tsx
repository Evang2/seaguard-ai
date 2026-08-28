import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  fetchPlaybackBounds,
  fetchPlaybackSnapshot,
} from "../api/playback";

import type {
  PlaybackBounds,
} from "../api/playback";

import type {
  RecentPosition,
} from "../api/types";

import "./playback.css";

type PlaybackSpeed =
  | 1
  | 4
  | 16
  | 60;

interface PlaybackControlsProps {
  onFrameChange: (
    positions: RecentPosition[],
    requestedAt: string,
  ) => void;

  onExitPlayback: () => void;
}

const FRAME_TOLERANCE_MINUTES = 5;

const BASE_STEP_MS = 60_000;

function formatPlaybackTimestamp(
  value: number | null,
): string {
  if (value === null) {
    return "—";
  }

  return (
    new Date(value).toLocaleString(
      undefined,
      {
        timeZone: "UTC",
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      },
    ) + " UTC"
  );
}

function formatClock(
  value: number,
): string {
  return new Date(
    value,
  ).toLocaleTimeString(
    undefined,
    {
      timeZone: "UTC",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    },
  );
}

export function PlaybackControls(
  props: PlaybackControlsProps,
) {
  const {
    onFrameChange,
    onExitPlayback,
  } = props;

  const [
    bounds,
    setBounds,
  ] =
    useState<PlaybackBounds | null>(
      null,
    );

  const [
    cursorMs,
    setCursorMs,
  ] =
    useState<number | null>(
      null,
    );

  const [
    isActive,
    setIsActive,
  ] =
    useState(false);

  const [
    isPlaying,
    setIsPlaying,
  ] =
    useState(false);

  const [
    speed,
    setSpeed,
  ] =
    useState<PlaybackSpeed>(
      4,
    );

  const [
    frameCount,
    setFrameCount,
  ] =
    useState(0);

  const [
    isFrameLoading,
    setIsFrameLoading,
  ] =
    useState(false);

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null,
    );

  const onFrameChangeRef =
    useRef(
      onFrameChange,
    );

  const onExitPlaybackRef =
    useRef(
      onExitPlayback,
    );

  const frameAbortRef =
    useRef<
      AbortController | null
    >(null);

  useEffect(() => {
    onFrameChangeRef.current =
      onFrameChange;
  }, [
    onFrameChange,
  ]);

  useEffect(() => {
    onExitPlaybackRef.current =
      onExitPlayback;
  }, [
    onExitPlayback,
  ]);

  useEffect(() => {
    const controller =
      new AbortController();

    const loadBounds =
      async () => {
        try {
          setError(
            null,
          );

          const response =
            await fetchPlaybackBounds(
              controller.signal,
            );

          setBounds(
            response,
          );
        } catch (
          caughtError
        ) {
          if (
            controller.signal
              .aborted
          ) {
            return;
          }

          setError(
            caughtError instanceof
              Error
              ? caughtError.message
              : "Could not load playback bounds.",
          );
        }
      };

    void loadBounds();

    return () => {
      controller.abort();
    };
  }, []);

  const startMs =
    useMemo(() => {
      if (
        bounds?.start_time ===
          null ||
        bounds?.start_time ===
          undefined
      ) {
        return null;
      }

      const value =
        new Date(
          bounds.start_time,
        ).getTime();

      return Number.isFinite(
        value,
      )
        ? value
        : null;
    }, [
      bounds,
    ]);

  const endMs =
    useMemo(() => {
      if (
        bounds?.end_time ===
          null ||
        bounds?.end_time ===
          undefined
      ) {
        return null;
      }

      const value =
        new Date(
          bounds.end_time,
        ).getTime();

      return Number.isFinite(
        value,
      )
        ? value
        : null;
    }, [
      bounds,
    ]);

  const durationSeconds =
    startMs !== null &&
    endMs !== null
      ? Math.max(
          0,
          Math.floor(
            (
              endMs -
              startMs
            ) /
              1000,
          ),
        )
      : 0;

  const sliderSeconds =
    startMs !== null &&
    cursorMs !== null
      ? Math.max(
          0,
          Math.min(
            durationSeconds,
            Math.floor(
              (
                cursorMs -
                startMs
              ) /
                1000,
            ),
          ),
        )
      : 0;

  /*
   * Fetch the AIS frame whenever
   * the playback cursor changes.
   */
  useEffect(() => {
    if (
      !isActive ||
      cursorMs === null
    ) {
      return;
    }

    const timeout =
      window.setTimeout(
        () => {
          frameAbortRef.current
            ?.abort();

          const controller =
            new AbortController();

          frameAbortRef.current =
            controller;

          const loadFrame =
            async () => {
              setIsFrameLoading(
                true,
              );

              setError(
                null,
              );

              try {
                const response =
                  await fetchPlaybackSnapshot(
                    new Date(
                      cursorMs,
                    ).toISOString(),
                    FRAME_TOLERANCE_MINUTES,
                    500,
                    controller.signal,
                  );

                /*
                 * Send both the vessel frame
                 * and the exact timestamp that
                 * produced it.
                 *
                 * App.tsx can now synchronize
                 * every investigation overlay
                 * to this exact frame.
                 */
                onFrameChangeRef.current(
                    response.items,
                    response.requested_at,
                  );

                setFrameCount(
                  response.total,
                );
              } catch (
                caughtError
              ) {
                if (
                  controller.signal
                    .aborted
                ) {
                  return;
                }

                setError(
                  caughtError instanceof
                    Error
                    ? caughtError.message
                    : "Could not load playback frame.",
                );
              } finally {
                if (
                  !controller.signal
                    .aborted
                ) {
                  setIsFrameLoading(
                    false,
                  );
                }
              }
            };

          void loadFrame();
        },
        120,
      );

    return () => {
      window.clearTimeout(
        timeout,
      );
    };
  }, [
    cursorMs,
    isActive,
  ]);

  /*
   * Playback clock.
   *
   * 1× means one simulated minute
   * every real second.
   */
  useEffect(() => {
    if (
      !isActive ||
      !isPlaying ||
      endMs === null
    ) {
      return;
    }

    const interval =
      window.setInterval(
        () => {
          setCursorMs(
            (
              previous,
            ) => {
              if (
                previous ===
                null
              ) {
                return previous;
              }

              const next =
                Math.min(
                  endMs,
                  previous +
                    BASE_STEP_MS *
                      speed,
                );

              if (
                next >= endMs
              ) {
                setIsPlaying(
                  false,
                );
              }

              return next;
            },
          );
        },
        1000,
      );

    return () => {
      window.clearInterval(
        interval,
      );
    };
  }, [
    isActive,
    isPlaying,
    speed,
    endMs,
  ]);

  useEffect(() => {
    return () => {
      frameAbortRef.current
        ?.abort();
    };
  }, []);

  const startPlayback =
    () => {
      if (
        startMs === null
      ) {
        return;
      }

      setIsPlaying(
        false,
      );

      setFrameCount(
        0,
      );

      setCursorMs(
        startMs,
      );

      setIsActive(
        true,
      );
    };

  const exitPlayback =
    () => {
      frameAbortRef.current
        ?.abort();

      setIsPlaying(
        false,
      );

      setIsActive(
        false,
      );

      setCursorMs(
        null,
      );

      setFrameCount(
        0,
      );

      setError(
        null,
      );

      onExitPlaybackRef
        .current();
    };

  const jumpToStart =
    () => {
      if (
        startMs === null
      ) {
        return;
      }

      setIsPlaying(
        false,
      );

      setCursorMs(
        startMs,
      );
    };

  const jumpToEnd =
    () => {
      if (
        endMs === null
      ) {
        return;
      }

      setIsPlaying(
        false,
      );

      setCursorMs(
        endMs,
      );
    };

  const togglePlayback =
    () => {
      if (
        cursorMs !== null &&
        startMs !== null &&
        endMs !== null &&
        cursorMs >= endMs
      ) {
        setCursorMs(
          startMs,
        );

        setIsPlaying(
          true,
        );

        return;
      }

      setIsPlaying(
        (
          previous,
        ) =>
          !previous,
      );
    };

  return (
    <section
      className="playback-panel"
      aria-label="Historical AIS playback"
    >
      <div className="playback-heading">
        <div>
          <p className="playback-eyebrow">
            Historical AIS playback
          </p>

          <h2>
            Replay vessel traffic
          </h2>

          <p>
            Scrub through the imported
            AIS recording using fresh
            vessel reports from each
            frame.
          </p>
        </div>

        <div className="playback-status">
          <span
            className={
              isActive
                ? "playback-mode active"
                : "playback-mode"
            }
          >
            {isActive
              ? "Playback"
              : "Ready"}
          </span>

          {isActive && (
            <span>
              {isFrameLoading
                ? "Loading frame…"
                : `${frameCount} vessels`}
            </span>
          )}
        </div>
      </div>

      {bounds !== null && (
        <div className="playback-dataset">
          <span>
            {bounds
              .observation_count
              .toLocaleString()}
            {" "}
            AIS reports
          </span>

          <span>
            {bounds
              .vessel_count
              .toLocaleString()}
            {" "}
            vessels
          </span>

          <span>
            {formatPlaybackTimestamp(
              startMs,
            )}

            {" → "}

            {formatPlaybackTimestamp(
              endMs,
            )}
          </span>
        </div>
      )}

      {error !== null && (
        <div
          className="playback-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {!isActive ? (
        <button
          type="button"
          className="playback-primary-button"
          onClick={
            startPlayback
          }
          disabled={
            startMs === null ||
            endMs === null
          }
        >
          Start historical playback
        </button>
      ) : (
        <>
          <div className="playback-current-time">
            <span>
              Playback time
            </span>

            <strong>
              {formatPlaybackTimestamp(
                cursorMs,
              )}
            </strong>
          </div>

          <input
            className="playback-slider"
            type="range"
            min={0}
            max={
              durationSeconds
            }
            step={60}
            value={
              sliderSeconds
            }
            aria-label="Playback time"
            onChange={(
              event,
            ) => {
              if (
                startMs ===
                null
              ) {
                return;
              }

              setIsPlaying(
                false,
              );

              setCursorMs(
                startMs +
                  Number(
                    event
                      .target
                      .value,
                  ) *
                    1000,
              );
            }}
          />

          <div className="playback-range-labels">
            <span>
              {startMs !==
              null
                ? formatClock(
                    startMs,
                  )
                : "—"}
            </span>

            <span>
              {endMs !==
              null
                ? formatClock(
                    endMs,
                  )
                : "—"}
            </span>
          </div>

          <div className="playback-actions">
            <button
              type="button"
              onClick={
                jumpToStart
              }
              title="Jump to start"
            >
              |◀
            </button>

            <button
              type="button"
              className="playback-play-button"
              onClick={
                togglePlayback
              }
            >
              {isPlaying
                ? "❚❚ Pause"
                : "▶ Play"}
            </button>

            <button
              type="button"
              onClick={
                jumpToEnd
              }
              title="Jump to end"
            >
              ▶|
            </button>

            <label className="playback-speed">
              <span>
                Speed
              </span>

              <select
                value={
                  speed
                }
                onChange={(
                  event,
                ) => {
                  const value =
                    Number(
                      event
                        .target
                        .value,
                    );

                  if (
                    value === 1 ||
                    value === 4 ||
                    value === 16 ||
                    value === 60
                  ) {
                    setSpeed(
                      value,
                    );
                  }
                }}
              >
                <option value={1}>
                  1×
                </option>

                <option value={4}>
                  4×
                </option>

                <option value={16}>
                  16×
                </option>

                <option value={60}>
                  60×
                </option>
              </select>
            </label>

            <button
              type="button"
              className="playback-exit-button"
              onClick={
                exitPlayback
              }
            >
              Exit playback
            </button>
          </div>

          <small className="playback-note">
            Historical investigation
            overlays use a 15-minute
            context window around the
            current replay frame.
          </small>
        </>
      )}
    </section>
  );
}