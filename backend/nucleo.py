"""Lógica de menús, cuentas y base de datos (sin interfaz). La usa la API (main.py)."""
import hashlib
import json
from datetime import date
from pathlib import Path
import unicodedata

import pandas as pd

CSV = Path(__file__).with_name("alimentos.csv")
GRUPOS = {"carb": ("Carbohidratos", "#C98F1E"), "prot": ("Proteínas", "#C2503B"),
          "fruit": ("Frutas", "#B23C84"), "veg": ("Vegetales", "#3B8A4C"),
          "fat": ("Grasas saludables", "#3C78AD")}
SUBTITULO = {"carb": "Te dan energía", "prot": "Construyen y reparan tu cuerpo",
             "fruit": "Vitaminas y fibra", "veg": "Vitaminas, minerales y fibra", "fat": "Energía y vitaminas"}
COCCION_KCAL = {"crudo": 0, "tal cual": 0, "hervido": 0, "al vapor": 0, "tostado": 0,
                "a la plancha": 20, "al horno": 20, "revuelto": 30, "salteado": 45, "frito": 110}
NEUTRO = {"tal cual", "crudo"}
PASOS = {
    "hervido": "hierve en agua con una pizca de sal hasta que esté tierno y escurre",
    "al vapor": "cuece al vapor, tapado, sobre una olla con agua hirviendo hasta que esté suave",
    "al horno": "coloca en una bandeja con unas gotas de aceite y hornea a 180 °C hasta que dore",
    "a la plancha": "cocina en una sartén con unas gotas de aceite por ambos lados hasta que dore",
    "salteado": "saltea en una sartén con poco aceite a fuego medio moviendo seguido",
    "frito": "fríe en aceite caliente hasta que dore y escurre sobre papel (es lo que más calorías suma: úsalo poco)",
    "revuelto": "bate con una pizca de sal y cocina en una sartén con poco aceite",
    "crudo": "lava bien y corta o sirve entero",
    "tal cual": "sirve tal como está",
    "tostado": "tuesta en la tostadora o en una sartén sin aceite"}
ACTIVIDAD = {"Sedentaria (casi sin ejercicio)": 1.2, "Ligera (1 a 3 días por semana)": 1.375,
             "Moderada (3 a 5 días por semana)": 1.55, "Alta (6 a 7 días por semana)": 1.725}
OBJETIVO = {"Bajar de peso": -0.15, "Mantener mi peso": 0.0, "Ganar masa o peso": 0.10}
REPARTO = {"Desayuno": .25, "Almuerzo": .35, "Merienda": .10, "Cena": .30}
ICONO = {"Desayuno": "🌅", "Almuerzo": "☀️", "Merienda": "🍎", "Cena": "🌙"}
RECETA = {"Desayuno": {"carb": .40, "prot": .35, "fruit": .25},
          "Almuerzo": {"carb": .38, "prot": .32, "veg": .15, "fat": .15},
          "Merienda": {"fruit": .60, "fat": .40},
          "Cena": {"carb": .38, "prot": .32, "veg": .15, "fat": .15}}
