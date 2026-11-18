"""API de «Lo que tengo, lo que como»: FastAPI + MongoDB + pandas.
Ejecutar (desde esta carpeta):  uvicorn main:app --reload   y abrir  http://localhost:8000
"""
import hashlib
import hmac
import json
import os
import random
import smtplib
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import nucleo as N
from datos_iniciales import PRODUCTOS

AQUI = Path(__file__).resolve().parent
SECRETO = os.getenv("JWT_SECRET", "cambia-este-secreto-en-produccion")
BD = N.AlmacenMongo(os.getenv("MONGO_URI")) if os.getenv("MONGO_URI") else N.AlmacenLocal(AQUI / "datos_usuarios.json")
PERFIL0 = {"edad": 30, "sexo": "Mujer", "peso": 68.0, "talla": 168, "act": list(N.ACTIVIDAD)[1], "obj": list(N.OBJETIVO)[1]}
FRONT = AQUI.parent / "frontend"
app = FastAPI(title="Lo que tengo, lo que como")
# CORS: el frontend (GitHub Pages) y el backend (Render) viven en dominios distintos.
# ORIGENES = lista separada por comas con la dirección de tu GitHub Pages (por defecto, todas).
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ORIGENES", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


class Registro(BaseModel):
    usuario: str
    correo: str
    clave: str


class Verificar(BaseModel):
    usuario: str
    codigo: str


class Login(BaseModel):
    usuario: str
    clave: str


class Perfil(BaseModel):
    edad: int
    sexo: str
    peso: float
    talla: int
    act: str
    obj: str


class Nevera(BaseModel):
    nevera: dict  # {alimento: forma de preparación}


class Estado(BaseModel):
    dia: int
    comida: str
    estado: str = ""


# ------------------------------------------------------------ utilidades
def guardar(uid, doc):
    BD.guardar(uid, N.limpio(doc))


def enviar_codigo(correo: str, codigo: str) -> bool:
    host = os.getenv("SMTP_HOST")
    if not host:
        print(f"[MODO PRUEBA] Código de verificación para {correo}: {codigo}")
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = "Tu código de verificación", os.getenv("SMTP_USER"), correo
    msg.set_content(f"Tu código es {codigo}. Vence en 15 minutos.")
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as s:
        s.starttls()
        s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_CLAVE"))
        s.send_message(msg)
    return True


def actual(authorization: str = Header(None)):
    try:
        uid = jwt.decode((authorization or "").replace("Bearer ", "").strip(), SECRETO, algorithms=["HS256"])["sub"]
    except Exception:
        raise HTTPException(401, "Sesión inválida. Vuelve a entrar.")
    doc = BD.obtener(uid)
    if not doc:
        raise HTTPException(401, "Usuario no encontrado.")
    return uid, doc


def necesidades(doc):
    p = doc["perfil"]
    n = N.calcular_necesidades(p["edad"], p["sexo"], p["peso"], p["talla"], p["act"], p["obj"])
    if p["edad"] < 18:
        n["kcal"] = 2000
    return n


def contexto(doc):
    despensa = N.construir_despensa(N.cargar_base(), doc["nevera"])
    return despensa, necesidades(doc)["kcal"], N.calcular_gustos(doc["semanas"])


def plan_semana(uid, doc, forzar=False):
    sem, (despensa, kcal, gustos) = N.clave_semana(), contexto(doc)
    if despensa.empty:
        return None
    viejo = doc["semanas"].get(sem)
    if viejo is None or forzar:
        if viejo and any(v != N.ESTADOS[0] for v in viejo["estados"].values()):
            doc["semanas"][f"{sem}b{len(doc['semanas'])}"] = viejo  # conserva lo que ya marcó
        semilla = random.randint(1, 999) if forzar else 0
        menu = [[N.armar_comida(n, i, semilla, kcal, despensa, gustos) for n in N.REPARTO] for i in range(7)]
        doc["semanas"][sem] = {"menu": menu, "estados": {}, "rechazos": [], "semilla": semilla}
        guardar(uid, doc)
    return doc["semanas"][sem]


