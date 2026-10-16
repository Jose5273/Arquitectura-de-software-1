"""
Recolector de datos públicos de un perfil de Instagram.

Requiere:
- Brave instalado en Windows.
- Un perfil de Brave con sesión activa en Instagram.
- chromedriver.exe descargado manualmente (opcional pero recomendado).
- requests (para descargar imágenes): pip install requests

Uso:
    python recolectar.py
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

class Config:
    USUARIO = "alondra_cgp"
    BASE_URL = "https://www.instagram.com/"
    URL_PERFIL = f"{BASE_URL}{USUARIO}/"

    # Límites de recolección
    LIMITE_PUBLICACIONES = 25
    LIMITE_NOMBRES = 50

    BRAVE_EXE = (
        r"C:\Program Files\BraveSoftware"
        r"\Brave-Browser\Application\brave.exe"
    )
    PERFIL_BRAVE_RAIZ = (
        r"C:\Users\joseg\AppData\Local"
        r"\BraveSoftware\Brave-Browser\User Data"
    )
    NOMBRE_PERFIL = "Default"
    RUTA_CHROMEDRIVER = r"C:\drivers\chromedriver.exe"

    CARPETA_SALIDA = Path("salida_instagram")
    CARPETA_IMAGENES = CARPETA_SALIDA / "imagenes"

    TIMEOUT_CORTO = 5
    TIMEOUT_MEDIO = 10
    TIMEOUT_LARGO = 20

    # Tiempo entre descargas y entre navegaciones
    PAUSA_ENTRE_POSTS = 2
    TIMEOUT_DESCARGA = 20

    RUTAS_EXCLUIDAS = {
        "blog", "popular", "explore", "accounts", "direct", "reels",
        "stories", "about", "developer", "legal", "web", "p", "reel",
        "challenge", "emails", "press", "api", "privacy", "terms",
        "directory", "followers", "following"
    }


# ==========================================================
# UTILIDADES
# ==========================================================

def fecha_actual() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def extraer_cantidad(texto: str | None, etiqueta: str) -> int | None:
    if not texto:
        return None
    coincidencia = re.search(
        rf"([\d.,]+)\s*{re.escape(etiqueta)}", texto, re.IGNORECASE
    )
    if not coincidencia:
        return None
    return int(coincidencia.group(1).replace(".", "").replace(",", ""))


def extraer_nombre_visible(titulo: str | None) -> str | None:
    if not titulo:
        return None
    coincidencia = re.search(r"^(.*?)\s*\(@", titulo)
    return coincidencia.group(1).strip() if coincidencia else None


def es_nombre_usuario_valido(nombre: str) -> bool:
    return bool(nombre and re.fullmatch(r"[A-Za-z0-9._]{1,30}", nombre))


def extraer_fecha_alt(texto_alt: str | None) -> str | None:
    if not texto_alt:
        return None
    coincidencia = re.search(
        r"\bon\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        texto_alt,
        re.IGNORECASE
    )
    return coincidencia.group(1) if coincidencia else None


def url_imagen_valida(url: str | None) -> bool:
    """Verifica que la URL apunte a un recurso de imagen de Instagram."""
    if not url:
        return False
    return (
        url.startswith("http")
        and (
            "scontent" in url
            or "cdninstagram" in url
            or "fbcdn" in url
        )
    )


def limpiar_nombre_archivo(texto: str) -> str:
    """Convierte un texto en un nombre de archivo seguro."""
    texto = re.sub(r"[^\w\-.]", "_", texto)
    return texto[:120] or "publicacion"


# ==========================================================
# DRIVER
# ==========================================================

class DriverInstagram:
    """Encapsula la creación y el ciclo de vida del WebDriver."""

    def __init__(self, config: type[Config]):
        self.config = config
        self.driver = self._crear()

    def _crear(self) -> webdriver.Chrome:
        cfg = self.config

        if not os.path.isfile(cfg.BRAVE_EXE):
            raise FileNotFoundError(
                f"No se encontró Brave en:\n{cfg.BRAVE_EXE}"
            )
        if not os.path.isdir(cfg.PERFIL_BRAVE_RAIZ):
            raise FileNotFoundError(
                f"No se encontró la carpeta de perfiles:\n"
                f"{cfg.PERFIL_BRAVE_RAIZ}"
            )

        opciones = Options()
        opciones.binary_location = cfg.BRAVE_EXE
        opciones.add_argument(
            f"--user-data-dir={cfg.PERFIL_BRAVE_RAIZ}"
        )
        opciones.add_argument(
            f"--profile-directory={cfg.NOMBRE_PERFIL}"
        )
        opciones.add_argument(
            "--disable-blink-features=AutomationControlled"
        )
        opciones.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )
        opciones.add_experimental_option(
            "useAutomationExtension", False
        )

        if os.path.isfile(cfg.RUTA_CHROMEDRIVER):
            servicio = Service(executable_path=cfg.RUTA_CHROMEDRIVER)
            driver = webdriver.Chrome(
                service=servicio, options=opciones
            )
        else:
            driver = webdriver.Chrome(options=opciones)

        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['es-ES', 'es', 'en']
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                """
            }
        )
        return driver

    def cerrar(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def __enter__(self):
        return self.driver

    def __exit__(self, *args):
        self.cerrar()


# ==========================================================
# HELPERS DE ESPERA
# ==========================================================

def esperar(segundos: float):
    time.sleep(segundos)


def esperar_elemento(driver, selector: str, timeout: int):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def sesion_iniciada(driver) -> bool:
    try:
        if "/accounts/login" in driver.current_url.lower():
            return False
        if driver.find_elements(By.CSS_SELECTOR, 'input[name="username"]'):
            return False
        return True
    except Exception:
        return False


# ==========================================================
# RECOLECCIÓN: PERFIL
# ==========================================================

def obtener_meta(driver, selector: str) -> str | None:
    elementos = driver.find_elements(By.CSS_SELECTOR, selector)
    return elementos[0].get_attribute("content") if elementos else None


def extraer_candidatos_biografia(driver, usuario, nombre_visible):
    candidatos = []
    vistos = set()

    excluir = {
        usuario.lower(),
        (nombre_visible or "").lower(),
        "seguir", "mensaje", "contactar", "más", "más información"
    }

    elementos = driver.find_elements(
        By.CSS_SELECTOR, "header [dir='auto'], header span"
    )

    for elemento in elementos:
        try:
            if not elemento.is_displayed():
                continue
            texto = elemento.text.strip()
            if not texto or texto.lower() in excluir or texto in vistos:
                continue
            if re.search(
                r"\b(seguidores|seguidos|publicaciones)\b",
                texto,
                re.IGNORECASE
            ):
                continue
            vistos.add(texto)
            candidatos.append(texto)
        except Exception:
            continue

    return candidatos


def recolectar_perfil(driver, cfg: type[Config]) -> dict:
    print(f"\nConsultando perfil @{cfg.USUARIO}...")
    driver.get(cfg.URL_PERFIL)
    esperar(4)

    titulo = obtener_meta(driver, 'meta[property="og:title"]')
    descripcion = obtener_meta(
        driver, 'meta[property="og:description"]'
    )
    imagen = obtener_meta(driver, 'meta[property="og:image"]')

    nombre_visible = extraer_nombre_visible(titulo)
    candidatos = extraer_candidatos_biografia(
        driver, cfg.USUARIO, nombre_visible
    )
    posibles = [
        t for t in candidatos
        if len(t) <= 500 and not t.startswith("@")
    ]
    biografia = max(posibles, key=len) if posibles else None

    print("\nCandidatos a biografía:")
    for c in candidatos:
        print("-", c)

    return {
        "usuario": cfg.USUARIO,
        "url": cfg.URL_PERFIL,
        "nombre_visible": nombre_visible,
        "titulo": titulo,
        "biografia": biografia,
        "candidatos_biografia": candidatos,
        "descripcion_meta": descripcion,
        "imagen_meta": imagen,
        "seguidores": extraer_cantidad(descripcion, "seguidores"),
        "seguidos": extraer_cantidad(descripcion, "seguidos"),
        "publicaciones_total": extraer_cantidad(
            descripcion, "publicaciones"
        ),
        "fecha_recoleccion": fecha_actual()
    }


# ==========================================================
# RECOLECCIÓN: PUBLICACIONES (POST POR POST)
# ==========================================================

def recolectar_enlaces_publicaciones(driver, cfg: type[Config]) -> list[str]:
    """
    Devuelve la lista de URLs de publicaciones visibles en el perfil,
    hasta LIMITE_PUBLICACIONES.
    """
    driver.get(cfg.URL_PERFIL)
    esperar(4)

    # Scroll para cargar más publicaciones si el perfil tiene muchas
    for _ in range(4):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )
        esperar(2)

    enlaces = driver.find_elements(
        By.CSS_SELECTOR, 'a[href*="/p/"], a[href*="/reel/"]'
    )

    urls = []
    vistos = set()

    for enlace in enlaces:
        if len(urls) >= cfg.LIMITE_PUBLICACIONES:
            break
        try:
            href = enlace.get_attribute("href")
            if not href or href in vistos:
                continue
            vistos.add(href)
            urls.append(href)
        except Exception:
            continue

    print(f"\nPublicaciones encontradas en el perfil: {len(urls)}")
    return urls


