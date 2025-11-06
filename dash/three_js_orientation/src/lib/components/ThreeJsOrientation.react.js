import React, { useState, useEffect, useRef } from "react";
import PropTypes from "prop-types";
import * as THREE from "three";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

const ThreeJsOrientation = ({
  id,
  data,
  activeTime,
  objFile,
  textureFile,
  style,
}) => {
  const mountRef = useRef(null);
  const sceneRef = useRef();
  const cameraRef = useRef();
  const rendererRef = useRef();
  const modelRef = useRef();
  const controlsRef = useRef();
  const mixerRef = useRef();
  const clockRef = useRef(new THREE.Clock());
  const requestIDRef = useRef();
  const loadStatus = useRef(0);
  const initialCameraPositionRef = useRef();
  const initialControlsTargetRef = useRef();

  const [currentPRH, setCurrentPRH] = useState({
    pitch: 0,
    roll: 0,
    heading: 0,
  });

  const [hasOrientationData, setHasOrientationData] = useState(true);

  // Add a ref to store the target quaternion
  const targetQuaternionRef = useRef(new THREE.Quaternion());

  // Sprites for cardinal direction labels
  const directionLabelsRef = useRef([]);

  // Initialize the scene only once
  useEffect(() => {
    const mount = mountRef.current;
    const width = mount.clientWidth;
    const height = mount.clientHeight;

    // Create scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xeeeeee);
    sceneRef.current = scene;

    // Add camera
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 10000);
    cameraRef.current = camera;

    // Add renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    rendererRef.current = renderer;
    mount.appendChild(renderer.domElement);

    // Add lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(0, 1, 1);
    scene.add(directionalLight);

    // Add orbit controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controlsRef.current = controls;

    const loader = new OBJLoader();
    loader.load(
      objFile,
      (obj) => {
        modelRef.current = obj;

        // Create an animation mixer for the model
        mixerRef.current = new THREE.AnimationMixer(obj);

        // Assuming animations are part of the model, load and play them
        if (obj.animations && obj.animations.length > 0) {
          obj.animations.forEach((clip) => {
            mixerRef.current.clipAction(clip).play();
          });
        }

        // Scale the model to 1/10th of its original size
        obj.scale.set(0.1, 0.1, 0.1);

        if (textureFile) {
          const textureLoader = new THREE.TextureLoader();
          const texture = textureLoader.load(textureFile, () => {
            obj.traverse((child) => {
              if (child.isMesh) {
                child.material.map = texture;
                child.material.needsUpdate = true;
              }
            });
          });
        }

        const box = new THREE.Box3().setFromObject(obj);
        const center = box.getCenter(new THREE.Vector3());
        obj.position.sub(center);

        // Add axes helper to the model
        const axesHelper = new THREE.AxesHelper(300);
        obj.add(axesHelper);

        // Adjust the camera to fit the model
        const size = box.getSize(new THREE.Vector3()).length();
        const fitDistance = size / Math.atan((Math.PI * camera.fov) / 360);
        camera.position.set(0, 0, fitDistance * 2);
        camera.updateProjectionMatrix();

        // Store initial camera position and controls target
        initialCameraPositionRef.current = camera.position.clone();
        initialControlsTargetRef.current = controls.target.clone();

        // Update controls target
        controls.target.copy(center);
        controls.update();

        scene.add(obj);

        // Calculate model's height
        const modelHeight = box.max.y - box.min.y;
        const gridOffset = modelHeight * 5;

        // Add grid helper below the model
        const gridSize = 100;
        const gridDivisions = 100;

        const gridHelperBelow = new THREE.GridHelper(gridSize, gridDivisions);
        gridHelperBelow.position.y = box.min.y - gridOffset;
        scene.add(gridHelperBelow);

        const gridHelperAbove = new THREE.GridHelper(
          gridSize,
          gridDivisions,
          0x5a5a8a,
          0x5a5a8a
        );
        gridHelperAbove.position.y = box.max.y + gridOffset;
        scene.add(gridHelperAbove);

        // Add cardinal direction labels to the lower grid
        addDirectionLabels(scene, gridHelperBelow.position.y, gridSize / 2);
      },
      (xhr) => {
        const percentLoaded = (xhr.loaded / xhr.total) * 100;
        const loadThresholds = [0, 25, 50, 75, 100];
        loadThresholds.forEach((threshold, index) => {
          if (
            loadStatus.current === loadThresholds[index - 1] &&
            percentLoaded >= threshold
          ) {
            console.log(`${threshold}% loaded`);
            loadStatus.current = threshold;
          }
        });
      },
      (error) => {
        console.error("An error occurred during OBJ loading:", error);
      }
    );

    // Start animation loop
    const animate = () => {
      const delta = clockRef.current.getDelta();

      // Update mixer for animations
      if (mixerRef.current) {
        mixerRef.current.update(delta);
      }

      // Interpolate the model's orientation
      if (modelRef.current) {
        modelRef.current.quaternion.slerp(targetQuaternionRef.current, 0.05);
      }

      // Update direction labels rotation based on model's heading
      updateDirectionLabels();

      controls.update();
      renderer.render(scene, camera);
      requestIDRef.current = requestAnimationFrame(animate);
    };
    animate();

    // Handle window resize
    const handleResize = () => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", handleResize);

    // Cleanup on unmount
    return () => {
      cancelAnimationFrame(requestIDRef.current);
      window.removeEventListener("resize", handleResize);
      controls.dispose();
      if (modelRef.current) {
        scene.remove(modelRef.current);
      }
      mount.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, [objFile, textureFile]);

  // Update the model's rotation whenever data or activeTime changes
  useEffect(() => {
    console.log("3D Model - useEffect triggered. Data length:", data?.length || 0, "activeTime:", activeTime);
    const updateModel = () => {
      let dataframe;
      try {
        dataframe = JSON.parse(data);
        console.log("3D Model - Parsed dataframe structure:", {
          hasIndex: !!dataframe.index,
          hasData: !!dataframe.data,
          hasColumns: !!dataframe.columns,
          indexLength: dataframe.index?.length || 0,
          dataLength: dataframe.data?.length || 0,
          columns: dataframe.columns,
          firstIndexValue: dataframe.index?.[0],
          firstDataRow: dataframe.data?.[0],
        });
      } catch (e) {
        console.error("Invalid data format:", e);
        setHasOrientationData(false);
        return;
      }

      // Check if dataframe has data
      if (
        !dataframe.index ||
        !dataframe.data ||
        dataframe.index.length === 0 ||
        dataframe.data.length === 0
      ) {
        console.warn("Empty dataframe provided to 3D orientation component", {
          hasIndex: !!dataframe.index,
          hasData: !!dataframe.data,
          indexLength: dataframe.index?.length || 0,
          dataLength: dataframe.data?.length || 0,
        });
        setHasOrientationData(false);
        setCurrentPRH({ pitch: 0, roll: 0, heading: 0 });
        return;
      }

      const timestamps = dataframe.index.map((t) => new Date(t).getTime());
      const activeTimestamp = activeTime;

      console.log("3D Model Update Debug:");
      console.log("  - activeTime received:", activeTime);
      console.log("  - First timestamp in data:", timestamps[0]);
      console.log("  - Last timestamp in data:", timestamps[timestamps.length - 1]);
      console.log("  - Number of timestamps:", timestamps.length);

      // Find the nearest timestamp
      let nearestIndex = 0;
      let minDiff = Math.abs(timestamps[0] - activeTimestamp);

      for (let i = 1; i < timestamps.length; i++) {
        const diff = Math.abs(timestamps[i] - activeTimestamp);
        if (diff < minDiff) {
          minDiff = diff;
          nearestIndex = i;
        }
      }

      // Map columns to indices
      // Check if columns exist and is an array
      if (!dataframe.columns || !Array.isArray(dataframe.columns)) {
        console.warn("Invalid or missing columns in dataframe");
        setHasOrientationData(false);
        setCurrentPRH({ pitch: 0, roll: 0, heading: 0 });
        return;
      }

      const columnIndices = dataframe.columns.reduce((acc, col, idx) => {
        acc[col] = idx;
        return acc;
      }, {});

      // Check if required orientation columns exist
      if (
        !("pitch" in columnIndices) ||
        !("roll" in columnIndices) ||
        !("heading" in columnIndices)
      ) {
        console.warn(
          "Missing orientation data (pitch/roll/heading). Showing neutral orientation."
        );
        setHasOrientationData(false);
        setCurrentPRH({ pitch: 0, roll: 0, heading: 0 });
        // Reset to neutral quaternion
        const neutralQuaternion = new THREE.Quaternion();
        neutralQuaternion.setFromEuler(new THREE.Euler(0, Math.PI / 2, 0, "ZYX"));
        targetQuaternionRef.current.copy(neutralQuaternion);
        return;
      }

      setHasOrientationData(true);

      // Get the pitch, roll, and heading from the nearest timestamp
      const rowData = dataframe.data[nearestIndex];
      const pitch = rowData[columnIndices.pitch] ?? 0;
      const roll = rowData[columnIndices.roll] ?? 0;
      const heading = rowData[columnIndices.heading] ?? 0;

      setCurrentPRH({ pitch, roll, heading });

      // Convert to radians
      const pitchRad = pitch * (Math.PI / 180);
      const rollRad = roll * (Math.PI / 180);
      const headingRad = heading * (Math.PI / 180);

      // Create a new quaternion for the target orientation
      const targetQuaternion = new THREE.Quaternion();
      targetQuaternion.setFromEuler(
        new THREE.Euler(pitchRad, headingRad + Math.PI / 2, rollRad, "ZYX")
      );

      // Store the target quaternion
      targetQuaternionRef.current.copy(targetQuaternion);
    };

    updateModel();
  }, [data, activeTime]);

  // Function to reset the camera to its initial position
  const resetCamera = () => {
    if (
      cameraRef.current &&
      controlsRef.current &&
      initialCameraPositionRef.current &&
      initialControlsTargetRef.current
    ) {
      cameraRef.current.position.copy(initialCameraPositionRef.current);
      controlsRef.current.target.copy(initialControlsTargetRef.current);
      controlsRef.current.update();
    }
  };

  // Function to add direction labels
  const addDirectionLabels = (scene, yPosition, distance) => {
    const labels = ["N", "S", "E", "W"];
    const positions = [
      new THREE.Vector3(0, yPosition, -distance), // North
      new THREE.Vector3(0, yPosition, distance), // South
      new THREE.Vector3(distance, yPosition, 0), // East
      new THREE.Vector3(-distance, yPosition, 0), // West
    ];

    labels.forEach((label, index) => {
      const sprite = createTextSprite(label);
      sprite.position.copy(positions[index]);
      scene.add(sprite);
      directionLabelsRef.current.push(sprite);
    });
  };

  // Function to create a text sprite
  const createTextSprite = (message) => {
    const fontface = "Arial";
    const fontsize = 82;
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 128;
    const context = canvas.getContext("2d");
    context.font = `${fontsize}px ${fontface}`;
    context.fillStyle = "white";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(message, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;

    const spriteMaterial = new THREE.SpriteMaterial({
      map: texture,
      depthTest: false,
      depthWrite: false,
    });

    const sprite = new THREE.Sprite(spriteMaterial);
    sprite.scale.set(20, 10, 1); // Adjust size as needed
    return sprite;
  };

  // Function to update direction labels rotation based on heading
  const updateDirectionLabels = () => {
    if (directionLabelsRef.current.length > 0) {
      const headingRad = currentPRH.heading * (Math.PI / 180);
      directionLabelsRef.current.forEach((sprite) => {
        sprite.rotation.y = -headingRad;
      });
    }
  };

  return (
    <div
      id={id}
      style={{ position: "relative", width: "100%", height: "100%", ...style }}
      ref={mountRef}
    >
      {/* Overlay for displaying pitch, roll, heading values */}
      <div
        style={{
          position: "absolute",
          top: "10px",
          left: "10px",
          backgroundColor: "rgba(255, 255, 255, 0.8)",
          padding: "10px",
          borderRadius: "5px",
          fontSize: "14px",
        }}
      >
        {hasOrientationData ? (
          <ul style={{ listStyleType: "none", margin: 0, padding: 0 }}>
            <li>
              <strong>Pitch:</strong>{" "}
              {currentPRH.pitch !== null && currentPRH.pitch !== undefined
                ? currentPRH.pitch.toFixed(2) + "°"
                : "N/A"}
            </li>
            <li>
              <strong>Roll:</strong>{" "}
              {currentPRH.roll !== null && currentPRH.roll !== undefined
                ? currentPRH.roll.toFixed(2) + "°"
                : "N/A"}
            </li>
            <li>
              <strong>Heading:</strong>{" "}
              {currentPRH.heading !== null && currentPRH.heading !== undefined
                ? currentPRH.heading.toFixed(2) + "°"
                : "N/A"}
            </li>
          </ul>
        ) : (
          <div style={{ color: "#666", fontStyle: "italic" }}>
            No orientation data available
          </div>
        )}
      </div>

      {/* Button to reset camera */}
      <button
        onClick={resetCamera}
        className="btn btn-sm btn-resetview"
      >
        Reset View
      </button>
    </div>
  );
};

ThreeJsOrientation.defaultProps = {};

ThreeJsOrientation.propTypes = {
  id: PropTypes.string,
  data: PropTypes.string.isRequired,
  activeTime: PropTypes.number.isRequired,
  objFile: PropTypes.string.isRequired,
  textureFile: PropTypes.string, // Optional texture file
  style: PropTypes.object,
};

export default ThreeJsOrientation;
