// Small helpers shared by the media pages.
// lead(from, to): a hairline from a real feature (projected anchor) to its label.
window.lead = function (from, to) {
  const line = document.createElement('div');
  line.className = 'leader';
  const dx = to[0] - from[0], dy = to[1] - from[1];
  Object.assign(line.style, { left: from[0] + 'px', top: from[1] + 'px', width: Math.hypot(dx, dy) + 'px',
                              transform: `rotate(${Math.atan2(dy, dx)}rad)` });
  document.body.appendChild(line);
};
// Anchors are in the render's CSS pixels; offset them by where the image sits.
window.at = function (anchor, image) {
  const box = document.querySelector(image);
  return [anchor[0] + box.offsetLeft, anchor[1] + box.offsetTop];
};
