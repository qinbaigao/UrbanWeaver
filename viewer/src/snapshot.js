// Keep the current viewport composition; never force a 16:9 crop.
export function snapshotSize(width, height, longEdge = 2560, maxDimension = 8192) {
  if (![width, height, longEdge, maxDimension].every(v => Number.isFinite(v) && v > 0)) {
    throw new Error('Invalid screenshot dimensions');
  }
  const scale = Math.min(longEdge / Math.max(width, height),
    maxDimension / Math.max(width, height), Math.sqrt(8388608 / (width * height)));
  return {width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale))};
}

export function canvasPng(canvas) {
  return new Promise((resolve, reject) => canvas.toBlob(blob =>
    blob ? resolve(blob) : reject(new Error('PNG encoding failed; try a smaller output')), 'image/png'));
}
