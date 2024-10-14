import React, { useState, useEffect, useRef } from "react";
import PropTypes from "prop-types";
import * as THREE from "three";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

const ThreeJsOrientation = ({ id, data, activeTime, fbxFile, style }) => {
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

  const [currentPRH, setCurrentPRH] = useState({ pitch: 0, roll: 0, heading: 0 });

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

    // Load the FBX model
    const loader = new FBXLoader();
    loader.load(
      fbxFile,
      (fbx) => {
        modelRef.current = fbx;

        // Adjust the model's orientation to align nose with positive X-axis
        fbx.rotation.y = Math.PI / 2;

        // Center the model
        const box = new THREE.Box3().setFromObject(fbx);
        const center = box.getCenter(new THREE.Vector3());
        fbx.position.sub(center);

        // Add axes helper to the model
        const axesHelper = new THREE.AxesHelper(20);
        fbx.add(axesHelper);

        // Adjust the camera to fit the model
        const size = box.getSize(new THREE.Vector3()).length();
        const fitDistance = size / Math.atan((Math.PI * camera.fov) / 360);
        camera.position.set(0, 0, fitDistance * 1.2);
        camera.updateProjectionMatrix();

        // Store initial camera position and controls target
        initialCameraPositionRef.current = camera.position.clone();
        initialControlsTargetRef.current = controls.target.clone();

        // Update controls target
        controls.target.copy(center);
        controls.update();

        // Add model to scene
        scene.add(fbx);

        // Calculate model's height
        const modelHeight = box.max.y - box.min.y;
        const gridOffset = modelHeight * 2;

        // Add grid helper below the model
        const gridSize = 100;
        const gridDivisions = 100;

        const gridHelperBelow = new THREE.GridHelper(gridSize, gridDivisions);
        gridHelperBelow.position.y = box.min.y - gridOffset;
        scene.add(gridHelperBelow);

        // Add grid helper above the model
        const gridHelperAbove = new THREE.GridHelper(gridSize, gridDivisions);
        gridHelperAbove.position.y = box.max.y + gridOffset;
        scene.add(gridHelperAbove);

        // Add cardinal direction labels to the lower grid
        addDirectionLabels(scene, gridHelperBelow.position.y, gridSize / 2);

        // Setup animation mixer if animations are present
        if (fbx.animations && fbx.animations.length) {
          const mixer = new THREE.AnimationMixer(fbx);
          mixer.clipAction(fbx.animations[0]).play();
          mixerRef.current = mixer;
        }
      },
      (xhr) => {
        const percentLoaded = (xhr.loaded / xhr.total) * 100;
        const loadThresholds = [0, 25, 50, 75, 100];
        loadThresholds.forEach((threshold, index) => {
          if (loadStatus.current === loadThresholds[index - 1] && percentLoaded >= threshold) {
            console.log(`${threshold}% loaded`);
            loadStatus.current = threshold;
          }
        });
      },
      (error) => {
        console.error("An error occurred during FBX loading:", error);
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
  }, [fbxFile]);

  // Update the model's rotation whenever data or activeTime changes
  useEffect(() => {
    const updateModel = () => {
      let dataframe;
      try {
        dataframe = JSON.parse(data);
      } catch (e) {
        console.error("Invalid data format:", e);
        return;
      }

      const timestamps = dataframe.index.map((t) => new Date(t).getTime());
      const activeTimestamp = new Date(activeTime).getTime();

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
      const columnIndices = dataframe.columns.reduce((acc, col, idx) => {
        acc[col] = idx;
        return acc;
      }, {});

      // Get the pitch, roll, and heading from the nearest timestamp
      const rowData = dataframe.data[nearestIndex];
      const pitch = rowData[columnIndices.pitch];
      const roll = rowData[columnIndices.roll];
      const heading = rowData[columnIndices.heading];

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
          backgroundColor: "rgba(255, 255, 255, 0.5)",
          padding: "10px",
          borderRadius: "5px",
          fontSize: "14px",
        }}
      >
        <ul style={{ listStyleType: "none", margin: 0, padding: 0 }}>
          <li>
            <strong>Pitch:</strong> {currentPRH.pitch.toFixed(2)}°
          </li>
          <li>
            <strong>Roll:</strong> {currentPRH.roll.toFixed(2)}°
          </li>
          <li>
            <strong>Heading:</strong> {currentPRH.heading.toFixed(2)}°
          </li>
        </ul>
      </div>

      {/* Button to reset camera */}
      <button
        onClick={resetCamera}
        style={{
          position: "absolute",
          top: "10px",
          right: "10px",
          padding: "10px",
          fontSize: "14px",
          cursor: "pointer",
        }}
      >
        Reset View
      </button>
    </div>
  );
};

ThreeJsOrientation.defaultProps = {};

ThreeJsOrientation.propTypes = {
  id: PropTypes.string,
  data: PropTypes.string.isRequired, // JSON stringified DataFrame
  activeTime: PropTypes.string.isRequired, // ISO formatted datetime string
  fbxFile: PropTypes.string.isRequired, // URL or path to the .fbx file
  style: PropTypes.object,
};

export default ThreeJsOrientation;