def extraer_datos_publicacion(driver, url: str, cfg: type[Config]) -> dict:
    """
    Entra a una publicación y extrae la URL de la imagen real
    del post (no la foto de perfil).
    """
    driver.get(url)
    esperar(3)

    # Esperar a que haya al menos una imagen del CDN
    try:
        WebDriverWait(driver, cfg.TIMEOUT_MEDIO).until(
            lambda d: d.find_elements(
                By.CSS_SELECTOR,
                'article img, main img, div[role="dialog"] img'
            )
        )
    except Exception:
        pass

    url_imagen = None
    texto_alt = None

    # Contenedores candidatos donde está la imagen del post,
    # de más específico a más genérico.
    selectores = [
        'article img[src*="scontent"]',
        'article img[src*="cdninstagram"]',
        'article img[src*="fbcdn"]',
        'main img[src*="scontent"]',
        'main img[src*="cdninstagram"]',
        'main img[src*="fbcdn"]',
        'div[role="dialog"] img[src*="scontent"]',
        'div[role="dialog"] img[src*="cdninstagram"]',
        'div[role="dialog"] img[src*="fbcdn"]',
    ]

    for selector in selectores:
        try:
            imagenes = driver.find_elements(By.CSS_SELECTOR, selector)
            for img in imagenes:
                src = img.get_attribute("src")
                if not url_imagen_valida(src):
                    continue

                # Descartar imágenes pequeñas (avatares)
                try:
                    ancho = img.size.get("width", 0)
                    alto = img.size.get("height", 0)
                except Exception:
                    ancho = alto = 0

                if ancho and alto and (ancho < 200 or alto < 200):
                    continue

                url_imagen = src
                texto_alt = img.get_attribute("alt")
                break
            if url_imagen:
                break
        except Exception:
            continue

    # Fallback: si no encontramos nada con los selectores anteriores,
    # buscamos cualquier imagen del CDN que no sea el avatar.
    if not url_imagen:
        try:
            imagenes = driver.find_elements(
                By.CSS_SELECTOR,
                'img[src*="scontent"], img[src*="cdninstagram"], '
                'img[src*="fbcdn"]'
            )
            for img in imagenes:
                src = img.get_attribute("src")
                if not url_imagen_valida(src):
                    continue
                try:
                    ancho = img.size.get("width", 0)
                    alto = img.size.get("height", 0)
                except Exception:
                    ancho = alto = 0
                # Las imágenes de posts suelen ser grandes
                if ancho and alto and ancho >= 400 and alto >= 400:
                    url_imagen = src
                    texto_alt = img.get_attribute("alt")
                    break
        except Exception:
            pass

    return {
        "url_publicacion": url,
        "url_imagen": url_imagen,
        "texto_alt": texto_alt,
        "fecha_publicacion_alt": extraer_fecha_alt(texto_alt),
        "fecha_recoleccion": fecha_actual()
    }