DESAYUNO = {"Avena", "Huevo", "Pan integral", "Verde", "Maduro", "Choclo", "Queso fresco", "Yogur natural", "Leche"}
SOLO_DESAYUNO = {"Avena", "Yogur natural", "Leche"}
LEGUMBRES = {"Lentejas", "Frejol", "Garbanzo", "Chochos", "Habas"}
ESTADOS = ["Pendiente", "✅ Lo hice", "❌ No lo hice"]
PERFIL_KEYS = ["p_edad", "p_sexo", "p_peso", "p_talla", "p_act", "p_obj"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
KCAL_GRUPO = {"carb": 130, "prot": 150, "fruit": 50, "veg": 30, "fat": 300}
MEDIDA_GRUPO = {"carb": ("taza|tazas", 150), "prot": ("porción|porciones", 100),
                "fruit": ("unidad mediana|unidades medianas", 120), "veg": ("taza|tazas", 90),
                "fat": ("cucharada|cucharadas", 12)}
COCC_GRUPO = {"carb": "tal cual|hervido|al horno|a la plancha|salteado|frito",
              "prot": "tal cual|hervido|al horno|a la plancha|salteado|frito",
              "veg": "crudo|hervido|al vapor|salteado", "fruit": "crudo", "fat": "tal cual"}
PALABRAS = {  # para adivinar el grupo de un alimento nuevo solo por su nombre
    "prot": ["carne", "pollo", "pescado", "queso", "huevo", "jamon", "salchicha", "atun", "chancho", "pavo", "pato",
             "soya", "leche", "yogur", "calamar", "mariscos", "concha", "cangrejo", "trucha", "tilapia", "higado",
             "frejol", "lenteja", "arveja seca", "res", "cerdo", "cuy", "conejo", "requeson"],
    "carb": ["pan", "arroz", "papa", "fideo", "harina", "galleta", "cereal", "maiz", "trigo", "yuca", "platano",
             "tortilla", "pasta", "avena", "machica", "morocho", "quinua", "cebada", "camote", "tallarin", "granola"],
    "fruit": ["fruta", "mora", "fresa", "durazno", "uva", "melon", "granadilla", "sandia", "pera", "manzana",
              "limon", "naranja", "mandarina", "kiwi", "cereza", "ciruela", "coco", "frutilla", "chirimoya", "pitahaya"],
    "veg": ["lechuga", "col", "acelga", "zapallo", "pepino", "verdura", "tomate", "cebolla", "ajo", "pimiento",
            "espinaca", "apio", "rabano", "nabo", "alcachofa", "champi", "hongo", "esparrago", "brocoli", "ensalada"],
    "fat": ["aceite", "mantequilla", "nuez", "almendra", "mani", "semilla", "aguacate", "pepa", "margarina"]}


def norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()



def nombre_de(label: str) -> str:
    return label.split(" ", 1)[1] if " " in label else label



class AlmacenLocal:
    """Guarda los usuarios en un archivo JSON (modo de prueba, sin MongoDB)."""

    def __init__(self, ruta):
        self.ruta = Path(ruta)

    def _leer(self):
        return json.loads(self.ruta.read_text("utf-8")) if self.ruta.exists() else {}

    def obtener(self, uid):
        return self._leer().get(uid)

    def guardar(self, uid, doc):
        datos = self._leer()
        datos[uid] = doc
        self.ruta.write_text(json.dumps(datos, ensure_ascii=False), "utf-8")



class AlmacenMongo:
    """Guarda los usuarios en MongoDB (colección 'usuarios')."""

    def __init__(self, uri):
        from pymongo import MongoClient
        cliente = MongoClient(uri, serverSelectionTimeoutMS=5000)
        cliente.admin.command("ping")
        self.col = cliente["lo_que_tengo"]["usuarios"]

    def obtener(self, uid):
        return self.col.find_one({"_id": uid})

    def guardar(self, uid, doc):
        self.col.replace_one({"_id": uid}, {**doc, "_id": uid}, upsert=True)



def _conv(o):
    return o.item() if hasattr(o, "item") else str(o)



def limpio(doc: dict) -> dict:
    """Convierte números de numpy a números normales para poder guardar."""
    return json.loads(json.dumps(doc, default=_conv))



def clave_hash(clave: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), 200_000).hex()



def clave_semana() -> str:
    y, w, _ = date.today().isocalendar()
    return f"{y}-S{w:02d}"



def calcular_gustos(semanas: dict) -> dict:
    """Puntos por alimento: +2 si comió esa comida, -1 si no la hizo, -1 por cada comida que cambió."""
    pts = {}
    for sem in semanas.values():
        for dia, comidas in enumerate(sem["menu"]):
            for c in comidas:
                e = sem["estados"].get(f"{dia}|{c['nombre']}", ESTADOS[0])
                v = 2 if e == ESTADOS[1] else (-1 if e == ESTADOS[2] else 0)
                for it in c["items"]:
                    pts[it["nombre"]] = pts.get(it["nombre"], 0) + v
        for a in sem.get("rechazos", []):
            pts[a] = pts.get(a, 0) - 1
    return pts



def ponderar(sub: pd.DataFrame, gustos: dict) -> pd.DataFrame:
    """Los alimentos que más le gustan aparecen más veces; los muy rechazados casi no."""
    pts = sub.alimento.map(lambda a: gustos.get(a, 0))
    if (pts > -3).any():
        sub, pts = sub[pts > -3], pts[pts > -3]
    return sub.loc[sub.index.repeat((1 + pts.clip(0, 3)).astype(int))]



def calcular_necesidades(edad, sexo, peso, talla, actividad, objetivo) -> dict:
    bmr = 10 * peso + 6.25 * talla - 5 * edad + (5 if sexo == "Hombre" else -161)
    kcal = max(round(bmr * ACTIVIDAD[actividad] * (1 + OBJETIVO[objetivo])), 1500 if sexo == "Hombre" else 1200)
    prot = round(peso * (1.6 if OBJETIVO[objetivo] > 0 else 1.2))
    grasa = round(kcal * 0.28 / 9)
    carb = round((kcal - prot * 4 - grasa * 9) / 4)
    return {"kcal": kcal, "prot": prot, "carb": carb, "grasa": grasa, "agua": round(peso * 0.035, 1)}



def cantidad(n: float) -> str:
    e = int(n)
    return "½" if e == 0 else (f"{e} ½" if n - e >= 0.5 else str(e))



def adjetivo(alimento: str, coccion: str) -> str:
    if alimento == "Carne de res" and coccion.endswith("o") and not coccion.startswith("al "):
        return coccion[:-1] + "a"
    return coccion



