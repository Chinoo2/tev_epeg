import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_URL = "https://plagtv.herokuapp.com/api/v1"

ENDPOINT = f"{BASE_URL}/tenants"

CARPETA = Path(__file__).resolve().parent

ARCHIVO_EPG = CARPETA / "tev_epg.xml"

# Zona horaria de Todo En Vivo / Montevideo
TIMEZONE_OFFSET = "-0300"

# Cuántos días hacia adelante conservar
DIAS_FUTUROS = 7

# Subdominio de Todo En Vivo
SUBDOMAIN = "todoenvivo"


# ============================================================
# OBTENER DATOS DE LA API
# ============================================================

def obtener_datos():

    print()
    print("=" * 60)
    print("      TODO EN VIVO - GENERADOR DE EPG")
    print("=" * 60)

    print()
    print("Consultando API:")
    print(ENDPOINT)

    # --------------------------------------------------------
    # HEADERS
    # --------------------------------------------------------

    headers = {

        "Accept":
            "application/json",

        "Accept-Language":
            "es-UY,es;q=0.9",

        "Content-Type":
            "application/json",

        "Origin":
            "https://todoenvivo.plag.tv",

        "Referer":
            "https://todoenvivo.plag.tv/",

        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/150.0.0.0 "
            "Safari/537.36"
        ),

        # IMPORTANTE
        # La API necesita saber qué tenant consultar.
        "subdomain":
            SUBDOMAIN,
    }

    try:

        response = requests.get(
            ENDPOINT,
            headers=headers,
            timeout=30
        )

    except requests.RequestException as error:

        print()
        print("ERROR DE CONEXIÓN:")
        print(error)

        return None

    print()
    print(
        f"HTTP {response.status_code}"
    )

    if response.status_code != 200:

        print()
        print(
            "ERROR: la API no devolvió HTTP 200."
        )

        print()
        print(
            response.text[:1000]
        )

        return None

    try:

        data = response.json()

    except ValueError:

        print()
        print(
            "ERROR: la respuesta no es JSON válido."
        )

        return None

    print()
    print(
        "Datos recibidos correctamente."
    )

    return data


# ============================================================
# CONVERTIR FECHA DE LA API
# ============================================================

def convertir_fecha(fecha):

    if not fecha:
        return None

    try:

        # Ejemplo:
        #
        # 2026-08-20T21:00:00.000-03:00
        #

        dt = datetime.fromisoformat(
            fecha.replace(
                "Z",
                "+00:00"
            )
        )

        return dt

    except ValueError:

        print()
        print(
            f"Fecha inválida: {fecha}"
        )

        return None


# ============================================================
# FORMATO XMLTV
# ============================================================

def formato_xmltv(fecha):

    if fecha is None:
        return ""

    # La API entrega las fechas con su offset.
    #
    # Ejemplo:
    #
    # 2026-08-20T21:00:00-03:00
    #
    # XMLTV:
    #
    # 20260820210000 -0300

    fecha_texto = fecha.strftime(
        "%Y%m%d%H%M%S"
    )

    return (
        fecha_texto
        + " "
        + TIMEZONE_OFFSET
    )


# ============================================================
# OBTENER EVENTOS + CATEGORÍAS
# ============================================================

def obtener_eventos(data):

    eventos = {}

    # ========================================================
    # EVENTOS GENERALES
    # ========================================================

    for evento in data.get(
        "events",
        []
    ):

        event_id = evento.get(
            "id"
        )

        if event_id is None:
            continue

        evento_copia = dict(
            evento
        )

        evento_copia["categoria"] = (
            evento_copia.get(
                "categoria",
                "TODO EN VIVO"
            )
        )

        eventos[
            event_id
        ] = evento_copia

    # ========================================================
    # EVENTOS DENTRO DE CATEGORÍAS
    # ========================================================

    for categoria in data.get(
        "categories",
        []
    ):

        categoria_nombre = categoria.get(
            "title",
            "TODO EN VIVO"
        )

        for evento in categoria.get(
            "events",
            []
        ):

            event_id = evento.get(
                "id"
            )

            if event_id is None:
                continue

            evento_copia = dict(
                evento
            )

            evento_copia["categoria"] = (
                categoria_nombre
            )

            # Si está dentro de una categoría,
            # usamos esa categoría.
            eventos[
                event_id
            ] = evento_copia

    return list(
        eventos.values()
    )


# ============================================================
# CREAR XMLTV
# ============================================================

