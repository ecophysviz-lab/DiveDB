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

        // Adjust the model's orientation
        fbx.rotation.y = Math.PI / 2; // Rotate model to align nose with positive X-axis

        // Center the model
        const box = new THREE.Box3().setFromObject(fbx);
        const center = box.getCenter(new THREE.Vector3());
        fbx.position.sub(center);

        // Add axes helper to the model
        const axesHelper = new THREE.AxesHelper(20); // Adjust size as needed
        fbx.add(axesHelper); // Attach axes helper to the model

        // Adjust the camera to fit the model
        const size = box.getSize(new THREE.Vector3()).length();
        const fitDistance = size / (2 * Math.atan((Math.PI * camera.fov) / 360));
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
        const gridOffset = modelHeight * 2; // Adjust this multiplier as needed

        // Add grid helper below the model
        const gridSize = 100;
        const gridDivisions = 100;

        const gridHelperBelow = new THREE.GridHelper(gridSize, gridDivisions);
        gridHelperBelow.position.y = box.min.y - gridOffset; // Position below
        scene.add(gridHelperBelow);

        // Add grid helper above the model
        const gridHelperAbove = new THREE.GridHelper(gridSize, gridDivisions);
        gridHelperAbove.position.y = box.max.y + gridOffset; // Position above
        scene.add(gridHelperAbove);

        // Setup animation mixer if animations are present
        if (fbx.animations && fbx.animations.length) {
          const mixer = new THREE.AnimationMixer(fbx);
          mixer.clipAction(fbx.animations[0]).play();
          mixerRef.current = mixer;
        }
      },
      (xhr) => {
        const percentLoaded = (xhr.loaded / xhr.total) * 100;
        const loadThresholds = [0, 25, 50, 75, 100]; // Define loading thresholds
        loadThresholds.forEach((threshold, index) => {
          if (loadStatus.current === loadThresholds[index-1] && percentLoaded >= threshold) {
            console.log(`${threshold}% loaded`);
            loadStatus.current = threshold;
          }
        });
      },
      (error) => {
        console.error('An error occurred during FBX loading:', error);
      }
    );

    // Start animation loop
    const animate = () => {
      const delta = clockRef.current.getDelta();

      // Update mixer for animations
      if (mixerRef.current) {
        mixerRef.current.update(delta);
      }

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
    window.addEventListener('resize', handleResize);

    // Cleanup on unmount
    return () => {
      cancelAnimationFrame(requestIDRef.current);
      window.removeEventListener('resize', handleResize);
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
        console.error('Invalid data format:', e);
        return;
      }

      console.log(dataframe);

      const timestamps = dataframe.index.map((t) => new Date(t).getTime());
      const activeTimestamp = new Date(activeTime).getTime();

      console.log(timestamps.map((t) => new Date(t).toISOString()));
      console.log(new Date(activeTime).toISOString());

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

      console.log(nearestIndex);

      // Map columns to indices
      const columnIndices = dataframe.columns.reduce((acc, col, idx) => {
        acc[col] = idx;
        return acc;
      }, {});

      // Get pitch, roll, heading
      const rowData = dataframe.data[nearestIndex];
      const pitch = rowData[columnIndices.pitch];
      const roll = rowData[columnIndices.roll];
      const heading = rowData[columnIndices.heading];

      console.log(pitch, roll, heading);

      // Store current PRH values
      setCurrentPRH({ pitch, roll, heading });

      // Convert to radians
      const pitchRad = pitch * (Math.PI / 180);
      const rollRad = roll * (Math.PI / 180);
      const headingRad = heading * (Math.PI / 180);

      // Apply rotations
      if (modelRef.current) {
        // Adjust rotation order if necessary
        modelRef.current.rotation.order = 'ZYX';

        // Apply rotations considering the initial rotation applied upon loading
        modelRef.current.rotation.x = pitchRad;
        modelRef.current.rotation.y = headingRad + Math.PI / 2; // Add initial rotation
        modelRef.current.rotation.z = rollRad;
      }
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

  return (
    <div
      id={id}
      style={{ position: 'relative', width: '100%', height: '100%', ...style }}
      ref={mountRef}
    >
      {/* Overlay for displaying pitch, roll, heading */}
      <div
        style={{
          position: 'absolute',
          top: '10px',
          left: '10px',
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          padding: '10px',
          borderRadius: '5px',
          fontSize: '14px',
        }}
      >
        <ul style={{ listStyleType: 'none', margin: 0, padding: 0 }}>
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
          position: 'absolute',
          top: '10px',
          right: '10px',
          padding: '10px',
          fontSize: '14px',
          cursor: 'pointer',
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
