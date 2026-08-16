(function () {
  const cont = document.getElementById("gantt");
  if (!cont) return;

  const desdeInput = document.getElementById("g-desde");
  const hastaInput = document.getElementById("g-hasta");
  const mulaSelect = document.getElementById("g-mula");

  async function cargar() {
    const res = await fetch(cont.dataset.url);
    const data = await res.json();
    pintar(data);
  }

  function estadoClase(cumplimiento, estado) {
    if (estado === "cancelado" || estado === "anulado") return "bad";
    if (cumplimiento >= 90) return "ok";
    if (cumplimiento >= 70) return "warn";
    return "bad";
  }

  function aMarca(iso) {
    const d = new Date(iso);
    return d.getTime();
  }

  const ESTADOS_LABEL = {
    programado: "Programado",
    realizado: "Realizado",
    cancelado: "Cancelado",
    anulado: "Anulado",
  };

  function estadoTitulo(estado) {
    return ESTADOS_LABEL[estado] || estado;
  }

  function fmtFechahora(iso) {
    return new Date(iso).toLocaleString("es-CO", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function cerrarDetalle() {
    const overlay = document.querySelector(".gantt-overlay");
    if (overlay) overlay.remove();
  }

  function mostrarDetalle(bloque) {
    const b = bloque._data;
    cerrarDetalle();
    const overlay = document.createElement("div");
    overlay.className = "gantt-overlay";
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) cerrarDetalle();
    });

    const panel = document.createElement("div");
    panel.className = "gantt-detail " + estadoClase(b.cumplimiento, b.estado);

    const head = document.createElement("div");
    head.className = "gantt-detail-head";
    const titulo = document.createElement("h3");
    titulo.textContent = "Mula " + b.mula;
    const cerrar = document.createElement("button");
    cerrar.className = "gantt-detail-close";
    cerrar.setAttribute("aria-label", "Cerrar");
    cerrar.textContent = "×";
    cerrar.addEventListener("click", cerrarDetalle);
    head.appendChild(titulo);
    head.appendChild(cerrar);

    const fila = (etiqueta, valor) => {
      const f = document.createElement("div");
      f.className = "gantt-detail-fila";
      const e = document.createElement("span");
      e.className = "gantt-detail-etiqueta";
      e.textContent = etiqueta;
      const v = document.createElement("span");
      v.textContent = valor;
      f.appendChild(e);
      f.appendChild(v);
      return f;
    };

    panel.appendChild(head);
    panel.appendChild(fila("Placa", b.mula));
    panel.appendChild(fila("Inicio", fmtFechahora(b.inicio)));
    panel.appendChild(fila("Fin", fmtFechahora(b.fin)));
    panel.appendChild(
      fila("Duración", b.horas.toLocaleString("es-CO", { maximumFractionDigits: 2 }) + " h")
    );
    panel.appendChild(fila("Cumplimiento", b.cumplimiento + "%"));
    panel.appendChild(fila("Tipo", b.tipo));
    panel.appendChild(fila("Estado", estadoTitulo(b.estado)));
    panel.appendChild(fila("Novedad", b.novedad || "Sin novedades"));

    overlay.appendChild(panel);
    document.body.appendChild(overlay);
  }

  function agregarInteraccion() {
    cont.addEventListener("click", function (e) {
      const bloque = e.target.closest(".gantt-bloque");
      if (bloque && bloque._data) mostrarDetalle(bloque);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") cerrarDetalle();
    });
  }

  function pintar(data) {
    const filas = data.filas;
    const todas = filas.flatMap((f) => f.bloques);
    let min = todas.length ? Math.min(...todas.map((b) => aMarca(b.inicio))) : Date.now() - 86400000;
    let max = todas.length ? Math.max(...todas.map((b) => aMarca(b.fin))) : Date.now();
    if (desdeInput.value) min = aMarca(desdeInput.value + "T00:00:00");
    if (hastaInput.value) max = aMarca(hastaInput.value + "T23:59:59");
    const rango = Math.max(max - min, 3600000);
    const ahora = Date.now();

    cont.innerHTML = "";
    const cab = document.createElement("div");
    cab.className = "gantt-cab";
    const etiqueta = document.createElement("div");
    etiqueta.className = "gantt-etiqueta";
    etiqueta.textContent = "Recurso";
    const regla = document.createElement("div");
    regla.className = "gantt-regla";
    const dias = Math.ceil(rango / 86400000);
    for (let i = 0; i <= dias; i++) {
      const d = document.createElement("span");
      d.textContent = new Date(min + i * 86400000).toLocaleDateString("es-CO", { day: "2-digit", month: "2-digit" });
      regla.appendChild(d);
    }
    cab.appendChild(etiqueta);
    cab.appendChild(regla);
    cont.appendChild(cab);

    filas.filter((f) => !mulaSelect.value || f.placa === mulaSelect.value).forEach((fila) => {
      const row = document.createElement("div");
      row.className = "gantt-fila";
      const et = document.createElement("div");
      et.className = "gantt-etiqueta";
      et.textContent = fila.placa;
      const track = document.createElement("div");
      track.className = "gantt-track";
      fila.bloques.forEach((b) => {
        if (aMarca(b.fin) < min || aMarca(b.inicio) > max) return;
        const block = document.createElement("div");
        block.className = "gantt-bloque " + estadoClase(b.cumplimiento, b.estado);
        block._data = b;
        block.style.left = ((aMarca(b.inicio) - min) / rango * 100) + "%";
        block.style.width = (Math.max((aMarca(b.fin) - aMarca(b.inicio)) / rango * 100, 0.5)) + "%";
        const hora = (ts) => new Date(ts).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
        block.textContent = hora(aMarca(b.inicio)) + "–" + hora(aMarca(b.fin)) + " · " + b.cumplimiento + "%";
        block.title = (b.novedad ? "Novedad: " + b.novedad + "\n" : "") + b.tipo + " · " + b.estado;
        track.appendChild(block);
      });
      if (ahora >= min && ahora <= max) {
        const now = document.createElement("div");
        now.className = "gantt-ahora";
        now.style.left = ((ahora - min) / rango * 100) + "%";
        track.appendChild(now);
      }
      row.appendChild(et);
      row.appendChild(track);
      cont.appendChild(row);
    });
    document.getElementById("gantt-meta-val").textContent = "Meta: " + data.operation.meta_horas + " h";
  }

  function poblarMula(data) {
    const actual = mulaSelect.value;
    mulaSelect.innerHTML = "";
    const todas = document.createElement("option");
    todas.value = "";
    todas.textContent = "Todas";
    mulaSelect.appendChild(todas);
    data.filas.forEach((fila) => {
      const op = document.createElement("option");
      op.value = fila.placa;
      op.textContent = fila.placa;
      mulaSelect.appendChild(op);
    });
    mulaSelect.value = actual;
  }

  async function inicializar() {
    const res = await fetch(cont.dataset.url);
    const data = await res.json();
    poblarMula(data);
    pintar(data);
  }

  agregarInteraccion();

  desdeInput.addEventListener("change", cargar);
  hastaInput.addEventListener("change", cargar);
  mulaSelect.addEventListener("change", cargar);
  inicializar();
})();
