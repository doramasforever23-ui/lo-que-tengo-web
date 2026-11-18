// Utilidades compartidas por todas las páginas: llamadas a la API, barra de navegación, avisos y animaciones.
const $ = (id) => document.getElementById(id);
const getToken = () => localStorage.getItem("token");
const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Llama al backend. Lanza un Error con un mensaje claro para mostrarlo al usuario. */
async function api(metodo, ruta, cuerpo, auth = true) {
  const h = { "Content-Type": "application/json" };
  if (auth && getToken()) h.Authorization = "Bearer " + getToken();
  let r;
  try { r = await fetch(API + ruta, { method: metodo, headers: h, body: cuerpo ? JSON.stringify(cuerpo) : undefined }); }
  catch (e) { throw new Error("No se pudo conectar con el servidor. Si es la primera vez en un rato, espera unos segundos y reintenta."); }
  const d = await r.json().catch(() => ({}));
  if (r.status === 401 && auth) { localStorage.clear(); if (!location.pathname.endsWith("auth.html")) location.href = "auth.html"; }
  if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Revisa los datos e intenta de nuevo.");
  return d;
}

function navbar(activo) {
  const rol = localStorage.getItem("rol"), L = [["index.html", "Inicio", "🏠"], ["catalogo.html", "Catálogo", "🛒"],
    ["app.html", "Mi cocina", "🥗"], ["contacto.html", "Contacto", "✉️"]];
  L.push(getToken() ? (rol === "admin" ? ["admin.html", "Admin", "⚙️"] : ["#salir", "Salir", "👋"]) : ["auth.html", "Entrar", "👤"]);
  const nav = document.createElement("nav");
  nav.className = "nav"; nav.setAttribute("aria-label", "Principal");
  nav.innerHTML = L.map(([h, t, i]) => `<a href="${h}" class="${h === activo ? "on" : ""}">${i} ${t}</a>`).join("");
  nav.querySelector('[href="#salir"]')?.addEventListener("click", (e) => { e.preventDefault(); localStorage.clear(); location.href = "auth.html"; });
  document.body.prepend(nav);
}
function toast(t) { const d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.append(d); setTimeout(() => d.remove(), 2600); }
function revelar() {
  const o = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target.classList.add("vis"), o.unobserve(e.target))), { threshold: 0.1 });
  document.querySelectorAll(".rev").forEach((el) => o.observe(el));
}
/** Tarjeta de producto (la usan el inicio y el catálogo). */
function fotoProducto(p) { return p.imagen ? `<img src="${esc(p.imagen)}" alt="${esc(p.nombre)}" loading="lazy" onerror="this.replaceWith('${esc(p.emoji)}')">` : esc(p.emoji); }