def respuesta_menu(doc, plan):
    despensa, _, _ = contexto(doc)
    faltan = [N.GRUPOS[g][0].lower() for g in N.GRUPOS if g not in set(despensa.grupo)]
    menu = [[dict(c, pasos=N.pasos_receta(c), video=N.video_url(c["plato"])) for c in dia] for dia in plan["menu"]]
    return {"semana": N.clave_semana(), "menu": menu, "estados": plan["estados"], "faltan": faltan}


# ------------------------------------------------------------ cuentas
@app.post("/api/registro")
def registro(d: Registro):
    uid = N.norm(d.usuario)
    if len(uid) < 3 or uid.startswith("_") or len(d.clave) < 6 or "@" not in d.correo:
        raise HTTPException(400, "Usuario de 3+ letras, contraseña de 6+ y un correo válido.")
    if BD.obtener(uid):
        raise HTTPException(409, "Ese usuario ya existe.")
    sal, codigo = os.urandom(16).hex(), f"{random.randint(0, 999999):06d}"
    guardar(uid, {"sal": sal, "hash": N.clave_hash(d.clave, sal), "correo": d.correo, "verificado": False,
                  "codigo": hashlib.sha256(codigo.encode()).hexdigest(),
                  "codigo_vence": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
                  "perfil": PERFIL0, "nevera": {}, "semanas": {}})
    enviado = enviar_codigo(d.correo, codigo)
    return {"mensaje": "Te enviamos un código a tu correo." if enviado else "Modo de prueba: no hay correo configurado.",
            "codigo_demo": None if enviado else codigo}


@app.post("/api/verificar")
def verificar(d: Verificar):
    uid = N.norm(d.usuario)
    doc = BD.obtener(uid)
    ok = (doc and doc.get("codigo") and datetime.fromisoformat(doc["codigo_vence"]) > datetime.now(timezone.utc)
          and hmac.compare_digest(doc["codigo"], hashlib.sha256(d.codigo.strip().encode()).hexdigest()))
    if not ok:
        raise HTTPException(400, "Código incorrecto o vencido.")
    doc["verificado"], doc["codigo"] = True, ""
    guardar(uid, doc)
    return {"mensaje": "Cuenta verificada. Ya puedes entrar."}


@app.post("/api/login")
def login(d: Login):
    uid = N.norm(d.usuario)
    doc = BD.obtener(uid)
    if not doc or not hmac.compare_digest(doc["hash"], N.clave_hash(d.clave, doc["sal"])):
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    if not doc.get("verificado"):
        raise HTTPException(403, "Verifica tu correo primero (usa «Ya tengo mi código»).")
    token = jwt.encode({"sub": uid, "exp": datetime.now(timezone.utc) + timedelta(days=7)}, SECRETO, algorithm="HS256")
    return {"token": token, "usuario": uid, "rol": doc.get("rol", "usuario")}


# ------------------------------------------------------------ datos de la app
@app.get("/api/config")
def config():
    return {"grupos": {g: {"nombre": v[0], "color": v[1], "sub": N.SUBTITULO[g]} for g, v in N.GRUPOS.items()},
            "actividad": list(N.ACTIVIDAD), "objetivo": list(N.OBJETIVO), "estados": N.ESTADOS,
            "dias": N.DIAS, "comidas": list(N.REPARTO), "iconos": N.ICONO}


@app.get("/api/alimentos")
def alimentos():
    b = N.cargar_base()
    return [{"alimento": r.alimento, "grupo": r.grupo, "emoji": r.emoji or "🍽️", "cocciones": r.cocciones.split("|")}
            for r in b.itertuples()]


@app.get("/api/yo")
def yo(u=Depends(actual)):
    _, doc = u
    return {"perfil": doc["perfil"], "nevera": doc["nevera"], "necesidades": necesidades(doc)}


