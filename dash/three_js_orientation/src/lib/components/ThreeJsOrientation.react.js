import React, { useState, useEffect, useRef } from "react";
import PropTypes from "prop-types";
import * as THREE from "three";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

// Fixed scene dimensions for consistent grid sizing across all models
const GRID_SIZE = 100;
const GRID_DIVISIONS = 100;
const GRID_OFFSET = 25; // Fixed vertical offset for grids from center
const TARGET_MODEL_SIZE = 10; // Target size for normalized models

/**
 * Get the appropriate loader based on file extension.
 * @param {string} filename - The filename or URL to load
 * @returns {OBJLoader|GLTFLoader|FBXLoader} The appropriate loader
 */
const getLoader = (filename) => {
  if (!filename) return null;
  
  const ext = filename.split('.').pop().toLowerCase().split('?')[0]; // Handle URLs with query params
  
  if (ext === 'glb' || ext === 'gltf') {
    return new GLTFLoader();
  }
  if (ext === 'fbx') {
    return new FBXLoader();
  }
  return new OBJLoader(); // default
};

/**
 * Get file extension from filename/URL
 * @param {string} filename - The filename or URL
 * @returns {string} The file extension (lowercase)
 */
const getFileExtension = (filename) => {
  if (!filename) return '';
  return filename.split('.').pop().toLowerCase().split('?')[0];
};

/**
 * Check if a model file path is valid (not empty or placeholder)
 */
const isValidModelFile = (modelFile) => {
  return modelFile && modelFile.trim() !== '' && modelFile !== 'none';
};