class DescargadorImagenes:
    """Descarga imágenes del CDN de Instagram a una carpeta local."""

    def __init__(self, carpeta: Path, timeout: int = 20):
        self.carpeta = carpeta
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        })

    def _nombre_desde_url(self, url: str, indice: int) -> str:
        # Intentar obtener un nombre desde el path
        try:
            ruta = urlparse(url).path
            base = os.path.basename(ruta).split("?")[0]
            if base and len(base) > 5:
                return f"{indice:03d}_{base}"
        except Exception:
            pass
        return f"{indice:03d}_imagen.jpg"

    def descargar(self, url: str, indice: int) -> str | None:
        if not url_imagen_valida(url):
            return None
        try:
            respuesta = self.session.get(
                url, timeout=self.timeout, stream=True
            )
            respuesta.raise_for_status()

            nombre = limpiar_nombre_archivo(
                self._nombre_desde_url(url, indice)
            )
            ruta = self.carpeta / nombre

            with open(ruta, "wb") as archivo:
                for chunk in respuesta.iter_content(chunk_size=8192):
                    archivo.write(chunk)

            return str(ruta)
        except Exception as error:
            print(f"    Error al descargar: {error}")
            return None


def recolectar_publicaciones(
    driver, cfg: type[Config], descargador: DescargadorImagenes
) -> list[dict]:
    """
    Recolecta las publicaciones una por una hasta alcanzar
    LIMITE_PUBLICACIONES o hasta que se acaben.
    """
    urls = recolectar_enlaces_publicaciones(driver, cfg)
    if not urls:
        print("No se encontraron publicaciones.")
        return []

    publicaciones = []
    total = len(urls)

    for indice, url in enumerate(urls, start=1):
        print(f"\n[{indice}/{total}] Procesando publicación...")
        datos = extraer_datos_publicacion(driver, url, cfg)

        if datos["url_imagen"]:
            print(f"  Imagen: {datos['url_imagen'][:80]}...")
            ruta_local = descargador.descargar(
                datos["url_imagen"], indice
            )
            datos["ruta_imagen_local"] = ruta_local
            if ruta_local:
                print(f"  Descargada en: {ruta_local}")
            else:
                print("  No se pudo descargar la imagen.")
        else:
            datos["ruta_imagen_local"] = None
            print("  No se encontró URL de imagen.")

        datos["usuario"] = cfg.USUARIO
        publicaciones.append(datos)

        esperar(cfg.PAUSA_ENTRE_POSTS)

    print(f"\nPublicaciones procesadas: {len(publicaciones)}")
    return publicaciones