def crear_epg(eventos):

    # --------------------------------------------------------
    # HORA ACTUAL
    # --------------------------------------------------------

    ahora = datetime.now(
        timezone.utc
    )

    limite = (
        ahora.timestamp()
        +
        (
            DIAS_FUTUROS
            * 24
            * 60
            * 60
        )
    )

    eventos_validos = []

    # ========================================================
    # FILTRAR EVENTOS
    # ========================================================

    for evento in eventos:

        event_id = evento.get(
            "id"
        )

        titulo = evento.get(
            "title",
            f"Evento {event_id}"
        )

        start = convertir_fecha(
            evento.get(
                "start_date"
            )
        )

        end = convertir_fecha(
            evento.get(
                "end_date"
            )
        )

        # ----------------------------------------------------
        # FECHAS INVÁLIDAS
        # ----------------------------------------------------

        if start is None or end is None:

            print()
            print(
                f"Evento {event_id} ignorado "
                f"por fecha inválida."
            )

            continue

        # ----------------------------------------------------
        # EVENTO YA TERMINADO
        # ----------------------------------------------------

        if end.timestamp() < ahora.timestamp():

            continue

        # ----------------------------------------------------
        # EVENTO DEMASIADO LEJANO
        # ----------------------------------------------------

        if start.timestamp() > limite:

            continue

        # ----------------------------------------------------
        # GUARDAR DATOS CONVERTIDOS
        # ----------------------------------------------------

        evento["start_dt"] = start

        evento["end_dt"] = end

        eventos_validos.append(
            evento
        )

    # ========================================================
    # ORDENAR POR HORA DE COMIENZO
    # ========================================================

    eventos_validos.sort(
        key=lambda x: x["start_dt"]
    )

    print()
    print(
        f"Eventos encontrados en API: "
        f"{len(eventos)}"
    )

    print(
        f"Eventos incluidos en EPG: "
        f"{len(eventos_validos)}"
    )

    # ========================================================
    # CREAR ROOT XMLTV
    # ========================================================

    root = ET.Element(
        "tv",
        {
            "generator-info-name":
                "Todo En Vivo EPG",

            "generator-info-url":
                "https://todoenvivo.plag.tv"
        }
    )

    # ========================================================
    # CREAR CHANNELS
    # ========================================================

    canales_creados = set()

    for evento in eventos_validos:

        event_id = evento[
            "id"
        ]

        tvg_id = (
            f"TEV_{event_id}"
        )

        # Evitar canales duplicados.
        if tvg_id in canales_creados:
            continue

        canales_creados.add(
            tvg_id
        )

        channel = ET.SubElement(
            root,
            "channel",
            {
                "id":
                    tvg_id
            }
        )

        # ----------------------------------------------------
        # NOMBRE DEL CANAL
        # ----------------------------------------------------

        display_name = ET.SubElement(
            channel,
            "display-name"
        )

        display_name.text = str(
            evento.get(
                "title",
                f"Evento {event_id}"
            )
        )

        # ----------------------------------------------------
        # LOGO
        # ----------------------------------------------------

        imagen = (
            evento.get(
                "main_image"
            )
            or
            evento.get(
                "thumbnail_image"
            )
        )

        if imagen:

            ET.SubElement(
                channel,
                "icon",
                {
                    "src":
                        str(imagen)
                }
            )

    # ========================================================
    # CREAR PROGRAMMES
    # ========================================================

    for evento in eventos_validos:

        event_id = evento[
            "id"
        ]

        titulo = evento.get(
            "title",
            f"Evento {event_id}"
        )

        descripcion = evento.get(
            "description",
            ""
        )

        categoria = evento.get(
            "categoria",
            "TODO EN VIVO"
        )

        start = evento[
            "start_dt"
        ]

        end = evento[
            "end_dt"
        ]

        tvg_id = (
            f"TEV_{event_id}"
        )

        # ----------------------------------------------------
        # PROGRAMME
        # ----------------------------------------------------

        programme = ET.SubElement(
            root,
            "programme",
            {
                "start":
                    formato_xmltv(
                        start
                    ),

                "stop":
                    formato_xmltv(
                        end
                    ),

                "channel":
                    tvg_id
            }
        )

        # ====================================================
        # TÍTULO
        # ====================================================

        title_element = ET.SubElement(
            programme,
            "title",
            {
                "lang":
                    "es"
            }
        )

        title_element.text = str(
            titulo
        )

        # ====================================================
        # DESCRIPCIÓN
        # ====================================================

        if descripcion:

            desc_element = ET.SubElement(
                programme,
                "desc",
                {
                    "lang":
                        "es"
                }
            )

            desc_element.text = str(
                descripcion
            )

        # ====================================================
        # CATEGORÍA
        # ====================================================

        if categoria:

            category_element = ET.SubElement(
                programme,
                "category",
                {
                    "lang":
                        "es"
                }
            )

            category_element.text = str(
                categoria
            )

        # ====================================================
        # IMAGEN
        # ====================================================

        imagen = (
            evento.get(
                "main_image"
            )
            or
            evento.get(
                "thumbnail_image"
            )
        )

        if imagen:

            ET.SubElement(
                programme,
                "icon",
                {
                    "src":
                        str(imagen)
                }
            )

    # ========================================================
    # INDENTAR XML
    # ========================================================

    ET.indent(
        root,
        space="    "
    )

    # ========================================================
    # GUARDAR ARCHIVO
    # ========================================================

    tree = ET.ElementTree(
        root
    )

    tree.write(
        ARCHIVO_EPG,
        encoding="utf-8",
        xml_declaration=True
    )

    return len(
        eventos_validos
    )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    data = obtener_datos()

    if not data:

        print()
        print(
            "No se pudieron obtener los datos."
        )

        return

    # ========================================================
    # OBTENER EVENTOS
    # ========================================================

    eventos = obtener_eventos(
        data
    )

    if not eventos:

        print()
        print(
            "No se encontraron eventos."
        )

        return

    # ========================================================
    # CREAR EPG
    # ========================================================

    cantidad = crear_epg(
        eventos
    )

    # ========================================================
    # RESULTADO
    # ========================================================

    print()
    print("=" * 60)
    print(
        "EPG GENERADO CORRECTAMENTE"
    )
    print("=" * 60)

    print()
    print(
        f"Programas incluidos: "
        f"{cantidad}"
    )

    print()
    print(
        "Archivo:"
    )

    print(
        ARCHIVO_EPG
    )

    print()


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":

    main()