@app.put("/api/perfil")
def poner_perfil(p: Perfil, u=Depends(actual)):
    uid, doc = u
    doc["perfil"] = p.model_dump()
    guardar(uid, doc)
    return {"necesidades": necesidades(doc)}


@app.put("/api/nevera")
def poner_nevera(n: Nevera, u=Depends(actual)):
    uid, doc = u
    validos = set(N.cargar_base().alimento)
    doc["nevera"] = {a: str(c) for a, c in n.nevera.items() if a in validos}
    guardar(uid, doc)
    return {"total": len(doc["nevera"])}


@app.get("/api/menu")
def menu(u=Depends(actual)):
    uid, doc = u
    plan = plan_semana(uid, doc)
    return respuesta_menu(doc, plan) if plan else {"menu": None}


@app.post("/api/menu/nuevo")
def menu_nuevo(u=Depends(actual)):
    uid, doc = u
    plan = plan_semana(uid, doc, forzar=True)
    return respuesta_menu(doc, plan) if plan else {"menu": None}


@app.post("/api/estado")
def marcar(e: Estado, u=Depends(actual)):
    uid, doc = u
    plan = plan_semana(uid, doc)
    if not plan or e.estado not in N.ESTADOS or e.comida not in N.REPARTO or not 0 <= e.dia <= 6:
        raise HTTPException(400, "Datos inválidos.")
    plan["estados"][f"{e.dia}|{e.comida}"] = e.estado
    guardar(uid, doc)
    return {"ok": True}


@app.post("/api/cambiar")
def cambiar(e: Estado, u=Depends(actual)):
    uid, doc = u
    plan = plan_semana(uid, doc)
    if not plan or e.comida not in N.REPARTO or not 0 <= e.dia <= 6:
        raise HTTPException(400, "Datos inválidos.")
    despensa, kcal, gustos = contexto(doc)
    i = list(N.REPARTO).index(e.comida)
    plan.setdefault("rechazos", []).extend(x["nombre"] for x in plan["menu"][e.dia][i]["items"])
    plan["menu"][e.dia][i] = N.armar_comida(e.comida, e.dia, random.randint(1, 80), kcal, despensa, gustos)
    plan["estados"][f"{e.dia}|{e.comida}"] = N.ESTADOS[0]
    guardar(uid, doc)
    return respuesta_menu(doc, plan)


@app.get("/api/progreso")
def progreso(u=Depends(actual)):
    _, doc = u
    hechas = lambda w: sum(v == N.ESTADOS[1] for v in w["estados"].values())
    actual_ = doc["semanas"].get(N.clave_semana())
    por_dia = [sum(actual_["estados"].get(f"{i}|{n}") == N.ESTADOS[1] for n in N.REPARTO) if actual_ else 0 for i in range(7)]
    emo = N.cargar_base().set_index("alimento").emoji.to_dict()
    top = sorted(((p, a) for a, p in N.calcular_gustos(doc["semanas"]).items() if p > 0), reverse=True)[:6]
    return {"hechas": hechas(actual_) if actual_ else 0, "total": 28, "por_dia": por_dia,
            "favoritos": [{"alimento": a, "emoji": emo.get(a, "🍽️")} for _, a in top],
            "historial": [{"semana": k, "hechas": hechas(w), "porcentaje": round(100 * hechas(w) / 28)}
                          for k, w in sorted(doc["semanas"].items())]}


# ------------------------------------------------------------ catálogo, contacto y pedidos
# Los datos de la tienda se guardan como documentos especiales («_catalogo», «_mensajes», «_pedidos»).
# Ningún usuario puede llamarse así porque el registro rechaza nombres que empiezan con «_».
class Producto(BaseModel):
    nombre: str
    descripcion: str
    precio: float
    emoji: str = "🍽️"
    imagen: str = ""
    categoria: str = "Cocinar"


class Contacto(BaseModel):
    nombre: str
    correo: str
    mensaje: str