# ==========================================================
# RECOLECCIÓN: SEGUIDORES / SEGUIDOS
# ==========================================================

class ModalSeguidores:
    """Abre el modal de seguidores/seguidos y extrae los nombres."""

    def __init__(self, driver, cfg: type[Config]):
        self.driver = driver
        self.cfg = cfg

    def _localizar_enlace(self, texto_buscado: str):
        try:
            for a in self.driver.find_elements(
                By.CSS_SELECTOR, "header a"
            ):
                try:
                    if texto_buscado in a.text.strip().lower():
                        return a
                except Exception:
                    continue
        except Exception:
            pass

        try:
            return self.driver.find_element(
                By.XPATH,
                f"//a[.//span[contains(text(), '{texto_buscado}')]]"
            )
        except Exception:
            return None

    def _abrir(self, tipo: str):
        texto_buscado = (
            "seguidores" if tipo == "followers" else "seguidos"
        )
        self.driver.get(self.cfg.URL_PERFIL)
        esperar(5)

        enlace = self._localizar_enlace(texto_buscado)
        if not enlace:
            print(f"No se encontró el enlace de {tipo}.")
            return None

        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                enlace
            )
            esperar(1)
            enlace.click()
        except Exception:
            try:
                self.driver.execute_script(
                    "arguments[0].click();", enlace
                )
            except Exception:
                print(f"No se pudo hacer clic en {tipo}.")
                return None

        try:
            esperar_elemento(
                self.driver,
                'div[role="dialog"]',
                self.cfg.TIMEOUT_MEDIO
            )
        except Exception:
            print("No apareció el modal.")
            return None

        esperar(3)
        return self._contenedor_scroll()

    def _contenedor_scroll(self):
        candidatos = [
            'div[role="dialog"] ._aano',
            'div[role="dialog"] .isgrP',
            'div[role="dialog"] div[style*="overflow-y"]',
            'div[role="dialog"] div[style*="overflow"]',
            'div[role="dialog"] ul',
        ]
        for selector in candidatos:
            encontrados = self.driver.find_elements(
                By.CSS_SELECTOR, selector
            )
            if encontrados:
                return encontrados[0]

        dialogos = self.driver.find_elements(
            By.CSS_SELECTOR, 'div[role="dialog"]'
        )
        return dialogos[0] if dialogos else None

    def _scroll(self, contenedor, max_intentos=25):
        ultimo_alto = 0
        sin_cambio = 0

        for _ in range(max_intentos):
            nombres_actuales = self.driver.find_elements(
                By.CSS_SELECTOR, 'div[role="dialog"] a[href]'
            )
            if len(nombres_actuales) >= self.cfg.LIMITE_NOMBRES:
                break

            try:
                alto = self.driver.execute_script(
                    "return arguments[0].scrollHeight;", contenedor
                )
            except Exception:
                break

            if alto == ultimo_alto:
                sin_cambio += 1
                if sin_cambio >= 3:
                    break
            else:
                sin_cambio = 0

            ultimo_alto = alto

            try:
                self.driver.execute_script(
                    "arguments[0].scrollTop = "
                    "arguments[0].scrollHeight;",
                    contenedor
                )
            except Exception:
                break

            esperar(2)

    def _extraer_nombres(self) -> set[str]:
        nombres = set()
        enlaces = self.driver.find_elements(
            By.CSS_SELECTOR, 'div[role="dialog"] a[href]'
        )

        for enlace in enlaces:
            if len(nombres) >= self.cfg.LIMITE_NOMBRES:
                break
            try:
                href = enlace.get_attribute("href")
                if not href:
                    continue
                partes = urlparse(href).path.strip("/").split("/")
                if len(partes) != 1:
                    continue
                nombre = partes[0]
                if nombre.lower() in self.cfg.RUTAS_EXCLUIDAS:
                    continue
                if nombre.lower() == self.cfg.USUARIO.lower():
                    continue
                if not es_nombre_usuario_valido(nombre):
                    continue
                nombres.add(nombre)
            except Exception:
                continue

        return nombres

    def _cerrar(self):
        try:
            webdriver.ActionChains(self.driver).send_keys(
                Keys.ESCAPE
            ).perform()
            esperar(1)
        except Exception:
            pass

    def recolectar(self, tipo: str):
        print(f"\nConsultando lista de {tipo}...")
        contenedor = self._abrir(tipo)
        if contenedor is None:
            return [], "modal_no_abierto"

        self._scroll(contenedor)
        nombres = self._extraer_nombres()
        self._cerrar()

        lista = sorted(nombres, key=str.lower)
        estado = (
            "nombres_visibles_parciales" if lista
            else "lista_no_visible"
        )
        print("Nombres encontrados:", len(lista))
        print("Estado:", estado)
        return lista, estado


