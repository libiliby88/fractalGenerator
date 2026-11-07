import { defaultVertices, stepPoint } from "./game.js";

const MAX_POINTS = 200000;
const canvas = document.querySelector("#chaos-canvas");
const canvasContainer = document.querySelector("#canvas-container");
const context = canvas.getContext("2d");
const layer = document.createElement("canvas");
const layerContext = layer.getContext("2d");
const vertexCountInput = document.querySelector("#vertex-count");
const vertexCountValue = document.querySelector("#vertex-count-value");
const fractionInput = document.querySelector("#fraction");
const fractionValue = document.querySelector("#fraction-value");
const runButton = document.querySelector("#run-button");
const traversingInput = document.querySelector("#traversing");
const resetButton = document.querySelector("#reset-button");
const nextButton = document.querySelector("#next-button");
const statusElement = document.querySelector("#status");

let vertices = [];
let start = { x: 0.5, y: 0.5 };
let current = { x: 0.5, y: 0.5 };
let points = [];
let running = false;
let animationFrame = null;
let dragTarget = null;
let dragPointerId = null;
let cssSize = 0;
let pixelRatio = 1;

function fraction() {
  return Math.max(0.01, Number(fractionInput.value));
}

function normalizedVertices(count, width, height) {
  return defaultVertices(count, width, height).map((vertex) => ({
    x: vertex.x / width,
    y: vertex.y / height,
    index: vertex.index,
  }));
}

function pointPixels(point) {
  return { x: point.x * cssSize, y: point.y * cssSize };
}

function setupCanvas() {
  const size = canvasContainer.clientWidth;
  if (!size) {
    return;
  }
  cssSize = size;
  pixelRatio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(size * pixelRatio));
  canvas.height = Math.max(1, Math.round(size * pixelRatio));
  layer.width = canvas.width;
  layer.height = canvas.height;
  layerContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  layerContext.clearRect(0, 0, size, size);
  points.forEach((point) => drawPointToLayer(point));
  render();
}

function drawPointToLayer(point) {
  const pixel = pointPixels(point);
  layerContext.beginPath();
  layerContext.fillStyle = "rgba(120,210,255,0.7)";
  layerContext.arc(pixel.x, pixel.y, 1.6, 0, Math.PI * 2);
  layerContext.fill();
}

function render() {
  if (!cssSize) {
    return;
  }
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.clearRect(0, 0, cssSize, cssSize);
  context.drawImage(layer, 0, 0, cssSize, cssSize);

  vertices.forEach((vertex) => {
    const pixel = pointPixels(vertex);
    context.beginPath();
    context.fillStyle = "rgb(255,140,40)";
    context.strokeStyle = "rgb(255,180,80)";
    context.lineWidth = 2;
    context.arc(pixel.x, pixel.y, 10, 0, Math.PI * 2);
    context.fill();
    context.stroke();
    context.fillStyle = "rgb(255,240,220)";
    context.font = "bold 9px Arial";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(String(vertex.index), pixel.x, pixel.y);
  });

  const startPixel = pointPixels(start);
  context.beginPath();
  context.fillStyle = "rgb(70,210,120)";
  context.strokeStyle = "rgb(120,255,160)";
  context.lineWidth = 2;
  context.arc(startPixel.x, startPixel.y, 9, 0, Math.PI * 2);
  context.fill();
  context.stroke();
  context.fillStyle = "rgb(180,255,200)";
  context.font = "9px Arial";
  context.textAlign = "left";
  context.textBaseline = "alphabetic";
  context.fillText("Start", startPixel.x + 12, startPixel.y - 8);

  const currentPixel = pointPixels(current);
  context.beginPath();
  context.fillStyle = "white";
  context.strokeStyle = "white";
  context.lineWidth = 1;
  context.arc(currentPixel.x, currentPixel.y, 4, 0, Math.PI * 2);
  context.fill();
  context.stroke();
}

function updateStatus() {
  const mode = traversingInput.checked ? "step (key press)" : "continuous";
  const state = running ? "running" : "stopped";
  statusElement.textContent = `State: ${state} | Mode: ${mode} | Points: ${points.length}`;
}

function resetPoints() {
  points = [];
  current = { ...start };
  layerContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  layerContext.clearRect(0, 0, cssSize, cssSize);
  render();
  updateStatus();
}

function resetVertices() {
  const count = Number(vertexCountInput.value);
  vertices = normalizedVertices(count, cssSize, cssSize);
  resetPoints();
}

