import { defaultVertices, lerpPoint, stepPoint } from "./game.js";

const results = document.querySelector("#results");
const summary = document.querySelector("#summary");
let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function closeEnough(actual, expected) {
  return Math.abs(actual - expected) < 1e-9;
}

function test(name, callback) {
  const item = document.createElement("li");
  try {
    callback();
    passed += 1;
    item.className = "pass";
    item.textContent = `PASS: ${name}`;
  } catch (error) {
    failed += 1;
    item.className = "fail";
    item.textContent = `FAIL: ${name} — ${error.message}`;
  }
  results.append(item);
}

test("defaultVertices creates the requested count", () => {
  const vertices = defaultVertices(5, 500, 400);
  assert(vertices.length === 5, "expected five vertices");
  assert(vertices[0].index === 1 && vertices[4].index === 5, "indices should start at one");
});

test("the first triangle vertex is at top centre", () => {
  const vertices = defaultVertices(3, 500, 400);
  assert(closeEnough(vertices[0].x, 250), "x should be the centre");
  assert(closeEnough(vertices[0].y, 60), "y should be cy minus ry");
});

test("lerpPoint handles zero and one", () => {
  const current = { x: 2, y: 4 };
  const target = { x: 10, y: 12 };
  assert(JSON.stringify(lerpPoint(current, target, 0)) === JSON.stringify(current), "fraction zero");
  assert(JSON.stringify(lerpPoint(current, target, 1)) === JSON.stringify(target), "fraction one");
});

test("lerpPoint handles fraction 0.75", () => {
  const result = lerpPoint({ x: 0, y: 4 }, { x: 8, y: 12 }, 0.75);
  assert(result.x === 6 && result.y === 10, "fraction should interpolate");
});

test("stepPoint is deterministic with a stubbed rng", () => {
  const state = {
    current: { x: 0, y: 0 },
    vertices: [{ x: 10, y: 0, index: 1 }, { x: 0, y: 10, index: 2 }],
    fraction: 0.5,
  };
  const result = stepPoint(state, () => 0.75);
  assert(result.x === 0 && result.y === 5, "rng should choose the second vertex");
});

test("stubbed rng covers every vertex uniformly", () => {
  const state = {
    current: { x: 0, y: 0 },
    vertices: [
      { x: 1, y: 0, index: 1 },
      { x: 2, y: 0, index: 2 },
      { x: 3, y: 0, index: 3 },
      { x: 4, y: 0, index: 4 },
    ],
    fraction: 1,
  };
  const counts = [0, 0, 0, 0];
  for (let index = 0; index < 40; index += 1) {
    const value = stepPoint(state, () => (index % 4) / 4);
    counts[value.x - 1] += 1;
  }
  assert(JSON.stringify(counts) === JSON.stringify([10, 10, 10, 10]), "coverage should be uniform");
});

test("fraction greater than one overshoots the target", () => {
  const result = lerpPoint({ x: 2, y: 2 }, { x: 6, y: 10 }, 1.5);
  assert(result.x === 8 && result.y === 14, "fraction should overshoot");
});

summary.textContent = `${passed} passed, ${failed} failed`;
summary.className = failed ? "fail" : "pass";
console.log(`${passed} passed, ${failed} failed`);