# ==========================================================
# EXPORTACIÓN
# ==========================================================

class Exportador:
    def __init__(self, carpeta: Path):
        self.carpeta = carpeta
        self.carpeta.mkdir(parents=True, exist_ok=True)

    def _ruta(self, nombre: str) -> Path:
        return self.carpeta / nombre

    def csv(self, nombre: str, datos, columnas):
        df = pd.DataFrame(datos, columns=columnas)
        df.to_csv(
            self._ruta(nombre), index=False, encoding="utf-8-sig"
        )
        print(f"  - {self._ruta(nombre)}")

    def json(self, nombre: str, datos):
        with open(
            self._ruta(nombre), "w", encoding="utf-8"
        ) as archivo:
            json.dump(
                datos, archivo, ensure_ascii=False, indent=2
            )
        print(f"  - {self._ruta(nombre)}")


# ==========================================================
# FLUJO PRINCIPAL
# ==========================================================

def asegurar_sesion(driver, cfg: type[Config]):
    driver.get(cfg.BASE_URL)
    esperar(3)

    if sesion_iniciada(driver):
        print(f"\nSesión activa detectada en '{cfg.NOMBRE_PERFIL}'.")
        return True

    print(
        f"\nNo se detectó sesión activa en '{cfg.NOMBRE_PERFIL}'."
    )
    print(
        "Inicia sesión manualmente en la ventana de Brave "
        "(usa tu CUENTA SECUNDARIA)."
    )
    input("Cuando veas tu feed, pulsa ENTER...")

    driver.get(cfg.BASE_URL)
    esperar(3)
    return sesion_iniciada(driver)


