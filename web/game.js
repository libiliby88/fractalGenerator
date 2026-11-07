export function defaultVertices(count, width, height, margin = 60) {
  const cx = width / 2;
  const cy = height / 2;
  const rx = (width - 2 * margin) / 2;
  const ry = (height - 2 * margin) / 2;
  return Array.from({ length: count }, (_, index) => {
    const angle = (2 * Math.PI * index) / count - Math.PI / 2;
    return {
      x: cx + rx * Math.cos(angle),
      y: cy + ry * Math.sin(angle),
      index: index + 1,
    };
  });
}

export function lerpPoint(current, target, fraction) {
  return {
    x: current.x + (target.x - current.x) * fraction,
    y: current.y + (target.y - current.y) * fraction,
  };
}

export function stepPoint(state, rng = Math.random) {
  const vertex = state.vertices[Math.floor(rng() * state.vertices.length)];
  return lerpPoint(state.current, vertex, state.fraction);
}
