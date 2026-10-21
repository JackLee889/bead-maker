// All viewing operations stay in this browser; no rerun, image conversion or request.
export default function({data, parentElement}) {
  const root = document.createElement("div");
  root.className = "bead-grid-viewer";
  // Only static markup is HTML. Translations and image bytes are assigned as data.
  root.innerHTML = `
    <button type="button" class="open-viewer" disabled></button>
    <button type="button" class="preview" disabled><img draggable="false"></button>
    <dialog class="viewer" aria-labelledby="grid-viewer-title">
      <div class="toolbar">
        <h2 class="title" id="grid-viewer-title"></h2>
        <div class="controls">
          <button type="button" data-action="out">−</button>
          <output class="scale" aria-live="polite"></output>
          <button type="button" data-action="in">＋</button>
          <button type="button" data-action="fit"></button>
          <button type="button" data-action="actual"></button>
        </div>
        <button type="button" data-action="close"></button>
      </div>
      <div class="stage" tabindex="0" role="region"><img class="detail" draggable="false"></div>
      <p class="hint"></p>
    </dialog>`;
  parentElement.append(root);
  const get = selector => root.querySelector(selector);
  const dialog = get(".viewer");
  const stage = get(".stage");
  const detail = get(".detail");
  const preview = get(".preview img");
  const openButton = get(".open-viewer");
  const previewButton = get(".preview");
  const labels = data.labels;
  openButton.textContent = labels.open;
  previewButton.setAttribute("aria-label", labels.open);
  get(".title").textContent = labels.title;
  get(".hint").textContent = labels.hint;
  stage.setAttribute("aria-label", labels.title);
  detail.alt = preview.alt = labels.title;
  for (const action of ["in", "out", "fit", "actual", "close"]) {
    const button = get(`[data-action="${action}"]`);
    button.setAttribute("aria-label", labels[action]);
    if (action !== "in" && action !== "out") button.textContent = labels[action];
  }

  const controller = new AbortController();
  const on = (element, type, handler, options = {}) => element.addEventListener(type, handler, {signal:controller.signal, ...options});
  let scale = 1, x = 0, y = 0, fitted = true, drag = null;
  const dimensions = () => [preview.naturalWidth, preview.naturalHeight];
  const fitScale = () => {
    const [width, height] = dimensions();
    return Math.min(1, stage.clientWidth / width, stage.clientHeight / height);
  };
  const minScale = () => Math.min(fitScale(), .1);
  const clampPosition = (position, imageSize, viewport) => imageSize <= viewport
    ? (viewport - imageSize) / 2 : Math.max(viewport - imageSize, Math.min(0, position));
  const paint = () => {
    const [width, height] = dimensions();
    x = clampPosition(x, width * scale, stage.clientWidth);
    y = clampPosition(y, height * scale, stage.clientHeight);
    detail.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
    get(".scale").textContent = `${Math.round(scale * 100)}%`;
    get('[data-action="out"]').disabled = scale <= minScale() + .0001;
    get('[data-action="in"]').disabled = scale >= 4;
  };
  const fit = () => {
    fitted = true;
    scale = fitScale();
    const [width, height] = dimensions();
    x = (stage.clientWidth - width * scale) / 2;
    y = (stage.clientHeight - height * scale) / 2;
    paint();
  };
  const zoom = (next, anchorX = stage.clientWidth / 2, anchorY = stage.clientHeight / 2) => {
    fitted = false;
    next = Math.max(minScale(), Math.min(4, next));
    x = anchorX - (anchorX - x) * next / scale;
    y = anchorY - (anchorY - y) * next / scale;
    scale = next;
    paint();
  };
  const open = () => {
    if (!preview.naturalWidth || dialog.open) return;
    dialog.showModal();
    fit();
    stage.focus({preventScroll:true});
  };
  const ready = () => {
    openButton.disabled = previewButton.disabled = false;
    if (dialog.open) fit();
  };
  on(preview, "load", ready);
  detail.src = preview.src = data.image;
  if (preview.complete && preview.naturalWidth) ready();
  on(openButton, "click", open);
  on(previewButton, "click", open);
  on(get('[data-action="in"]'), "click", () => zoom(scale * 1.4));
  on(get('[data-action="out"]'), "click", () => zoom(scale / 1.4));
  on(get('[data-action="fit"]'), "click", fit);
  on(get('[data-action="actual"]'), "click", () => zoom(1));
  on(get('[data-action="close"]'), "click", () => dialog.close());
  on(dialog, "close", () => { drag = null; stage.classList.remove("dragging"); });
  on(stage, "wheel", event => {
    event.preventDefault();
    const bounds = stage.getBoundingClientRect();
    zoom(scale * (event.deltaY < 0 ? 1.2 : 1 / 1.2), event.clientX - bounds.left, event.clientY - bounds.top);
  }, {passive:false});
  on(stage, "pointerdown", event => {
    if (event.button !== 0 || drag) return;
    drag = {id:event.pointerId, x:event.clientX, y:event.clientY};
    stage.setPointerCapture(event.pointerId);
    stage.classList.add("dragging");
    stage.focus({preventScroll:true});
  });
  on(stage, "pointermove", event => {
    if (!drag || event.pointerId !== drag.id) return;
    x += event.clientX - drag.x;
    y += event.clientY - drag.y;
    drag.x = event.clientX;
    drag.y = event.clientY;
    paint();
  });
  const endDrag = event => {
    if (!drag || event.pointerId !== drag.id) return;
    drag = null;
    stage.classList.remove("dragging");
  };
  on(stage, "pointerup", endDrag);
  on(stage, "pointercancel", endDrag);
  on(stage, "lostpointercapture", endDrag);
  on(stage, "keydown", event => {
    if (["+", "=", "-", "0", "1", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) event.preventDefault();
    if (event.key === "+" || event.key === "=") zoom(scale * 1.4);
    if (event.key === "-") zoom(scale / 1.4);
    if (event.key === "0") fit();
    if (event.key === "1") zoom(1);
    if (event.key.startsWith("Arrow")) {
      x += event.key === "ArrowLeft" ? 80 : event.key === "ArrowRight" ? -80 : 0;
      y += event.key === "ArrowUp" ? 80 : event.key === "ArrowDown" ? -80 : 0;
      paint();
    }
  });
  const resize = new ResizeObserver(() => {
    if (dialog.open) fitted ? fit() : paint();
  });
  resize.observe(stage);
  return () => {
    controller.abort();
    resize.disconnect();
    if (dialog.open) dialog.close();
    root.remove();
  };
}
