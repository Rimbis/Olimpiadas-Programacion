// Dirección del backend (uvicorn). Cambiala cuando lo subas a producción.
// Dirección del backend (uvicorn). Cambiala cuando lo subas a producción.
const API_URL = (location.hostname === "localhost" || location.hostname === "127.0.0.1")
    ? "http://localhost:8000"                  // desarrollo (PC)
    : "https://aeroplate-backend.onrender.com"; // producción (Render)

/* Sesión (token y rol guardados en el navegador) */
function getToken() {
    return localStorage.getItem("token");
}

function getRol() {
    return localStorage.getItem("rol"); // "cliente", "ventas" o "jefe_ventas"
}

function esAdmin() {
    return getRol() === "ventas" || getRol() === "jefe_ventas";
}

function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("rol");
}

/* Pedido genérico a la API */
async function apiFetch(ruta, opciones = {}) {
    const headers = { "Content-Type": "application/json", ...(opciones.headers || {}) };
    if (getToken()) headers.Authorization = `Bearer ${getToken()}`;

    const res = await fetch(`${API_URL}${ruta}`, { ...opciones, headers });

    if (res.status === 401) {
        logout(); // La sesión venció o inexistente.
        throw new Error("No autorizado");
    }
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        // En errores de validación de FastAPI, detail es un array
        const msg = Array.isArray(err.detail) ? err.detail[0].msg : err.detail;
        throw new Error(msg || `Error ${res.status}`);
    }
    return res.json();
}

/* Auth */
async function login(email, password) {
    const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Credenciales incorrectas");
    }
    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("rol", data.rol);
    return data;
}

async function registrar({ nombre, apellido, email, password }) {
    const res = await fetch(`${API_URL}/auth/registro`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre, apellido, email, password }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = Array.isArray(err.detail) ? err.detail[0].msg : err.detail;
        throw new Error(msg || "No se pudo crear la cuenta");
    }
    return res.json(); 
}

// Devuelve los datos del usuario si el token guardado sigue siendo válido, o un null
async function iniciarSesionGuardada() {
    if (!getToken()) return null;
    try {
        return await apiFetch("/auth/me");
    } catch {
        return null;
    }
}

/* Catálogo y compras  */
function crearPaquete(datos) {
    return apiFetch("/paquetes", { method: "POST", body: JSON.stringify(datos) });
}

function crearCompra(compra) {
    return apiFetch("/compras", { method: "POST", body: JSON.stringify(compra) });
}

function misPedidos() {
    return apiFetch("/compras");
}

function cancelarPedido(id) {
    return apiFetch(`/compras/${id}`, { method: "DELETE" });
}

/* Carrito (se guarda en el navegador hasta confirmar la compra) */
function getCarrito() {
    try { return JSON.parse(localStorage.getItem("carrito")) || []; } catch { return []; }
}
 
function guardarCarrito(carrito) {
    localStorage.setItem("carrito", JSON.stringify(carrito));
}
 
// Devuelve false si ya estaba seleccionado.
function agregarAlCarrito(p) {
    const carrito = getCarrito();
    if (carrito.some((x) => x.id === p.id)) return false;
    carrito.push({ id: p.id, titulo: p.titulo, precio_total: p.precio_total, cantidad_noches: p.cantidad_noches, pasajeros: [] });
    guardarCarrito(carrito);
    return true;
}