const ThreeJsOrientation = ({
  id,
  data,
  activeTime,
  modelFile, // Can be empty/null for no-model state
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
  const gridHelpersRef = useRef([]);
  const axesHelperRef = useRef();

  const [currentPRH, setCurrentPRH] = useState({
    pitch: 0,
    roll: 0,
    heading: 0,
  });

  const [hasOrientationData, setHasOrientationData] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [hasModel, setHasModel] = useState(false);

  // Add a ref to store the target quaternion
  const targetQuaternionRef = useRef(new THREE.Quaternion());

  // Sprites for cardinal direction labels
  const directionLabelsRef = useRef([]);

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

  /**
   * Set up the default scene with grids (no model)
   */
  const setupDefaultScene = (scene, camera, controls) => {
    // Add grid helpers at fixed positions
    const gridHelperBelow = new THREE.GridHelper(GRID_SIZE, GRID_DIVISIONS);
    gridHelperBelow.position.y = -GRID_OFFSET;
    scene.add(gridHelperBelow);
    gridHelpersRef.current.push(gridHelperBelow);

    const gridHelperAbove = new THREE.GridHelper(
      GRID_SIZE,
      GRID_DIVISIONS,
      0x5a5a8a,
      0x5a5a8a
    );
    gridHelperAbove.position.y = GRID_OFFSET;
    scene.add(gridHelperAbove);
    gridHelpersRef.current.push(gridHelperAbove);

    // Add cardinal direction labels to the lower grid
    addDirectionLabels(scene, gridHelperBelow.position.y, GRID_SIZE / 2);

    // Set up camera for the default view
    camera.position.set(0, 30, 100);
    camera.updateProjectionMatrix();
    
    // Store initial camera position and controls target
    initialCameraPositionRef.current = camera.position.clone();
    initialControlsTargetRef.current = new THREE.Vector3(0, 0, 0);
    
    controls.target.set(0, 0, 0);
    controls.update();

    setHasModel(false);
    setIsLoading(false);
    setLoadError(null);
  };

  /**
   * Process the loaded model and add it to the scene.
   * Handles different loader output formats (OBJ, GLTF, FBX).
   * Normalizes model size to TARGET_MODEL_SIZE for consistent grid appearance.
   */
  const processLoadedModel = (loadResult, fileExtension, scene, camera, controls) => {
    let model;
    let animations = [];

    // GLTFLoader returns { scene, animations, ... }
    if (fileExtension === 'glb' || fileExtension === 'gltf') {
      model = loadResult.scene;
      animations = loadResult.animations || [];
      console.log(`GLTF/GLB model loaded with ${animations.length} animations`);
    } 
    // FBXLoader returns a Group with animations property
    else if (fileExtension === 'fbx') {
      model = loadResult;
      animations = loadResult.animations || [];
      console.log(`FBX model loaded with ${animations.length} animations`);
    }
    // OBJLoader returns a Group
    else {
      model = loadResult;
      animations = loadResult.animations || [];
    }

    modelRef.current = model;

    // Create an animation mixer for the model
    mixerRef.current = new THREE.AnimationMixer(model);

    // Play all animations if available
    if (animations.length > 0) {
      animations.forEach((clip) => {
        mixerRef.current.clipAction(clip).play();
      });
    }

    // Calculate model's bounding box BEFORE any transforms
    const box = new THREE.Box3().setFromObject(model);
    const modelSize = box.getSize(new THREE.Vector3());
    const maxDimension = Math.max(modelSize.x, modelSize.y, modelSize.z);
    
    // Normalize the model scale so the largest dimension equals TARGET_MODEL_SIZE
    const scaleFactor = TARGET_MODEL_SIZE / maxDimension;
    model.scale.set(scaleFactor, scaleFactor, scaleFactor);
    
    console.log(`Model original size: ${maxDimension.toFixed(2)}, scale factor: ${scaleFactor.toFixed(4)}`);

    // Recalculate bounding box after scaling
    const scaledBox = new THREE.Box3().setFromObject(model);
    const center = scaledBox.getCenter(new THREE.Vector3());
    model.position.sub(center);

    // Apply texture if provided
    // For OBJ/FBX: textures need to be loaded separately
    // For GLB/GLTF: textures are usually embedded, but we can override if provided
    if (textureFile && textureFile.trim() !== '') {
      console.log(`Loading texture: ${textureFile}`);
      const textureLoader = new THREE.TextureLoader();
      
      // For cross-origin textures (like from Notion S3), we need to handle CORS
      textureLoader.setCrossOrigin('anonymous');
      
      textureLoader.load(
        textureFile,
        (texture) => {
          console.log('Texture loaded successfully');
          model.traverse((child) => {
            if (child.isMesh) {
              // Preserve existing material properties, just add/update the texture map
              if (child.material) {
                child.material.map = texture;
                child.material.needsUpdate = true;
              }
            }
          });
        },
        undefined, // onProgress
        (error) => {
          console.warn('Failed to load texture:', error);
        }
      );
    }

    // Add axes helper to the model (scaled appropriately)
    const axesHelper = new THREE.AxesHelper(TARGET_MODEL_SIZE * 20);
    model.add(axesHelper);
    axesHelperRef.current = axesHelper;

    scene.add(model);

    // Add grids at fixed positions (not relative to model size)
    const gridHelperBelow = new THREE.GridHelper(GRID_SIZE, GRID_DIVISIONS);
    gridHelperBelow.position.y = -GRID_OFFSET;
    scene.add(gridHelperBelow);
    gridHelpersRef.current.push(gridHelperBelow);

    const gridHelperAbove = new THREE.GridHelper(
      GRID_SIZE,
      GRID_DIVISIONS,
      0x5a5a8a,
      0x5a5a8a
    );
    gridHelperAbove.position.y = GRID_OFFSET;
    scene.add(gridHelperAbove);
    gridHelpersRef.current.push(gridHelperAbove);

    // Add cardinal direction labels to the lower grid
    addDirectionLabels(scene, gridHelperBelow.position.y, GRID_SIZE / 2);

    // Set camera to a good viewing position for the normalized model
    const fitDistance = TARGET_MODEL_SIZE * 8;
    camera.position.set(0, TARGET_MODEL_SIZE * 2, fitDistance);
    camera.updateProjectionMatrix();

    // Store initial camera position and controls target
    initialCameraPositionRef.current = camera.position.clone();
    initialControlsTargetRef.current = new THREE.Vector3(0, 0, 0);

    // Update controls target
    controls.target.set(0, 0, 0);
    controls.update();

    setHasModel(true);
    setIsLoading(false);
    setLoadError(null);
  };

  /**
   * Clean up the current model and associated objects from the scene.
   */
  const cleanupModel = (scene) => {
    // Remove current model
    if (modelRef.current) {
      scene.remove(modelRef.current);
      modelRef.current.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
          if (Array.isArray(child.material)) {
            child.material.forEach((mat) => mat.dispose());
          } else {
            child.material.dispose();
          }
        }
      });
      modelRef.current = null;
    }

    // Remove grid helpers
    gridHelpersRef.current.forEach((grid) => {
      scene.remove(grid);
      grid.geometry.dispose();
      grid.material.dispose();
    });
    gridHelpersRef.current = [];

    // Remove direction labels
    directionLabelsRef.current.forEach((sprite) => {
      scene.remove(sprite);
      sprite.material.map.dispose();
      sprite.material.dispose();
    });
    directionLabelsRef.current = [];

    // Reset mixer
    if (mixerRef.current) {
      mixerRef.current.stopAllAction();
      mixerRef.current = null;
    }

    setHasModel(false);
  };

  // Initialize the scene only once, but reload model when modelFile changes
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

    // Check if we should load a model or show empty state
    if (isValidModelFile(modelFile)) {
      // Load the model
      setIsLoading(true);
      setLoadError(null);
      loadStatus.current = 0;

      const fileExtension = getFileExtension(modelFile);
      const loader = getLoader(modelFile);
      
      console.log(`Loading 3D model: ${modelFile} (format: ${fileExtension})`);

      loader.load(
        modelFile,
        (loadResult) => {
          processLoadedModel(loadResult, fileExtension, scene, camera, controls);
        },
        (xhr) => {
          if (xhr.total > 0) {
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
          }
        },
        (error) => {
          console.error(`Error loading ${fileExtension.toUpperCase()} model:`, error);
          setLoadError(`Failed to load model: ${error.message || 'Unknown error'}`);
          setIsLoading(false);
          // Fall back to default scene on error
          setupDefaultScene(scene, camera, controls);
        }
      );
    } else {
      // No model file - show default scene with grids only
      console.log("No model file specified, showing default scene");
      setupDefaultScene(scene, camera, controls);
    }

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
      cleanupModel(scene);
      mount.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, [modelFile, textureFile]);

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

  return (
    <div
      id={id}
      style={{ position: "relative", width: "100%", height: "100%", ...style }}
      ref={mountRef}
    >
      {/* Loading indicator */}
      {isLoading && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            backgroundColor: "rgba(255, 255, 255, 0.9)",
            padding: "20px",
            borderRadius: "8px",
            fontSize: "14px",
            zIndex: 10,
          }}
        >
          Loading 3D model...
        </div>
      )}

      {/* Error message */}
      {loadError && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            backgroundColor: "rgba(255, 200, 200, 0.9)",
            padding: "20px",
            borderRadius: "8px",
            fontSize: "14px",
            color: "#800",
            zIndex: 10,
          }}
        >
          {loadError}
        </div>
      )}

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

ThreeJsOrientation.defaultProps = {
  modelFile: "", // Empty string = no model, just grids
};

ThreeJsOrientation.propTypes = {
  id: PropTypes.string,
  data: PropTypes.string.isRequired,
  activeTime: PropTypes.number.isRequired,
  modelFile: PropTypes.string, // Optional - empty/null shows grids only
  textureFile: PropTypes.string, // Optional texture file (mainly for OBJ)
  style: PropTypes.object,
};

export default ThreeJsOrientation;