def con_coccion(f) -> str:
    return f.alimento if f.coccion in NEUTRO else f"{f.alimento} {adjetivo(f.alimento, f.coccion)}"



def nombre_plato(comida: str, e: dict) -> str:
    p, c, v, f, fa = (e.get(k) for k in ("prot", "carb", "veg", "fruit", "fat"))
    cap = lambda s: s[:1].upper() + s[1:]
    if comida == "Merienda":
        return cap(" con ".join(x.alimento.lower() for x in (f, fa) if x is not None)) or "Fruta"
    partes = []
    if p is not None and p.alimento in LEGUMBRES:
        partes.append(f"Guiso de {p.alimento.lower()}")
    elif p is not None:
        partes.append(con_coccion(p))
    if c is not None:
        partes.append(("con " if partes else "") + c.alimento.lower())
    if v is not None:
        partes.append(("y ensalada de " if partes else "Ensalada de ") + v.alimento.lower())
    if f is not None:
        partes.append(("y " if partes else "") + f.alimento.lower())
    return cap(" ".join(partes))



def armar_comida(nombre: str, dia: int, semilla: int, kcal_dia: int, despensa: pd.DataFrame, gustos=None) -> dict:
    meta = kcal_dia * REPARTO[nombre]
    escogidos, items = {}, []
    for i, (grupo, parte) in enumerate(RECETA[nombre].items()):
        sub = despensa[despensa.grupo == grupo] if len(despensa) else despensa
        if sub.empty:
            continue
        if nombre == "Desayuno":
            pref = sub[sub.alimento.isin(DESAYUNO)]
            sub = pref if len(pref) else sub
        elif nombre == "Merienda":
            sub = sub[sub.alimento != "Aceite de oliva"]
        else:
            otros = sub[~sub.alimento.isin(SOLO_DESAYUNO)]
            sub = otros if len(otros) else sub
        if sub.empty:
            continue
        if gustos:
            sub = ponderar(sub, gustos)
        f = sub.iloc[(dia + semilla + i + len(nombre)) % len(sub)]
        kcal_medida = f.kcal_ef * f.g_medida / 100
        if grupo == "fat" or f.alimento == "Huevo":
            n = min(max(round(meta * parte / kcal_medida), 1), 2 if grupo == "fat" else 3)
        else:
            lo, hi = (1, 2) if grupo == "veg" else (0.5, 3)
            n = min(max(round(meta * parte / kcal_medida * 2) / 2, lo), hi)
        sing, plur = f.medida.split("|")
        medida = sing if n <= 1 else plur
        texto = f"{cantidad(n)} {medida}" if sing.lower() == f.alimento.lower() else f"{cantidad(n)} {medida} de {f.alimento.lower()}"
        if f.coccion not in NEUTRO:
            texto += f" ({f.coccion})"
        items.append({"texto": texto, "kcal": round(n * kcal_medida), "gramos": round(n * f.g_medida / 5) * 5,
                      "color": GRUPOS[grupo][1], "nombre": f.alimento, "emoji": f.emoji or "🍽️",
                      "previo": f.previo, "tip": f.tip, "coccion": f.coccion})
        escogidos[grupo] = f
    return {"nombre": nombre, "plato": nombre_plato(nombre, escogidos) if escogidos else "",
            "items": items, "kcal": sum(x["kcal"] for x in items), "meta": round(meta)}



def pasos_receta(c: dict) -> list:
    pasos = [f"**{it['nombre']}:** {it['previo']}." for it in c["items"] if it["previo"]]
    for it in c["items"]:
        if it["coccion"] in PASOS and it["coccion"] not in ("tal cual",):
            pasos.append(f"**{it['nombre']}:** {PASOS[it['coccion']]}.")
    pasos.append("Sirve todo junto en un plato siguiendo la cuchara: la mitad con vegetales y frutas, "
                 "un cuarto con carbohidratos y un cuarto con proteínas. ¡Buen provecho!")
    return pasos



def cargar_base() -> pd.DataFrame:
    return pd.read_csv(CSV).fillna("")


def construir_despensa(base: pd.DataFrame, nevera: dict) -> pd.DataFrame:
    """nevera = {alimento: forma de preparación}."""
    filas = []
    for nombre, coc in nevera.items():
        r = base[base.alimento == nombre]
        if r.empty:
            continue
        f = r.iloc[0].copy()
        ops = f.cocciones.split("|")
        f["coccion"] = coc if coc in ops else ops[0]
        f["kcal_ef"] = f.kcal_100g + COCCION_KCAL.get(f.coccion, 0)
        filas.append(f)
    return pd.DataFrame(filas)


def video_url(plato: str) -> str:
    """Enlace a una búsqueda de YouTube con la receta (siempre válido; no depende de un video fijo)."""
    from urllib.parse import quote_plus
    return "https://www.youtube.com/results?search_query=" + quote_plus(f"cómo preparar {plato} receta fácil")
