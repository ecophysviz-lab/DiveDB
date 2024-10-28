import React, { useRef, useEffect, useState } from "react";
import PropTypes from "prop-types";
import { Range, getTrackBackground } from "react-range";

const VideoPreview = ({
  id,
  videoSrc,
  activeTime,
  startTime: propStartTime,
  endTime: propEndTime,
  setProps,
  style,
  playheadTime,
  isPlaying, // New prop for controlling playback
}) => {
  const videoRef = useRef(null);
  const [duration, setDuration] = useState(0);
  const [startTime, setStartTime] = useState(propStartTime || 0);
  const [endTime, setEndTime] = useState(propEndTime || 0);
  const pastPlayheadTime = useRef(0);

  const tolerance = 1.1; // Define a small tolerance

  useEffect(() => {
    if (videoRef.current) {
      if (
        Math.abs(playheadTime - pastPlayheadTime.current) < tolerance ){
        console.log("maintaing seting playheadTime", playheadTime);
        pastPlayheadTime.current = playheadTime;
      } else if (playheadTime) {
        console.log({
          playheadTime,
          pastPlayheadTime: pastPlayheadTime.current,
        });
        videoRef.current.currentTime = playheadTime;
        pastPlayheadTime.current = playheadTime;
      }
    }
    console.log("videoRef.current", videoRef.current, playheadTime);
  }, [playheadTime, isPlaying]);

  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play();
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);

  const handleLoadedMetadata = () => {
    console.log("handleLoadedMetadata", videoRef.current);
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

  return (
    <div id={id} style={{ ...style }}>
      <video
        ref={videoRef}
        src={videoSrc}
        onLoadedMetadata={handleLoadedMetadata}
        width="100%"
        controls
        muted
      />
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
      ) : (
        <div style={{ margin: "50px", textAlign: "center" }}>
          Loading video duration...
        </div>
      )}
    </div>
  );
};

VideoPreview.propTypes = {
  id: PropTypes.string,
  videoSrc: PropTypes.string.isRequired,
  activeTime: PropTypes.number,
  startTime: PropTypes.number,
  endTime: PropTypes.number,
  setProps: PropTypes.func,
  style: PropTypes.object,
  playheadTime: PropTypes.number,
  isPlaying: PropTypes.bool, // New prop type
};

VideoPreview.defaultProps = {
  activeTime: 0,
  style: {},
  isPlaying: false, // Default to not playing
};

export default VideoPreview;
