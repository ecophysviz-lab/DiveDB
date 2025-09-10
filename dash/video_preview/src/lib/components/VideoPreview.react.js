import React, { useRef, useEffect, useState } from "react";
import PropTypes from "prop-types";
import { Range, getTrackBackground } from "react-range";

const VideoPreview = ({
  id,
  videoSrc,
  startTime: propStartTime,
  endTime: propEndTime,
  setProps,
  style,
  playheadTime,
  isPlaying, // New prop for controlling playback
  videoOptions = [], // New prop for video options
  selectedVideoId = null, // New prop for selected video
  restrictedTimeRange = {}, // New prop for time restrictions
}) => {
  const videoRef = useRef(null);
  const [duration, setDuration] = useState(0);
  const [startTime, setStartTime] = useState(propStartTime || 0);
  const [endTime, setEndTime] = useState(propEndTime || 0);
  const pastPlayheadTime = useRef(0);
  const initialPlayheadTime = useRef(null); // Store the initial playheadTime
  const [currentVideoId, setCurrentVideoId] = useState(selectedVideoId);
  const [currentVideoSrc, setCurrentVideoSrc] = useState(videoSrc);

  useEffect(() => {
    if (videoRef.current && playheadTime != null) {
      if (initialPlayheadTime.current === null) {
        // Store the first playheadTime as the reference point
        initialPlayheadTime.current = playheadTime;
      }

      // Calculate the time difference from the initial playheadTime
      const timeDiff =
        new Date(playheadTime) - new Date(initialPlayheadTime.current);
      if (Math.abs(videoRef.current.currentTime - timeDiff) > 1) {
        // Adjust the threshold as needed
        videoRef.current.currentTime = timeDiff;
        pastPlayheadTime.current = playheadTime;

        if (isPlaying) {
          videoRef.current.play();
        }
      }
    }
  }, [playheadTime]);

  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play();
        pastPlayheadTime.current = playheadTime;
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);

  const handleLoadedMetadata = () => {
    const videoDuration = videoRef.current.duration;
    setDuration(videoDuration);

    if (propStartTime === undefined) {
      setStartTime(0);
      if (setProps) setProps({ startTime: 0 });
    }
    if (propEndTime === undefined) {
      setEndTime(videoDuration);
      if (setProps) setProps({ endTime: videoDuration });
    }
  };

  const handleTrimChange = (values) => {
    setStartTime(values[0]);
    setEndTime(values[1]);
    if (setProps) {
      setProps({ startTime: values[0], endTime: values[1] });
    }

    if (videoRef.current) {
      if (
        videoRef.current.currentTime < values[0] ||
        videoRef.current.currentTime > values[1]
      ) {
        videoRef.current.currentTime = values[0];
      }
    }
  };

  const handleVideoSelection = (videoId) => {
    const selectedVideo = videoOptions.find(video => video.id === videoId);
    if (selectedVideo) {
      setCurrentVideoId(videoId);
      
      // Use the share key URL if available, otherwise fallback to original
      const videoUrl = selectedVideo.shareUrl || selectedVideo.originalUrl;
      
      console.log(`Loading video: ${videoUrl}`);
      console.log('Share URL available:', !!selectedVideo.shareUrl);
      console.log('Selected video object:', selectedVideo);
      console.log('Available URLs:', {
        shareUrl: selectedVideo.shareUrl,
        originalUrl: selectedVideo.originalUrl,
        thumbnailUrl: selectedVideo.thumbnailUrl
      });
      
      setCurrentVideoSrc(videoUrl);
      
      if (setProps) {
        setProps({ 
          selectedVideoId: videoId,
          videoSrc: videoUrl
        });
      }
    }
  };

  const handleBackToSelector = () => {
    setCurrentVideoId(null);
    setCurrentVideoSrc(null);
    if (setProps) {
      setProps({ 
        selectedVideoId: null,
        videoSrc: null
      });
    }
  };

  // Helper function to safely convert duration to number of seconds
  const parseDuration = (duration) => {
    if (!duration) return null;
    
    // Handle different duration formats
    if (typeof duration === 'number') {
      return duration; // Already in seconds
    }
    
    if (typeof duration === 'string') {
      // Check if it's in HH:MM:SS.mmm format
      const timeMatch = duration.match(/^(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?$/);
      if (timeMatch) {
        const [, hours, minutes, seconds, milliseconds = '0'] = timeMatch;
        const totalSeconds = 
          parseInt(hours) * 3600 + 
          parseInt(minutes) * 60 + 
          parseInt(seconds) + 
          parseInt(milliseconds.padEnd(3, '0')) / 1000;
        return totalSeconds;
      }
      
      // Try parsing as a simple number string
      const parsed = parseFloat(duration);
      if (!isNaN(parsed)) {
        return parsed;
      }
    }
    
    return null;
  };

  // Helper function to format duration nicely
  const formatDuration = (duration) => {
    const parsed = parseDuration(duration);
    if (!parsed) return null;
    
    if (parsed < 60) {
      return `${Math.round(parsed)}s`;
    } else if (parsed < 3600) {
      const minutes = Math.floor(parsed / 60);
      const seconds = Math.round(parsed % 60);
      return `${minutes}m ${seconds}s`;
    } else {
      const hours = Math.floor(parsed / 3600);
      const minutes = Math.floor((parsed % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  };

  const renderVideoSelector = () => {
    if (videoOptions.length === 0) {
      return (
        <div style={{ 
          padding: "60px 40px", 
          textAlign: "center", 
          backgroundColor: "#f8fafc",
          border: "2px dashed #cbd5e1",
          borderRadius: "12px",
          color: "#64748b",
          margin: "20px"
        }}>
          <h3 style={{ margin: "0 0 8px 0", color: "#475569" }}>No videos available</h3>
          <p style={{ margin: 0, fontSize: "14px" }}>No videos found for this deployment</p>
        </div>
      );
    }

    return (
      <div style={{ 
        marginBottom: "24px",
        padding: "20px",
        backgroundColor: "#f8fafc",
        borderRadius: "12px"
      }}>
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          marginBottom: "24px",
          paddingBottom: "16px",
          borderBottom: "2px solid #e2e8f0"
        }}>
          <h3 style={{ 
            margin: 0,
            fontSize: "18px",
            fontWeight: "600",
            color: "#1e293b"
          }}>
            Select Video ({videoOptions.length} available)
          </h3>
        </div>
        
        <div style={{ 
          display: "grid", 
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: "20px",
          padding: "4px"
        }}>
          {videoOptions.map((video) => {
            const isSelected = currentVideoId === video.id;
            const duration = formatDuration(video.metadata?.duration);
            
            return (
              <div
                key={video.id}
                onClick={() => handleVideoSelection(video.id)}
                style={{
                  padding: "16px",
                  paddingBottom: "8px",
                  border: isSelected ? "2px solid #3b82f6" : "1px solid #e2e8f0",
                  borderRadius: "12px",
                  backgroundColor: isSelected ? "#eff6ff" : "#ffffff",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  boxShadow: isSelected ? "0 8px 25px rgba(59, 130, 246, 0.15)" : "0 4px 6px rgba(0, 0, 0, 0.05)",
                  position: "relative",
                  overflow: "scroll"
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow = "0 8px 25px rgba(0, 0, 0, 0.1)";
                    e.currentTarget.style.borderColor = "#cbd5e1";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow = "0 4px 6px rgba(0, 0, 0, 0.05)";
                    e.currentTarget.style.borderColor = "#e2e8f0";
                  }
                }}
              >
                {/* Header */}
                <div style={{ 
                  display: "flex", 
                  alignItems: "flex-start",
                  marginBottom: "4px"
                }}>
                  <div style={{ 
                    fontWeight: "600", 
                    fontSize: "16px",
                    color: isSelected ? "#1d4ed8" : "#1e293b",
                    flex: 1,
                    lineHeight: "1.3",
                    paddingRight: "8px"
                  }}>
                    {video.filename || 'Untitled Video'}
                  </div>
                  {isSelected && (
                    <div style={{
                      width: "20px",
                      height: "20px",
                      backgroundColor: "#10b981",
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "12px",
                      flexShrink: 0
                    }}>
                      ✓
                    </div>
                  )}
                </div>

                {/* Metadata section */}
                <div style={{ marginBottom: "16px" }}>
                  <div style={{ 
                    fontSize: "14px", 
                    color: "#64748b", 
                    fontWeight: "500"
                  }}>
                    Created: {new Date(video.fileCreatedAt).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </div>
                  
                  <div style={{ 
                    fontSize: "14px", 
                    color: "#64748b",
                    fontWeight: "500"
                  }}>
                    Duration: {duration || 'Unknown'}
                  </div>
                </div>

                {/* Selection indicator */}
                {isSelected && (
                  <div style={{ 
                    position: "absolute",
                    top: 0,
                    right: 0,
                    width: "0",
                    height: "0",
                    borderStyle: "solid",
                    borderWidth: "0 30px 30px 0",
                    borderColor: "transparent #3b82f6 transparent transparent"
                  }} />
                )}

                {/* Bottom action area */}
                <div style={{
                  marginTop: "8px",
                  paddingTop: "8px",
                  borderTop: "1px solid #f1f5f9",
                  textAlign: "center"
                }}>
                  <div style={{ 
                    fontSize: "13px",
                    fontWeight: "500",
                    color: isSelected ? "#1d4ed8" : "#64748b",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px"
                  }}>
                    {isSelected ? "Selected" : "Click to Select"}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div id={id} style={{ ...style }}>
      {/* Show video selector when no video is selected */}
      {!currentVideoId && renderVideoSelector()}
      
      {/* Show video player with back button when video is selected */}
      {currentVideoId && currentVideoSrc ? (
        <div>
          {/* Back button and video info header */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "16px",
            padding: "16px 20px",
            backgroundColor: "#f8fafc",
            borderRadius: "8px",
            border: "1px solid #e2e8f0"
          }}>
            <button
              onClick={handleBackToSelector}
              style={{
                display: "flex",
                alignItems: "center",
                padding: "8px 16px",
                backgroundColor: "#ffffff",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                cursor: "pointer",
                fontSize: "14px",
                fontWeight: "500",
                color: "#374151",
                transition: "all 0.2s ease"
              }}
              onMouseEnter={(e) => {
                e.target.style.backgroundColor = "#f9fafb";
                e.target.style.borderColor = "#9ca3af";
              }}
              onMouseLeave={(e) => {
                e.target.style.backgroundColor = "#ffffff";
                e.target.style.borderColor = "#d1d5db";
              }}
            >
              <span style={{ marginRight: "8px" }}>←</span>
              Back to Videos
            </button>
            
            <div style={{ 
              fontSize: "14px", 
              color: "#6b7280",
              fontWeight: "500"
            }}>
              {videoOptions.find(v => v.id === currentVideoId)?.filename || 'Selected Video'}
            </div>
          </div>

          {/* Video player */}
          <video
            ref={videoRef}
            src={currentVideoSrc}
            onLoadedMetadata={handleLoadedMetadata}
            width="100%"
            controls
            muted
            style={{
              borderRadius: "8px",
              backgroundColor: "#000000"
            }}
          />
        </div>
      ) : !currentVideoId && videoOptions.length === 0 ? (
        <div style={{ 
          padding: "40px", 
          textAlign: "center", 
          backgroundColor: "#f8fafc",
          border: "2px dashed #cbd5e1",
          borderRadius: "12px",
          color: "#64748b",
          margin: "20px"
        }}>
          <h3 style={{ margin: "0 0 8px 0", color: "#475569" }}>No videos available</h3>
          <p style={{ margin: 0, fontSize: "14px" }}>No videos found for this deployment</p>
        </div>
      ) : null}
      {duration > 0 ? (
        <div style={{ margin: "50px", width: "90%" }}>
          <Range
            values={[startTime, endTime]}
            step={0.01}
            min={0}
            max={duration}
            onChange={handleTrimChange}
            renderTrack={({ props, children }) => (
              <div
                onMouseDown={props.onMouseDown}
                onTouchStart={props.onTouchStart}
                style={{
                  ...props.style,
                  height: "8px",
                  display: "flex",
                  width: "100%",
                  backgroundColor: "#2C3E50",
                  borderRadius: "4px",
                }}
              >
                <div
                  ref={props.ref}
                  style={{
                    height: "8px",
                    width: "100%",
                    borderRadius: "4px",
                    background: getTrackBackground({
                      values: [startTime, endTime],
                      colors: ["#ccc", "#3498DB", "#ccc"],
                      min: 0,
                      max: duration,
                    }),
                    alignSelf: "center",
                  }}
                >
                  {children}
                </div>
              </div>
            )}
            renderThumb={({ index, props, isDragged }) => (
              <div
                {...props}
                style={{
                  ...props.style,
                  height: "20px",
                  width: "20px",
                  borderRadius: "50%",
                  backgroundColor: "#FFF",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  boxShadow: "0px 2px 6px #AAA",
                  border: "2px solid #3498DB",
                }}
              >
                <div
                  style={{
                    height: "10px",
                    width: "2px",
                    backgroundColor: isDragged ? "#3498DB" : "#CCC",
                  }}
                />
              </div>
            )}
          />
        </div>
      ) : null}
    </div>
  );
};

VideoPreview.propTypes = {
  id: PropTypes.string,
  videoSrc: PropTypes.string.isRequired,
  startTime: PropTypes.number,
  endTime: PropTypes.number,
  setProps: PropTypes.func,
  style: PropTypes.object,
  playheadTime: PropTypes.number,
  isPlaying: PropTypes.bool,
  currentTime: PropTypes.number,

  /**
   * Array of available video options with metadata.
   */
  videoOptions: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    filename: PropTypes.string.isRequired,
    fileCreatedAt: PropTypes.string.isRequired,
    shareUrl: PropTypes.string, // URL with share key for authenticated access
    originalUrl: PropTypes.string, // Fallback URL without authentication
    thumbnailUrl: PropTypes.string, // Thumbnail image URL
    metadata: PropTypes.shape({
      duration: PropTypes.string, // Duration in HH:MM:SS.mmm format or seconds
      originalFilename: PropTypes.string,
      type: PropTypes.string, // VIDEO, IMAGE, etc.
    })
  })),

  /**
   * The ID of the currently selected video.
   */
  selectedVideoId: PropTypes.string,

  /**
   * Time range restrictions for video playback synchronization.
   */
  restrictedTimeRange: PropTypes.shape({
    start: PropTypes.string,
    end: PropTypes.string,
    startTimestamp: PropTypes.number,
    endTimestamp: PropTypes.number,
  }),
};

VideoPreview.defaultProps = {
  style: {},
  isPlaying: false,
  currentTime: 0,
  videoOptions: [],
  selectedVideoId: null,
  restrictedTimeRange: {},
};

export default VideoPreview;
