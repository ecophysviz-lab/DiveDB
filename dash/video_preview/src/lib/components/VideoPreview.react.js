import React, { useRef, useEffect, useState } from "react";
import PropTypes from "prop-types";

const VideoPreview = ({
  id,
  videoSrc,
  videoMetadata,
  datasetStartTime,
  setProps,
  style,
  playheadTime,
  isPlaying, // Prop for controlling playback
  playbackRate = 1, // Prop for controlling playback speed (0.25 to 16)
  showControls = true, // Prop for controlling video controls visibility
  timeOffset = 0, // Prop for timeline offset in seconds
}) => {
  const videoRef = useRef(null);
  const [duration, setDuration] = useState(0);
  const [isVideoActive, setIsVideoActive] = useState(false); // Track if video should be active for current playhead
  const [controlsVisible, setControlsVisible] = useState(showControls); // Internal state for controls visibility
  const [localOffset, setLocalOffset] = useState(timeOffset); // Local offset state
  const [offsetPanelOpen, setOffsetPanelOpen] = useState(false); // Collapsible panel state
  const [fineControlsOpen, setFineControlsOpen] = useState(false); // Fine adjustment controls state
  const lastPlayheadTime = useRef(null);
  const lastPlayingState = useRef(false);
  const videoStartTime = useRef(null); // Cache video start timestamp
  const lastSeekTime = useRef(0); // Throttle seeking operations
  const lastActiveState = useRef(null); // Track active state to avoid unnecessary re-renders

  // Reset video state when videoSrc changes
  useEffect(() => {
    if (videoSrc) {
      setDuration(0);
      setIsVideoActive(false);
      setControlsVisible(showControls); // Reset controls state for new video
      setLocalOffset(0); // Reset offset to 0 for new video
      setOffsetPanelOpen(false); // Close offset panel for new video
      setFineControlsOpen(false); // Close fine controls for new video
      lastPlayheadTime.current = null;
      lastPlayingState.current = false;
      videoStartTime.current = null;
      lastSeekTime.current = 0; // Reset seek throttle
      lastActiveState.current = null; // Reset active state tracking
      
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
      }
    }
  }, [videoSrc, showControls]);

  // Helper function to parse video duration from HH:MM:SS.mmm format
  const parseVideoDuration = (durationStr) => {
    if (!durationStr) return 0;
    try {
      const timeParts = durationStr.split(":");
      if (timeParts.length === 3) {
        const hours = parseInt(timeParts[0]);
        const minutes = parseInt(timeParts[1]);
        const seconds = parseFloat(timeParts[2]);
        return hours * 3600 + minutes * 60 + seconds;
      }
    } catch (e) {
      console.error("Error parsing video duration:", e);
    }
    return 0;
  };

  // Helper function to format offset in a readable way
  const formatOffset = (offsetSeconds) => {
    const absOffset = Math.abs(offsetSeconds);
    const sign = offsetSeconds >= 0 ? "+" : "-";
    
    if (absOffset < 60) {
      return `${sign}${absOffset.toFixed(1)}s`;
    } else if (absOffset < 3600) {
      const minutes = Math.floor(absOffset / 60);
      const seconds = (absOffset % 60).toFixed(1);
      return `${sign}${minutes}m ${seconds}s`;
    } else {
      const hours = Math.floor(absOffset / 3600);
      const minutes = Math.floor((absOffset % 3600) / 60);
      const seconds = (absOffset % 60).toFixed(1);
      return `${sign}${hours}h ${minutes}m ${seconds}s`;
    }
  };

  // Helper function to format time in UTC 24-hour format (matching playhead format)
  const formatUTCTime = (dateString) => {
    try {
      const dateObject = new Date(dateString);
      const hours = dateObject.getUTCHours();
      const minutes = dateObject.getUTCMinutes();
      const seconds = dateObject.getUTCSeconds();
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } catch (e) {
      console.error("Error formatting UTC time:", e);
      return "Invalid time";
    }
  };

  // Helper function to update offset and notify parent
  const updateOffset = (newOffset) => {
    setLocalOffset(newOffset);
    if (setProps) {
      setProps({ timeOffset: newOffset });
    }
  };

  // Helper function to calculate video position and active state
  const calculateVideoPosition = () => {
    if (!videoMetadata || !playheadTime) return null;

    // Cache original video start time for performance
    if (videoStartTime.current === null) {
      videoStartTime.current = new Date(videoMetadata.fileCreatedAt.replace("Z", "+00:00")).getTime() / 1000;
    }

    // Apply time offset to video start time (positive offset = video appears later)
    const adjustedVideoStartTime = videoStartTime.current + localOffset;
    const videoDurationSeconds = parseVideoDuration(videoMetadata.duration);
    const adjustedVideoEndTime = adjustedVideoStartTime + videoDurationSeconds;

    // Check if playhead is within adjusted video's temporal range
    const isActive = playheadTime >= adjustedVideoStartTime && playheadTime <= adjustedVideoEndTime;
    const videoPosition = isActive ? playheadTime - adjustedVideoStartTime : 0;

    return {
      isActive,
      videoPosition: Math.max(0, Math.min(videoDurationSeconds, videoPosition)),
      videoDurationSeconds,
      originalVideoStartTime: videoStartTime.current,
      adjustedVideoStartTime,
      adjustedVideoEndTime
    };
  };

  // Handle play/pause state changes and manual seeking
  // Optimized with: seek throttling, state change detection to avoid unnecessary re-renders
  useEffect(() => {
    if (!videoRef.current || !playheadTime || !videoMetadata) return;

    const positionData = calculateVideoPosition();
    if (!positionData) return;

    const { isActive, videoPosition } = positionData;
    
    // Only update active state if it actually changed (prevents unnecessary re-renders)
    if (lastActiveState.current !== isActive) {
      setIsVideoActive(isActive);
      lastActiveState.current = isActive;
    }

    // Detect state changes
    const playStateChanged = lastPlayingState.current !== isPlaying;
    const isFirstUpdate = lastPlayheadTime.current === null; // First time this video gets playhead data
    
    // Detect manual scrubbing vs automatic progression
    let significantTimeJump = false;
    if (lastPlayheadTime.current !== null) {
      const timeDiff = playheadTime - lastPlayheadTime.current;
      
      // If we're playing, expect ~1 second progression (with tolerance)
      // If paused or time jump is large, it's manual scrubbing
      if (!isPlaying || Math.abs(timeDiff) > 3 || Math.abs(timeDiff) < 0.5) {
        significantTimeJump = Math.abs(timeDiff) >= 0.05; // Any meaningful change when paused/jumped
      }
    }

    // Throttle seeking during playback - max once per 100ms
    const SEEK_THROTTLE_MS = 100;
    const now = Date.now();
    const timeSinceLastSeek = now - lastSeekTime.current;
    const shouldThrottleSeek = isPlaying && timeSinceLastSeek < SEEK_THROTTLE_MS;

    if (isActive) {
      // Handle seeking (time jumps, state changes, or first update that need position update)
      // Apply throttle only during normal playback
      if ((playStateChanged || significantTimeJump || isFirstUpdate) && !shouldThrottleSeek) {
        videoRef.current.currentTime = videoPosition;
        lastSeekTime.current = now;
      }

      // Handle playback state changes
      if (playStateChanged || isFirstUpdate) {
        if (isPlaying) {
          // Set playback rate before playing (clamped to browser-supported range)
          const clampedRate = Math.max(0.25, Math.min(16, playbackRate || 1));
          videoRef.current.playbackRate = clampedRate;
          videoRef.current.play().catch(e => console.warn("Video play failed:", e));
        } else {
          videoRef.current.pause();
        }
      }
    } else {
      // Video is outside temporal range
      if (!videoRef.current.paused) {
        videoRef.current.pause();
      }
    }

    // Update refs
    lastPlayheadTime.current = playheadTime;
    lastPlayingState.current = isPlaying;
  }, [isPlaying, playheadTime, videoMetadata]);

  // Handle playback rate changes while playing
  useEffect(() => {
    if (!videoRef.current || !isPlaying) return;
    
    // Clamp to browser-supported range (most browsers: 0.25 to 16)
    const clampedRate = Math.max(0.25, Math.min(16, playbackRate || 1));
    videoRef.current.playbackRate = clampedRate;
  }, [playbackRate, isPlaying]);

  // Handle offset changes - immediately recalculate video position
  useEffect(() => {
    if (!videoRef.current || !playheadTime || !videoMetadata) return;

    const positionData = calculateVideoPosition();
    if (!positionData) return;

    const { isActive, videoPosition } = positionData;
    
    // Update active state immediately
    setIsVideoActive(isActive);

    if (isActive) {
      // Immediately seek to new position when offset changes
      console.log(`⏰ ${videoMetadata.filename}: Offset changed, seeking to ${videoPosition.toFixed(2)}s`);
      videoRef.current.currentTime = videoPosition;
      
      // Maintain current playback state
      if (isPlaying && videoRef.current.paused) {
        videoRef.current.play().catch(e => console.warn("Video play failed after offset change:", e));
      } else if (!isPlaying && !videoRef.current.paused) {
        videoRef.current.pause();
      }
    } else {
      // Video is now outside temporal range due to offset change
      if (!videoRef.current.paused) {
        console.log(`❌ ${videoMetadata.filename}: Offset change made video inactive - pausing`);
        videoRef.current.pause();
      }
    }
  }, [localOffset]); // Only trigger when offset changes (will use current values via closure)

  const handleLoadedMetadata = () => {
    const videoDuration = videoRef.current.duration;
    setDuration(videoDuration);
  };

  const handleVideoError = (e) => {
    console.error("VideoPreview: Video loading error:", e);
    console.error("VideoPreview: Failed video source:", videoSrc);
  };

  const toggleControls = () => {
    setControlsVisible(!controlsVisible);
  };

  const handleVideoMouseEnter = () => {
    setControlsVisible(true);
  };

  const handleVideoMouseLeave = () => {
    setControlsVisible(false);
  };

  return (
    <div id={id} style={{ ...style }}>
      {videoSrc && videoSrc.trim() ? (
        <div className="h-100">
          <video
            ref={videoRef}
            src={videoSrc}
            onLoadedMetadata={handleLoadedMetadata}
            onError={handleVideoError}
            onMouseEnter={handleVideoMouseEnter}
            onMouseLeave={handleVideoMouseLeave}
            width="100%"
            controls={controlsVisible}
            style={{
              opacity: isVideoActive ? 1 : 0.5, // Dim video when not temporally active
            }}
          />
          {/* Controls toggle button in top right */}
          <button
            onClick={toggleControls}
            className="d-none btn btn-xs btn-hidecontrols"
          >
            {controlsVisible ? "Hide Controls" : "Show Controls"}
          </button>
          {!isVideoActive && videoMetadata && (
            <div
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                backgroundColor: "rgba(0, 0, 0, 0.8)",
                color: "white",
                padding: "12px 20px",
                borderRadius: "8px",
                textAlign: "center",
                fontSize: "14px",
                boxSizing: "border-box",
              }}
            >
              <div style={{ fontWeight: "bold", marginBottom: "4px" }}>
                Video not active
              </div>
              <div style={{ fontSize: "12px", opacity: 0.9 }}>
                Timeline is outside video time range
              </div>
            </div>
          )}

          {/* Timeline offset controls - positioned below video */}
          {videoMetadata && (
            <div className="offset_panel">
              {/* Toggle button for offset panel */}
              <button
                className="btn btn-xs"
                onClick={() => setOffsetPanelOpen(!offsetPanelOpen)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                🕒 {formatOffset(localOffset)} {offsetPanelOpen ? "▲" : "▼"}
              </button>
              
              {/* Collapsible offset controls panel */}
              {offsetPanelOpen && (
                <div className="dropdown-menu show">
                  <p><strong>Timeline Offset Adjustment</strong></p>
                  
                  {/* Slider control */}
                  <div>
                    <p className="p sm">
                      Coarse: {formatOffset(localOffset)}
                    </p>
                    <input
                      class="form-range"
                      type="range"
                      min="-3600"
                      max="3600"
                      step="60"
                      value={localOffset}
                      onChange={(e) => updateOffset(parseFloat(e.target.value))}
                      // style={{
                      //   width: "100%",
                      //   height: "6px",
                      //   background: "var(--blueMedium))",
                      //   borderRadius: "3px",
                      //   outline: "none"
                      // }}
                    />
                    <div className="range-labels">
                      <span>-1hr</span>
                      <span>0</span>
                      <span>+1hr</span>
                    </div>
                  </div>
                  
                  {/* Fine adjustment toggle/input */}
                  <div style={{ marginBottom: "16px" }}>
                    {!fineControlsOpen ? (
                      // Show toggle button when fine controls are closed
                      <button
                        className="btn btn-xs btn-stroke"
                        onClick={() => setFineControlsOpen(true)}
                      >
                        + Fine adjustment (seconds)
                      </button>
                    ) : (
                      // Show fine controls when open
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                          <p className="sm">Fine (seconds):</p>
                          <button
                            onClick={() => setFineControlsOpen(false)}
                            className="btn btn-xs"
                          >
                            ✕ close
                          </button>
                        </div>
                        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                          <input
                            type="number"
                            step="0.1"
                            value={localOffset}
                            onChange={(e) => updateOffset(parseFloat(e.target.value) || 0)}
                            style={{
                              flex: 1,
                              padding: "8px",
                              backgroundColor: "rgba(255, 255, 255, 0.1)",
                              border: "1px solid rgba(255, 255, 255, 0.3)",
                              borderRadius: "4px",
                              color: "white",
                              fontSize: "12px"
                            }}
                          />
                          <button
                            onClick={() => updateOffset(0)}
                            style={{
                              padding: "8px 12px",
                              backgroundColor: "rgba(255, 255, 255, 0.2)",
                              border: "1px solid rgba(255, 255, 255, 0.3)",
                              borderRadius: "4px",
                              color: "white",
                              fontSize: "11px",
                              cursor: "pointer",
                              fontWeight: "500"
                            }}
                          >
                            Reset
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Visual feedback */}
                  <hr />
                  <p className="sm mb-1">
                    <strong>Original:</strong> {formatUTCTime(videoMetadata.fileCreatedAt)} UTC
                  </p>
                  <p className="sm mb-0">
                    <strong>Adjusted:</strong> {formatUTCTime(new Date(new Date(videoMetadata.fileCreatedAt).getTime() + localOffset * 1000).toISOString())} UTC
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div
          style={{
            padding: "40px",
            textAlign: "center",
            backgroundColor: "#f8fafc",
            borderRadius: "12px",
          }}
        >
          <h3 style={{ margin: "0 0 8px 0", color: "#475569" }}>
            No video selected
          </h3>
          <p style={{ margin: 0, fontSize: "14px", color: "#475569" }}>
            Click a video indicator on the timeline to play
          </p>
        </div>
      )}
    </div>
  );
};

VideoPreview.propTypes = {
  id: PropTypes.string,
  videoSrc: PropTypes.string,
  videoMetadata: PropTypes.object,
  datasetStartTime: PropTypes.number,
  setProps: PropTypes.func,
  style: PropTypes.object,
  playheadTime: PropTypes.number,
  isPlaying: PropTypes.bool,
  playbackRate: PropTypes.number,
  showControls: PropTypes.bool,
  timeOffset: PropTypes.number,
};

VideoPreview.defaultProps = {
  style: {},
  isPlaying: false,
  playbackRate: 1,
  showControls: true,
  timeOffset: 0,
};

export default VideoPreview;