class Pedido(BaseModel):
    nombre: str
    contacto: str
    nota: str = ""
    items: list  # [{"id": ..., "cantidad": ...}]


class Chat(BaseModel):
    mensajes: list  # [{"rol": "user"|"assistant", "texto": ...}]


def leer(clave, campo):
    return (BD.obtener(clave) or {}).get(campo, [])


def poner(clave, campo, lista):
    doc = BD.obtener(clave) or {}
    doc[campo] = lista
    guardar(clave, doc)


def administrador(u=Depends(actual)):
    if u[1].get("rol") != "admin":
        raise HTTPException(403, "Solo para administradores.")
    return u


def sembrar():
    """Crea el catálogo de ejemplo y la cuenta de administrador (variables ADMIN_USER y ADMIN_CLAVE)."""
    if not BD.obtener("_catalogo"):
        poner("_catalogo", "productos", [{"id": uuid.uuid4().hex[:8], "nombre": n, "descripcion": d, "precio": p,
                                          "emoji": e, "imagen": "", "categoria": c} for n, d, p, e, c in PRODUCTOS])
    adm = N.norm(os.getenv("ADMIN_USER", ""))
    if adm and os.getenv("ADMIN_CLAVE") and not BD.obtener(adm):
        sal = os.urandom(16).hex()
        guardar(adm, {"sal": sal, "hash": N.clave_hash(os.getenv("ADMIN_CLAVE"), sal), "correo": "", "verificado": True,
                      "rol": "admin", "perfil": PERFIL0, "nevera": {}, "semanas": {}})


sembrar()


@app.get("/api/productos")
def productos():
    return leer("_catalogo", "productos")


@app.post("/api/admin/productos")
def crear_producto(p: Producto, u=Depends(administrador)):
    lista = leer("_catalogo", "productos")
    lista.append({"id": uuid.uuid4().hex[:8], **p.model_dump()})
    poner("_catalogo", "productos", lista)
    return lista[-1]


@app.put("/api/admin/productos/{pid}")
def editar_producto(pid: str, p: Producto, u=Depends(administrador)):
    lista = leer("_catalogo", "productos")
    for i, x in enumerate(lista):
        if x["id"] == pid:
            lista[i] = {"id": pid, **p.model_dump()}
            poner("_catalogo", "productos", lista)
            return lista[i]
    raise HTTPException(404, "Producto no encontrado.")


@app.delete("/api/admin/productos/{pid}")
def borrar_producto(pid: str, u=Depends(administrador)):
    poner("_catalogo", "productos", [x for x in leer("_catalogo", "productos") if x["id"] != pid])
    return {"ok": True}


@app.post("/api/contacto")
def contacto(c: Contacto):
    if len(c.nombre.strip()) < 2 or "@" not in c.correo or len(c.mensaje.strip()) < 5:
        raise HTTPException(400, "Escribe tu nombre, un correo válido y un mensaje.")
    lista = leer("_mensajes", "items")
    lista.insert(0, {"id": uuid.uuid4().hex[:8], "fecha": datetime.now(timezone.utc).isoformat()[:16],
                     "nombre": c.nombre.strip()[:80], "correo": c.correo.strip()[:120], "mensaje": c.mensaje.strip()[:1500]})
    poner("_mensajes", "items", lista[:300])
    return {"mensaje": "¡Gracias! Recibimos tu mensaje y te responderemos pronto."}