function addPoint() {
  if (points.length >= MAX_POINTS) {
    return;
  }
  const state = { current, vertices, fraction: fraction() };
  current = stepPoint(state);
  points.push({ ...current });
  drawPointToLayer(current);
}

function animate() {
  animationFrame = null;
  if (!running || traversingInput.checked) {
    return;
  }
  for (let count = 0; count < 200; count += 1) {
    addPoint();
  }
  render();
  updateStatus();
  animationFrame = window.requestAnimationFrame(animate);
}

function setRunning(value) {
  running = value;
  runButton.textContent = running ? "Stop" : "Start";
  if (running && !traversingInput.checked && animationFrame === null) {
    animationFrame = window.requestAnimationFrame(animate);
  }
  if (!running && animationFrame !== null) {
    window.cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }
  updateStatus();
}

function setTraversing() {
  if (traversingInput.checked && animationFrame !== null) {
    window.cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }
  nextButton.hidden = !traversingInput.checked;
  if (!traversingInput.checked && running && animationFrame === null) {
    animationFrame = window.requestAnimationFrame(animate);
  }
  updateStatus();
}

function nextStep() {
  if (running && traversingInput.checked) {
    addPoint();
    render();
    updateStatus();
  }
}

function pointerPosition(event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left) / rect.width,
    y: (event.clientY - rect.top) / rect.height,
  };
}

function hitTarget(point) {
  const radius = window.matchMedia("(pointer: coarse)").matches ? 22 : 14;
  const radiusSquared = radius * radius;
  const startPixel = pointPixels(start);
  if ((point.x * cssSize - startPixel.x) ** 2 + (point.y * cssSize - startPixel.y) ** 2 <= radiusSquared) {
    return "start";
  }
  for (let index = 0; index < vertices.length; index += 1) {
    const vertexPixel = pointPixels(vertices[index]);
    if ((point.x * cssSize - vertexPixel.x) ** 2 + (point.y * cssSize - vertexPixel.y) ** 2 <= radiusSquared) {
      return index;
    }
  }
  return null;
}

function updateDrag(point) {
  if (dragTarget === "start") {
    start = {
      x: Math.min(1, Math.max(0, point.x)),
      y: Math.min(1, Math.max(0, point.y)),
    };
    current = { ...start };
  } else if (typeof dragTarget === "number") {
    vertices[dragTarget] = {
      ...vertices[dragTarget],
      x: Math.min(1, Math.max(0, point.x)),
      y: Math.min(1, Math.max(0, point.y)),
    };
  }
  render();
}

canvas.addEventListener("pointerdown", (event) => {
  const point = pointerPosition(event);
  const target = hitTarget(point);
  if (target === null) {
    return;
  }
  dragTarget = target;
  dragPointerId = event.pointerId;
  canvas.setPointerCapture(event.pointerId);
  canvas.classList.add("dragging");
  updateDrag(point);
});
canvas.addEventListener("pointermove", (event) => {
  if (event.pointerId === dragPointerId && dragTarget !== null) {
    updateDrag(pointerPosition(event));
    return;
  }
  canvas.classList.toggle("hover-target", hitTarget(pointerPosition(event)) !== null);
});
canvas.addEventListener("pointerup", (event) => {
  if (event.pointerId === dragPointerId) {
    canvas.releasePointerCapture(event.pointerId);
    dragTarget = null;
    dragPointerId = null;
    canvas.classList.remove("dragging");
  }
});
canvas.addEventListener("pointercancel", () => {
  dragTarget = null;
  dragPointerId = null;
  canvas.classList.remove("dragging");
});

vertexCountInput.addEventListener("input", () => {
  vertexCountValue.textContent = vertexCountInput.value;
  resetVertices();
});
fractionInput.addEventListener("input", () => {
  fractionValue.textContent = fraction().toFixed(2);
  updateStatus();
});
runButton.addEventListener("click", () => setRunning(!running));
traversingInput.addEventListener("change", setTraversing);
resetButton.addEventListener("click", resetPoints);
nextButton.addEventListener("click", nextStep);
window.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    nextStep();
  }
});
window.addEventListener("resize", setupCanvas);
if (typeof ResizeObserver === "function") {
  new ResizeObserver(setupCanvas).observe(canvasContainer);
}

vertexCountValue.textContent = vertexCountInput.value;
fractionValue.textContent = Number(fractionInput.value).toFixed(2);
setupCanvas();
vertices = normalizedVertices(Number(vertexCountInput.value), cssSize, cssSize);
resetPoints();
updateStatus();

if ("serviceWorker" in navigator &&
    (window.isSecureContext || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
