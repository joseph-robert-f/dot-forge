// Draws the sheet frame, zone markers and title block for every media page.
// Reads data-title and data-sheet from <body>.
(function () {
  const b = document.body;
  const W = b.clientWidth, H = b.clientHeight;
  const frame = document.createElement('div');
  frame.className = 'frame';
  frame.innerHTML = '<div class="frame-inner"></div>';
  b.appendChild(frame);
  const add = (cls, text, style) => {
    const e = document.createElement('div');
    e.className = cls; if (text) e.textContent = text; Object.assign(e.style, style);
    frame.appendChild(e);
  };
  const cols = Math.round(W / 160), rows = Math.max(3, Math.round(H / 160));
  const iw = W - 24, ih = H - 24;
  for (let i = 0; i < cols; i++) {
    const x = (iw / cols) * (i + 0.5) - 6;
    add('zone t', String(cols - i), { left: x + 'px' });
    add('zone b', String(cols - i), { left: x + 'px' });
    if (i) {
      add('tick', '', { left: (iw / cols) * i + 'px', top: 0, width: '1px', height: '14px' });
      add('tick', '', { left: (iw / cols) * i + 'px', bottom: 0, width: '1px', height: '14px' });
    }
  }
  for (let j = 0; j < rows; j++) {
    const y = (ih / rows) * (j + 0.5) - 6;
    add('zone l', 'ABCDEFGH'[j], { top: y + 'px' });
    add('zone r', 'ABCDEFGH'[j], { top: y + 'px' });
    if (j) {
      add('tick', '', { top: (ih / rows) * j + 'px', left: 0, height: '1px', width: '14px' });
      add('tick', '', { top: (ih / rows) * j + 'px', right: 0, height: '1px', width: '14px' });
    }
  }
  if (b.dataset.title) {
    const t = document.createElement('div');
    t.className = 'tblock';
    t.innerHTML =
      '<div><svg class="mark" viewBox="0 0 22 22" aria-hidden="true"><line x1="11" y1="0" x2="11" y2="22"/><line x1="0" y1="11" x2="22" y2="11"/><circle cx="11" cy="11" r="6"/></svg><span class="brand">Dot Forge</span></div>' +
      '<div><small>Title</small><b>' + b.dataset.title + '</b></div>' +
      '<div><small>Units</small><b>mm</b></div>' +
      '<div><small>Rev</small><b>1.02</b></div>' +
      '<div><small>Sheet</small><b>' + b.dataset.sheet + '</b></div>';
    b.appendChild(t);
  }
})();