def ejecutar():
    cfg = Config
    exportador = Exportador(cfg.CARPETA_SALIDA)
    descargador = DescargadorImagenes(
        cfg.CARPETA_IMAGENES, timeout=cfg.TIMEOUT_DESCARGA
    )

    with DriverInstagram(cfg) as driver:
        if not asegurar_sesion(driver, cfg):
            print("Aún no hay sesión. Abortando.")
            return

        perfil = recolectar_perfil(driver, cfg)
        publicaciones = recolectar_publicaciones(
            driver, cfg, descargador
        )

        modal = ModalSeguidores(driver, cfg)
        seguidores, estado_seguidores = modal.recolectar("followers")
        seguidos, estado_seguidos = modal.recolectar("following")

        perfil["estado_lista_seguidores"] = estado_seguidores
        perfil["estado_lista_seguidos"] = estado_seguidos

        datos_seguidores = [
            {"usuario_seguidor": n, "perfil_consultado": cfg.USUARIO}
            for n in seguidores
        ]
        datos_seguidos = [
            {"usuario_seguido": n, "perfil_consultado": cfg.USUARIO}
            for n in seguidos
        ]

        print("\nGuardando archivos en:", cfg.CARPETA_SALIDA)
        exportador.csv("perfil.csv", [perfil], list(perfil.keys()))
        exportador.csv(
            "publicaciones.csv",
            publicaciones,
            [
                "usuario", "url_publicacion", "url_imagen",
                "ruta_imagen_local", "texto_alt",
                "fecha_publicacion_alt", "fecha_recoleccion"
            ]
        )
        exportador.csv(
            "seguidores.csv",
            datos_seguidores,
            ["usuario_seguidor", "perfil_consultado"]
        )
        exportador.csv(
            "seguidos.csv",
            datos_seguidos,
            ["usuario_seguido", "perfil_consultado"]
        )
        exportador.json(
            "datos_instagram.json",
            {
                "perfil": perfil,
                "publicaciones": publicaciones,
                "seguidores": seguidores,
                "seguidos": seguidos
            }
        )

        print("\n========== RESUMEN ==========")
        print("Usuario:", cfg.USUARIO)
        print("Nombre visible:", perfil["nombre_visible"])
        print("Biografía:", perfil["biografia"])
        print("Seguidores (metadatos):", perfil["seguidores"])
        print("Seguidos (metadatos):", perfil["seguidos"])
        print("Publicaciones totales:", perfil["publicaciones_total"])
        print("Publicaciones procesadas:", len(publicaciones))
        print("Imágenes descargadas:", sum(
            1 for p in publicaciones if p.get("ruta_imagen_local")
        ))
        print("Seguidores capturados:", len(seguidores))
        print("Seguidos capturados:", len(seguidos))
        print("Estado seguidores:", estado_seguidores)
        print("Estado seguidos:", estado_seguidos)
        print(f"\nCarpeta de imágenes: {cfg.CARPETA_IMAGENES}")
        print(f"Perfil Brave: {cfg.PERFIL_BRAVE_RAIZ} / "
              f"{cfg.NOMBRE_PERFIL}")

        input("\nPulsa ENTER para cerrar el navegador...")


if __name__ == "__main__":
    ejecutar()