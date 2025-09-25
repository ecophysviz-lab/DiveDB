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
}) => {
  const videoRef = useRef(null);
  const [duration, setDuration] = useState(0);
  const [isVideoActive, setIsVideoActive] = useState(false); // Track if video should be active for current playhead
  const lastPlayheadTime = useRef(null);
  const lastPlayingState = useRef(false);
  const videoStartTime = useRef(null); // Cache video start timestamp

  // Reset video state when videoSrc changes
  useEffect(() => {
    if (videoSrc) {
      setDuration(0);
      setIsVideoActive(false);
      lastPlayheadTime.current = null;
      lastPlayingState.current = false;
      videoStartTime.current = null;
      
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
      }
    }
  }, [videoSrc]);

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

  // Helper function to calculate video position and active state
  const calculateVideoPosition = () => {
    if (!videoMetadata || !playheadTime) return null;

    // Cache video start time for performance
    if (videoStartTime.current === null) {
      videoStartTime.current = new Date(videoMetadata.fileCreatedAt.replace("Z", "+00:00")).getTime() / 1000;
    }

    const videoDurationSeconds = parseVideoDuration(videoMetadata.duration);
    const videoEndTime = videoStartTime.current + videoDurationSeconds;

    // Check if playhead is within video's temporal range
    const isActive = playheadTime >= videoStartTime.current && playheadTime <= videoEndTime;
    const videoPosition = isActive ? playheadTime - videoStartTime.current : 0;

    return {
      isActive,
      videoPosition: Math.max(0, Math.min(videoDurationSeconds, videoPosition)),
      videoDurationSeconds
    };
  };

  // Handle play/pause state changes and manual seeking
  useEffect(() => {
    if (!videoRef.current || !playheadTime || !videoMetadata) return;

    const positionData = calculateVideoPosition();
    if (!positionData) return;

    const { isActive, videoPosition } = positionData;
    
    // Update active state
    setIsVideoActive(isActive);

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
        significantTimeJump = Math.abs(timeDiff) > 0.1; // Any meaningful change when paused/jumped
      }
    }

    if (isActive) {
      // Handle seeking (time jumps, state changes, or first update that need position update)
      if (playStateChanged || significantTimeJump || isFirstUpdate) {
        console.log(`🎯 ${videoMetadata.filename}: Seeking to ${videoPosition.toFixed(2)}s`);
        videoRef.current.currentTime = videoPosition;
      }

      // Handle playback state changes
      if (playStateChanged || isFirstUpdate) {
        if (isPlaying) {
          console.log(`▶️ ${videoMetadata.filename}: Starting playback`);
          videoRef.current.play().catch(e => console.warn("Video play failed:", e));
        } else {
          console.log(`⏸️ ${videoMetadata.filename}: Pausing video`);
          videoRef.current.pause();
        }
      }
    } else {
      // Video is outside temporal range
      if (!videoRef.current.paused) {
        console.log(`❌ ${videoMetadata.filename}: Video inactive - pausing`);
        videoRef.current.pause();
      }
    }

    // Update refs
    lastPlayheadTime.current = playheadTime;
    lastPlayingState.current = isPlaying;
  }, [isPlaying, playheadTime, videoMetadata]);

  const handleLoadedMetadata = () => {
    const videoDuration = videoRef.current.duration;
    setDuration(videoDuration);
  };

  const handleVideoError = (e) => {
    console.error("VideoPreview: Video loading error:", e);
    console.error("VideoPreview: Failed video source:", videoSrc);
  };


  return (
    <div id={id} style={{ ...style }}>
      {videoSrc && videoSrc.trim() ? (
        <div style={{ position: 'relative' }}>
          <video
            ref={videoRef}
            src={videoSrc}
            onLoadedMetadata={handleLoadedMetadata}
            onError={handleVideoError}
            width="100%"
            controls
            style={{
              borderRadius: "8px",
              backgroundColor: "#000000",
              opacity: isVideoActive ? 1 : 0.5, // Dim video when not temporally active
            }}
          />
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
                maxWidth: "90%",
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
        </div>
      ) : (
        <div
          style={{
            padding: "40px",
            textAlign: "center",
            backgroundColor: "#f8fafc",
            border: "2px dashed #cbd5e1",
            borderRadius: "12px",
            margin: "20px",
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
};

VideoPreview.defaultProps = {
  style: {},
  isPlaying: false,
};

export default VideoPreview;