@app.post("/api/pedido")
def pedido(p: Pedido):
    catalogo = {x["id"]: x for x in leer("_catalogo", "productos")}
    lineas = [{"nombre": catalogo[i["id"]]["nombre"], "cantidad": max(1, min(int(i["cantidad"]), 20)),
               "precio": catalogo[i["id"]]["precio"]} for i in p.items if i.get("id") in catalogo]
    if not lineas or len(p.nombre.strip()) < 2 or len(p.contacto.strip()) < 5:
        raise HTTPException(400, "Agrega productos y escribe tu nombre y un contacto (correo o teléfono).")
    lista = leer("_pedidos", "items")
    lista.insert(0, {"id": uuid.uuid4().hex[:8], "fecha": datetime.now(timezone.utc).isoformat()[:16],
                     "nombre": p.nombre.strip()[:80], "contacto": p.contacto.strip()[:120], "nota": p.nota.strip()[:500],
                     "items": lineas, "total": round(sum(l["cantidad"] * l["precio"] for l in lineas), 2)})
    poner("_pedidos", "items", lista[:300])
    return {"mensaje": "¡Pedido recibido! Te contactaremos para coordinar la entrega y el pago."}


@app.get("/api/admin/mensajes")
def ver_mensajes(u=Depends(administrador)):
    return leer("_mensajes", "items")


@app.get("/api/admin/pedidos")
def ver_pedidos(u=Depends(administrador)):
    return leer("_pedidos", "items")


# ------------------------------------------------------------ IA: asistente «Chef Cuchara»
def prompt_sistema(doc) -> str:
    """El asistente conoce la marca, el tono, los productos de la tienda y los alimentos del usuario."""
    prods = "; ".join(f"{p['nombre']} (${p['precio']}): {p['descripcion']}" for p in leer("_catalogo", "productos"))
    nevera = ", ".join(doc["nevera"]) or "todavía no ha registrado alimentos"
    return ("Eres «Chef Cuchara», el asistente de la marca «Lo que tengo, lo que como», una app ecuatoriana que ayuda a "
            "armar comidas equilibradas con lo que hay en casa. Hablas en español, con un tono cálido, cercano y positivo, "
            "frases cortas y sin palabras técnicas. Respondes en máximo 120 palabras. Solo hablas de cocina saludable, "
            "porciones, recetas, la app y los utensilios de la tienda. No diagnosticas ni indicas dietas médicas: si la persona "
            "tiene una enfermedad o es menor de edad, sugiere consultar a su nutricionista o médico. "
            f"Productos de la tienda: {prods}. Alimentos que la persona tiene en casa: {nevera}. "
            "Si recomiendas un utensilio, nómbralo exactamente como está en la tienda y explica en una frase para qué le sirve.")


def llamar_claude(sistema: str, mensajes: list):
    clave = os.getenv("ANTHROPIC_API_KEY")
    if not clave:
        return None
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", method="POST",
        data=json.dumps({"model": os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"), "max_tokens": 400,
                         "system": sistema, "messages": mensajes}).encode(),
        headers={"content-type": "application/json", "x-api-key": clave, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["content"][0]["text"]


def respuesta_basica(texto: str) -> str:
    """Plan B cuando no hay clave de IA: recomienda un producto por palabras clave."""
    t = N.norm(texto)
    for p in leer("_catalogo", "productos"):
        if any(w in t for w in N.norm(p["nombre"]).split() if len(w) > 4):
            return f"Te puede servir: {p['nombre']}. {p['descripcion']}"
    return "Estoy en modo básico (sin IA conectada). Pregúntame por un utensilio, por ejemplo «balanza» o «licuadora»."


@app.post("/api/chat")
def chat(c: Chat, u=Depends(actual)):
    _, doc = u
    msgs = [{"role": "user" if m.get("rol") == "user" else "assistant", "content": str(m.get("texto", ""))[:500]}
            for m in c.mensajes[-8:]]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(400, "Escribe una pregunta.")
    try:
        texto = llamar_claude(prompt_sistema(doc), msgs)
    except Exception:
        raise HTTPException(502, "El asistente no está disponible ahora. Intenta de nuevo en un momento.")
    return {"respuesta": texto or respuesta_basica(msgs[-1]["content"]), "ia": bool(texto)}


if FRONT.exists():  # solo para pruebas locales; en producción el frontend va en GitHub Pages
    app.mount("/", StaticFiles(directory=FRONT, html=True), name="web")
