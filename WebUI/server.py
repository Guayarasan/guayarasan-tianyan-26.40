import importlib.util
import json
import logging
import math
import os
import subprocess
import sys
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger("tianyan_plugin")

# Instalación automática de dependencias
# noinspection PyUnusedImports
def install_dependencies():
    """Instala automáticamente las dependencias necesarias de Python"""

    # Lista de paquetes obligatorios a verificar
    required_packages = ['fastapi', 'uvicorn', 'pydantic']

    # Comprobar si ya está instalado
    missing_packages = []
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)

    if not missing_packages:
        # print("All required dependencies are installed.")
        return True

    print(f"Missing dependencies found: {missing_packages}")
    print("Attempting automatic installation...")

    # Comprobar si pip está disponible
    try:
        # Intentar importar pip
        import pip
        print("pip installed, version:", pip.__version__)
    except ImportError:
        print("pip not found, trying to install pip...")
        try:
            # Instalar pip usando ensurepip
            import ensurepip
            subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
            print("pip installed successfully")
        except Exception as error:
            print(f"Failed to install pip: {error}")
            print("Please install pip manually: https://pip.pypa.io/en/stable/installation/")
            return False

    # Instalar los paquetes faltantes
    try:
        # Primero actualizar pip
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

        requirements_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
        if os.path.exists(requirements_file):
            print(f"Using requirements.txt to install dependencies: {requirements_file}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
        else:
            # En caso contrario, instalar solo los paquetes faltantes
            print("requirements.txt not found, installing missing packages...")
            for package in missing_packages:
                print(f"Installing {package}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])

        print("Dependencies installed successfully!")
        return True

    except subprocess.CalledProcessError as error:
        print(f"Failed to install dependencies: {error}")
        return False
    except Exception as error:
        print(f"Unknown error during installation: {error}")
        return False


def verify_dependencies():
    """Verifica que todas las dependencias necesarias estén instaladas"""
    required_packages = ['fastapi', 'uvicorn', 'pydantic']

    # print("Verifying dependencies...")
    missing_packages = []

    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError as error:
            missing_packages.append(package)
            print(f"✗ {package} not installed: {error}")

    if missing_packages:
        print(f"\nMissing required dependencies: {missing_packages}")
        print("Attempting automatic installation...")

        if install_dependencies():
            # Volver a verificar
            print("\nRe-verifying dependencies...")
            final_missing = []
            for package in required_packages:
                try:
                    importlib.import_module(package)
                except ImportError:
                    final_missing.append(package)

            if final_missing:
                print(f"\nError: Failed to install the following dependencies: {final_missing}")
                print("Please install manually: pip install " + " ".join(final_missing))
                return False
            else:
                print("\nAll dependencies installed successfully!")
                return True
        else:
            print("\nAutomatic installation failed, please install dependencies manually.")
            print("Please run: pip install " + " ".join(missing_packages))
            return False
    else:
        return True


# Verificar dependencias antes de importar librerías de terceros
if __name__ != "__main__":
    # Si el módulo fue importado, omitir la verificación de dependencias
    pass
else:
    # Verificar dependencias al ejecutar el programa principal
    if not verify_dependencies():
        print("Dependency check failed, program exiting.")
        sys.exit(1)

try:
    # noinspection PyUnusedImports
    import uvicorn
    # noinspection PyUnusedImports
    from fastapi import FastAPI, Header, HTTPException, Query
    # noinspection PyUnusedImports
    from fastapi.middleware.cors import CORSMiddleware
    # noinspection PyUnusedImports
    from pydantic import BaseModel
    # noinspection PyUnusedImports
    from fastapi.staticfiles import StaticFiles
    # noinspection PyUnusedImports
    from fastapi.responses import FileResponse
except ImportError as e:
    print(f"Failed to import third-party libraries: {e}")
    print("Please ensure all dependencies are installed:")
    print("pip install fastapi uvicorn pydantic")
    sys.exit(1)

# Obtener la ruta absoluta del script actual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# print(f"Base directory: {BASE_DIR}")
# Forzar el directorio de trabajo a la carpeta WebUI
os.chdir(BASE_DIR)

# Reubicar rutas (relativas a la carpeta WebUI)
DB_PATH = "../ty_data.db"
CONFIG_PATH = "../web_config.json"
LOG_PATH = "../logs/webui.log"
LANGUAGES_DIR = "languages"
READY_FILE = "ready"

# Asegurar que el directorio de logs exista
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

# Bandera global de depuración
DEBUG_MODE = "--debug" in sys.argv


def load_config() -> dict:
    """Carga segura del archivo de configuración, con valores por defecto y manejo de errores"""
    default_config = {
        "secret": "",
        "backend_port": 8098,
        # Se pueden agregar otros valores por defecto según sea necesario
    }
    if not os.path.exists(CONFIG_PATH):
        logging.warning(f"Config file not found. Generating template at {CONFIG_PATH}")
        template = {
            "secret": "your_secret",
            "backend_port": 8098
        }
        with open(CONFIG_PATH, 'w', encoding='utf-8') as cf:
            json.dump(template, cf, indent=4, ensure_ascii=False)
        return template

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as cf:
            the_config = json.load(cf)
            # Combinar con los valores por defecto (solo se completan los campos faltantes)
            for key, value in default_config.items():
                if key not in the_config:
                    the_config[key] = value
            return the_config
    except json.JSONDecodeError as error:
        logging.error(f"Invalid JSON in config file {CONFIG_PATH}: {error}")
        raise RuntimeError(f"Configuration file is not valid JSON: {error}")
    except Exception as error:
        logging.error(f"Failed to load config file {CONFIG_PATH}: {error}")
        raise RuntimeError(f"Cannot load configuration: {error}")


def load_language(lang_code="en_US"):
    """Cargar archivo de idioma"""
    lang_file = os.path.join(BASE_DIR, LANGUAGES_DIR, f"{lang_code}.json")

    # Si el archivo de idioma solicitado no existe, usar inglés como respaldo
    if not os.path.exists(lang_file):
        lang_file = os.path.join(BASE_DIR, LANGUAGES_DIR, "en_US.json")

    try:
        with open(lang_file, 'r', encoding='utf-8') as lf:
            return json.load(lf)
    except Exception as error:
        logging.error(f"Failed to load language file {lang_file}: {error}")
        # Devolver un diccionario vacío
        return {}


def _load_mysql_config():
    """Lee la información de conexión MySQL desde la configuración del plugin Tianyan."""
    tianyan_config_path = os.path.join(BASE_DIR, "..", "config.json")
    raw = {}
    try:
        with open(tianyan_config_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"Failed to read tianyan config: {e}, using defaults")
    return {
        "host": raw.get("mysql_host", "127.0.0.1"),
        "port": int(raw.get("mysql_port", 3306)),
        "user": raw.get("mysql_user", "root"),
        "password": raw.get("mysql_password", ""),
        "database": raw.get("mysql_database", "endstone"),
    }


class Database:
    """Envoltorio de conexión a base de datos; elige automáticamente SQLite o MySQL según la configuración."""

    def __init__(self):
        self.db_type = "sqlite"
        self.conn = None

        # Leer la configuración del plugin Tianyan para determinar el tipo de base de datos
        tianyan_config_path = os.path.join(BASE_DIR, "..", "config.json")
        db_type = "sqlite"
        try:
            with open(tianyan_config_path, 'r', encoding='utf-8') as f:
                tc = json.load(f)
                db_type = tc.get("database_type", "sqlite")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"Failed to read tianyan config: {e}, using SQLite")

        if db_type == "mysql":
            try:
                # Agregar la ruta de dependencias del plugin Endstone (pymysql se instala aquí y no en site-packages del venv)
                _plugin_site = os.path.join(
                    BASE_DIR, "..", "..", ".local", "lib",
                    f"python{sys.version_info.major}.{sys.version_info.minor}",
                    "site-packages"
                )
                if os.path.isdir(_plugin_site):
                    sys.path.insert(0, _plugin_site)
                import pymysql
                mysql_cfg = _load_mysql_config()
                self.conn = pymysql.connect(
                    host=mysql_cfg["host"],
                    port=mysql_cfg["port"],
                    user=mysql_cfg["user"],
                    password=mysql_cfg["password"],
                    database=mysql_cfg["database"],
                    cursorclass=pymysql.cursors.DictCursor,
                )
                self.db_type = "mysql"
                self.database = mysql_cfg["database"]
                logging.info("WebUI connected to MySQL")
            except ImportError:
                logging.warning("pymysql not installed, falling back to SQLite")
            except Exception as e:
                logging.warning(f"MySQL connection failed ({e}), falling back to SQLite")

        if self.db_type == "sqlite":
            import sqlite3
            self._sqlite3 = sqlite3
            self.database = None
            db_path = os.path.join(BASE_DIR, "..", "ty_data.db")
            self.conn = self._sqlite3.connect(db_path)
            self.conn.row_factory = self._sqlite3.Row

    def execute(self, sql: str, params: Optional[list] = None):
        """Ejecuta SQL y devuelve el cursor. Maneja automáticamente las diferencias de marcador de parámetros."""
        if self.db_type == "mysql":
            sql = sql.replace("?", "%s")
        cursor = self.conn.cursor()
        cursor.execute(sql, params or [])
        return cursor

    def fetchall(self, cursor) -> list[dict]:
        """Devuelve todas las filas de resultado como una lista de diccionarios."""
        if self.db_type == "sqlite":
            return [dict(row) for row in cursor.fetchall()]
        return cursor.fetchall()

    def fetchone(self, cursor) -> Optional[dict]:
        """Devuelve la primera fila como un diccionario."""
        rows = self.fetchall(cursor)
        return rows[0] if rows else None

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Configuración del sistema de logs
def setup_logging():
    """Configura el logging, con salida a archivo y consola"""
    global logger
    # Establece el nivel de log según el modo de depuración
    if DEBUG_MODE:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Eliminar todos los manejadores existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Asegurar que el directorio de logs exista
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    # 👇 Vaciar el contenido del archivo de log en cada inicio
    with open(LOG_PATH, 'w', encoding='utf-8'):
        pass

    # Crear manejador de archivo
    file_handler = logging.FileHandler(LOG_PATH, encoding='utf-8')
    if DEBUG_MODE:
        file_handler.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.INFO)

    # Crear manejador de consola (solo en modo depuración o siempre)
    console_handler = logging.StreamHandler()
    if DEBUG_MODE:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)

    # Crear formateador
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Agregar al logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Configurar el log de uvicorn
    if DEBUG_MODE:
        # Conservar más logs en modo depuración
        logging.getLogger("uvicorn").setLevel(logging.DEBUG)
        logging.getLogger("uvicorn.access").setLevel(logging.DEBUG)
        logging.getLogger("uvicorn.error").setLevel(logging.DEBUG)
    else:
        # Reducir logs en modo producción
        logging.getLogger("uvicorn").handlers = []
        logging.getLogger("uvicorn.access").handlers = []
        logging.getLogger("uvicorn.error").handlers = []


# Configurar logging
setup_logging()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# Obtener lista de idiomas disponibles
@app.get("/api/languages")
async def get_languages():
    """Obtiene la lista de idiomas disponibles"""
    languages = []
    if os.path.exists(LANGUAGES_DIR):
        for file in os.listdir(LANGUAGES_DIR):
            if file.endswith(".json"):
                lang_code = file.replace(".json", "")
                languages.append(lang_code)

    # Asegurar que al menos se devuelva inglés
    if "en_US" not in languages:
        languages.append("en_US")

    return {"languages": sorted(languages), "default": "en_US"}


# Obtener contenido del archivo de idioma
@app.get("/api/language/{lang_code}")
async def get_language(lang_code: str):
    """Obtiene el contenido del archivo de idioma indicado"""
    return load_language(lang_code)


# Función auxiliar: obtiene el tamaño del archivo o el identificador de MySQL
def get_db_size(db: Database):
    if db.db_type == "mysql":
        cursor = db.execute(
            "SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb "
            "FROM information_schema.tables WHERE table_schema = ?",
            [db.database]
        )
        row = db.fetchone(cursor)
        if row and row["size_mb"] is not None:
            return f"{float(row['size_mb']):.2f} MB"
        return "MySQL"
    db_path = os.path.join(BASE_DIR, "..", "ty_data.db")
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return "0 MB"


# Modelos de datos
class LogsResponse(BaseModel):
    data: List[Dict]
    total: int
    page: int
    page_size: int
    total_pages: int
    query_time_ms: float


@app.get("/api/stats")
async def get_stats(x_secret: str = Header(None)):
    web_config = load_config()
    if x_secret != web_config.get("secret"):
        raise HTTPException(status_code=403, detail="Clave secreta inválida")

    with Database() as db:
        cursor = db.execute("SELECT COUNT(*) AS cnt FROM LOGDATA")
        row = db.fetchone(cursor)
        total_count = int(row["cnt"]) if row else 0
        db_size = get_db_size(db)

    return {
        "total_logs": total_count,
        "db_size": db_size,
        "server_time": int(time.time())
    }


@app.get("/api/logs", response_model=LogsResponse)
async def get_logs(
        page: int = Query(1, ge=1, description="Número de página"),
        page_size: int = Query(100, ge=1, le=500, description="Registros por página"),
        start_time: int = Query(None, description="Hora de inicio (marca de tiempo Unix)"),
        end_time: int = Query(None, description="Hora de fin (marca de tiempo Unix)"),
        filter_type: str = Query(None, description="Tipo de campo de filtro"),
        filter_value: str = Query(None, description="Valor de filtro (admite coincidencia parcial)"),
        center_x: float = Query(None, description="Coordenada X del punto central"),
        center_y: float = Query(None, description="Coordenada Y del punto central"),
        center_z: float = Query(None, description="Coordenada Z del punto central"),
        radius: float = Query(None, description="Radio de búsqueda (bloques)"),
        dimension: str = Query(None, description="Nombre de la dimensión"),
        x_secret: str = Header(None),
        x_lang: str = Header("en_US")
):
    start_time_query = time.time()  # Registrar la hora de inicio de la consulta

    web_config = load_config()
    if x_secret != web_config.get("secret"):
        raise HTTPException(status_code=403, detail="Clave secreta inválida")

    # Verificar los parámetros de búsqueda por coordenadas
    has_coord_query = all([center_x is not None, center_y is not None, center_z is not None, radius is not None])
    if any([center_x is not None, center_y is not None, center_z is not None, radius is not None]):
        if not has_coord_query:
            raise HTTPException(
                status_code=400,
                detail="La búsqueda por coordenadas requiere todos los parámetros: center_x, center_y, center_z, radius"
            )
        if radius < 0:
            raise HTTPException(status_code=400, detail="El radio no puede ser negativo")

    # Registrar los parámetros de la solicitud (modo depuración)
    if DEBUG_MODE:
        logging.debug(f"Parámetros de solicitud de API /logs:")
        logging.debug(f"  page={page}, page_size={page_size}")
        logging.debug(f"  start_time={start_time}, end_time={end_time}")
        logging.debug(f"  filter_type={filter_type}, filter_value={filter_value}")
        logging.debug(f"  center_x={center_x}, center_y={center_y}, center_z={center_z}, radius={radius}")
        logging.debug(f"  dimension={dimension}")
        logging.debug(f"  has_coord_query={has_coord_query}")

    with Database() as db:
        try:
            # Construir consulta de conteo, usada para obtener el total de registros
            count_query = "SELECT COUNT(*) AS cnt FROM LOGDATA WHERE 1=1"
            data_query = "SELECT * FROM LOGDATA WHERE 1=1"
            count_params = []
            data_params = []

            # Filtro de rango de tiempo
            if start_time:
                count_query += " AND time >= ?"
                data_query += " AND time >= ?"
                count_params.append(start_time)
                data_params.append(start_time)
            if end_time:
                count_query += " AND time <= ?"
                data_query += " AND time <= ?"
                count_params.append(end_time)
                data_params.append(end_time)

            # Filtro de campo (usa LIKE para coincidencia parcial)
            if filter_type and filter_value:
                allowed_fields = ["id", "name", "type", "obj_id", "obj_name", "world", "status", "data"]
                if filter_type in allowed_fields:
                    count_query += f" AND ({filter_type} IS NOT NULL AND {filter_type} != '' AND {filter_type} LIKE ?)"
                    data_query += f" AND ({filter_type} IS NOT NULL AND {filter_type} != '' AND {filter_type} LIKE ?)"
                    count_params.append(f"%{filter_value}%")
                    data_params.append(f"%{filter_value}%")

            # Filtro de dimensión
            if dimension:
                if dimension.lower() != "all" and dimension != "":
                    count_query += " AND world = ?"
                    data_query += " AND world = ?"
                    count_params.append(dimension)
                    data_params.append(dimension)

            # Filtro de rango de coordenadas
            if has_coord_query:
                valid_coord_condition = " AND pos_x IS NOT NULL AND pos_y IS NOT NULL AND pos_z IS NOT NULL"
                count_query += valid_coord_condition
                data_query += valid_coord_condition

                # Pre-filtro rectangular: usa el índice para descartar rápidamente datos fuera del área, reduciendo los cálculos de distancia
                bbox = (center_x - radius, center_x + radius,
                        center_y - radius, center_y + radius,
                        center_z - radius, center_z + radius)
                bbox_sql = " AND pos_x >= ? AND pos_x <= ? AND pos_y >= ? AND pos_y <= ? AND pos_z >= ? AND pos_z <= ?"
                count_query += bbox_sql
                data_query += bbox_sql
                count_params.extend(bbox)
                data_params.extend(bbox)

                distance_condition = """
                    AND ((pos_x - ?) * (pos_x - ?) +
                        (pos_y - ?) * (pos_y - ?) +
                        (pos_z - ?) * (pos_z - ?)) <= (? * ?)
                """
                count_query += distance_condition
                data_query += distance_condition
                params = [center_x, center_x, center_y, center_y, center_z, center_z, radius, radius]
                count_params.extend(params)
                data_params.extend(params)

            if DEBUG_MODE:
                logging.debug(f"SQL de la consulta de conteo: {count_query}")
                logging.debug(f"Parámetros de la consulta de conteo: {count_params}")

            cursor = db.execute(count_query, count_params)
            row = db.fetchone(cursor)
            total_records = int(row["cnt"]) if row else 0

            offset = (page - 1) * page_size
            total_pages = (total_records + page_size - 1) // page_size

            data_query += " ORDER BY time DESC LIMIT ? OFFSET ?"
            data_params.extend([page_size, offset])

            if DEBUG_MODE:
                logging.debug(f"SQL de la consulta de datos: {data_query}")
                logging.debug(f"Parámetros de la consulta de datos: {data_params}")

            cursor = db.execute(data_query, data_params)
            rows = db.fetchall(cursor)

            for record in rows:
                if has_coord_query:
                    dx = float(record["pos_x"]) - center_x
                    dy = float(record["pos_y"]) - center_y
                    dz = float(record["pos_z"]) - center_z
                    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
                    record["distance"] = round(distance, 2)

            query_time = (time.time() - start_time_query) * 1000

            if DEBUG_MODE:
                logging.debug(f"Resultado de la consulta: se encontraron {len(rows)} registros de un total de {total_records}")
                logging.debug(f"Tiempo de consulta: {query_time:.2f} ms")

            return LogsResponse(
                data=rows,
                total=total_records,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                query_time_ms=round(query_time, 2)
            )

        except Exception as error:
            logging.error(f"Error de consulta en la base de datos: {str(error)}")
            raise HTTPException(status_code=500, detail=f"Error de consulta en la base de datos: {str(error)}")


# Nuevo: endpoint de consulta por lotes (usado para exportar)
@app.get("/api/export")
async def export_logs(
        start_page: int = Query(1, ge=1, description="Página inicial"),
        end_page: int = Query(1, ge=1, description="Página final"),
        page_size: int = Query(100, ge=1, le=500, description="Registros por página"),
        start_time: int = Query(None, description="Hora de inicio (marca de tiempo Unix)"),
        end_time: int = Query(None, description="Hora de fin (marca de tiempo Unix)"),
        filter_type: str = Query(None, description="Tipo de campo de filtro"),
        filter_value: str = Query(None, description="Valor de filtro (admite coincidencia parcial)"),
        center_x: float = Query(None, description="Coordenada X del punto central"),
        center_y: float = Query(None, description="Coordenada Y del punto central"),
        center_z: float = Query(None, description="Coordenada Z del punto central"),
        radius: float = Query(None, description="Radio de búsqueda (bloques)"),
        dimension: str = Query(None, description="Nombre de la dimensión"),
        x_secret: str = Header(None),
        x_lang: str = Header("en_US")
):
    web_config = load_config()
    if x_secret != web_config.get("secret"):
        raise HTTPException(status_code=403, detail="Clave secreta inválida")

    if start_page > end_page:
        raise HTTPException(status_code=400, detail="La página inicial no puede ser mayor que la página final")

    if (end_page - start_page + 1) * page_size > 50000:
        raise HTTPException(status_code=400, detail="El volumen de datos a exportar es demasiado grande, máximo 50000 registros")

    # Registrar los parámetros de la solicitud (modo depuración)
    if DEBUG_MODE:
        logging.debug(f"Parámetros de solicitud de API /export:")
        logging.debug(f"  start_page={start_page}, end_page={end_page}, page_size={page_size}")
        logging.debug(f"  start_time={start_time}, end_time={end_time}")
        logging.debug(f"  filter_type={filter_type}, filter_value={filter_value}")
        logging.debug(f"  center_x={center_x}, center_y={center_y}, center_z={center_z}, radius={radius}")
        logging.debug(f"  dimension={dimension}")

    with Database() as db:
        try:
            # Primero obtener el total de datos que cumplen la condición
            count_query = "SELECT COUNT(*) AS cnt FROM LOGDATA WHERE 1=1"
            count_params = []

            if start_time:
                count_query += " AND time >= ?"
                count_params.append(start_time)
            if end_time:
                count_query += " AND time <= ?"
                count_params.append(end_time)

            if filter_type and filter_value:
                allowed_fields = ["id", "name", "type", "obj_id", "obj_name", "world", "status", "data"]
                if filter_type in allowed_fields:
                    count_query += f" AND ({filter_type} IS NOT NULL AND {filter_type} != '' AND {filter_type} LIKE ?)"
                    count_params.append(f"%{filter_value}%")

            if dimension and dimension.lower() != "all" and dimension != "":
                count_query += " AND world = ?"
                count_params.append(dimension)

            has_coord_query = all([center_x is not None, center_y is not None, center_z is not None, radius is not None])
            if has_coord_query:
                count_query += " AND pos_x IS NOT NULL AND pos_y IS NOT NULL AND pos_z IS NOT NULL"
                bbox = (center_x - radius, center_x + radius,
                        center_y - radius, center_y + radius,
                        center_z - radius, center_z + radius)
                count_query += " AND pos_x >= ? AND pos_x <= ? AND pos_y >= ? AND pos_y <= ? AND pos_z >= ? AND pos_z <= ?"
                count_params.extend(bbox)
                distance_condition = """
                    AND ((pos_x - ?) * (pos_x - ?) +
                        (pos_y - ?) * (pos_y - ?) +
                        (pos_z - ?) * (pos_z - ?)) <= (? * ?)
                """
                count_query += distance_condition
                params = [center_x, center_x, center_y, center_y, center_z, center_z, radius, radius]
                count_params.extend(params)

            if DEBUG_MODE:
                logging.debug(f"SQL de conteo para exportación: {count_query}")
                logging.debug(f"Parámetros de conteo para exportación: {count_params}")

            cursor = db.execute(count_query, count_params)
            row = db.fetchone(cursor)
            total_records = int(row["cnt"]) if row else 0

            total_pages = (total_records + page_size - 1) // page_size
            actual_end_page = min(end_page, total_pages)

            if start_page > total_pages:
                logging.warning(f"La página inicial solicitada {start_page} excede el total de páginas {total_pages}")
                return {
                    "data": [],
                    "total_records": 0,
                    "exported_records": 0,
                    "pages_exported": 0,
                    "message": f"La página inicial {start_page} excede el total de páginas {total_pages}"
                }

            all_data = []
            for page_num in range(start_page, actual_end_page + 1):
                offset_val = (page_num - 1) * page_size

                data_query = "SELECT * FROM LOGDATA WHERE 1=1"
                data_params = []

                if start_time:
                    data_query += " AND time >= ?"
                    data_params.append(start_time)
                if end_time:
                    data_query += " AND time <= ?"
                    data_params.append(end_time)

                if filter_type and filter_value:
                    allowed_fields = ["id", "name", "type", "obj_id", "obj_name", "world", "status", "data"]
                    if filter_type in allowed_fields:
                        data_query += f" AND ({filter_type} IS NOT NULL AND {filter_type} != '' AND {filter_type} LIKE ?)"
                        data_params.append(f"%{filter_value}%")

                if dimension and dimension.lower() != "all" and dimension != "":
                    data_query += " AND world = ?"
                    data_params.append(dimension)

                if has_coord_query:
                    bbox = (center_x - radius, center_x + radius,
                            center_y - radius, center_y + radius,
                            center_z - radius, center_z + radius)
                    data_query += " AND pos_x >= ? AND pos_x <= ? AND pos_y >= ? AND pos_y <= ? AND pos_z >= ? AND pos_z <= ?"
                    data_params.extend(bbox)
                    distance_condition = """
                        AND ((pos_x - ?) * (pos_x - ?) +
                             (pos_y - ?) * (pos_y - ?) +
                             (pos_z - ?) * (pos_z - ?)) <= (? * ?)
                    """
                    data_query += distance_condition
                    params = [center_x, center_x, center_y, center_y, center_z, center_z, radius, radius]
                    data_params.extend(params)

                data_query += " ORDER BY time DESC LIMIT ? OFFSET ?"
                data_params.extend([page_size, offset_val])

                if DEBUG_MODE:
                    logging.debug(f"SQL de exportación de la página {page_num}: {data_query}")

                cursor = db.execute(data_query, data_params)
                rows = db.fetchall(cursor)
                for record in rows:
                    if has_coord_query:
                        dx = float(record["pos_x"]) - center_x
                        dy = float(record["pos_y"]) - center_y
                        dz = float(record["pos_z"]) - center_z
                        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
                        record["distance"] = round(distance, 2)
                    all_data.append(record)

            if DEBUG_MODE:
                logging.debug(f"Resultado de exportación: se exportaron {len(all_data)} registros en total")

            return {
                "data": all_data,
                "total_records": total_records,
                "exported_records": len(all_data),
                "pages_exported": actual_end_page - start_page + 1,
                "start_page": start_page,
                "end_page": actual_end_page,
                "total_pages": total_pages
            }

        except Exception as error:
            logging.error(f"Error al exportar datos: {str(error)}")
            raise HTTPException(status_code=500, detail=f"Error al exportar datos: {str(error)}")


# Nuevo: obtener el estado de los índices de la base de datos y recomendaciones
@app.get("/api/db_info")
async def get_db_info(x_secret: str = Header(None)):
    web_config = load_config()
    if x_secret != web_config.get("secret"):
        raise HTTPException(status_code=403, detail="Clave secreta inválida")

    with Database() as db:
        if db.db_type == "sqlite":
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row["name"] for row in db.fetchall(cursor)]

            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='LOGDATA'")
            indexes = [row["name"] for row in db.fetchall(cursor)]

            cursor = db.execute("PRAGMA table_info(LOGDATA)")
            columns = [{"name": row["name"], "type": row["type"], "notnull": row["notnull"], "pk": row["pk"]} for row in db.fetchall(cursor)]

            cursor = db.execute("SELECT COUNT(*) AS cnt FROM LOGDATA")
            row = db.fetchone(cursor)
            total_rows = int(row["cnt"]) if row else 0
        else:
            cursor = db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = ?", [db.database])
            tables = [row["table_name"] for row in db.fetchall(cursor)]

            cursor = db.execute("""
                SELECT index_name FROM information_schema.statistics
                WHERE table_schema = ? AND table_name = 'LOGDATA'
                GROUP BY index_name
            """, [db.database])
            indexes = [row["index_name"] for row in db.fetchall(cursor)]

            cursor = db.execute("""
                SELECT column_name AS name, column_type AS type,
                       is_nullable AS notnull, column_key AS pk
                FROM information_schema.columns
                WHERE table_schema = ? AND table_name = 'LOGDATA'
            """, [db.database])
            columns = [dict(row) for row in db.fetchall(cursor)]

            cursor = db.execute("SELECT COUNT(*) AS cnt FROM LOGDATA")
            row = db.fetchone(cursor)
            total_rows = int(row["cnt"]) if row else 0

        return {
            "tables": tables,
            "indexes": indexes,
            "columns": columns,
            "total_rows": total_rows
        }


# Para depuración
@app.get("/api/debug/query")
async def debug_query(
        sql: str = Query(None, description="Sentencia de consulta SQL"),
        x_secret: str = Header(None)
):
    """Endpoint de depuración: ejecuta directamente una consulta SQL (solo disponible en modo depuración)"""
    if not DEBUG_MODE:
        raise HTTPException(status_code=403, detail="Este endpoint solo está disponible en modo depuración")

    web_config = load_config()
    if x_secret != web_config.get("secret"):
        raise HTTPException(status_code=403, detail="Clave secreta inválida")

    if not sql or not sql.strip():
        raise HTTPException(status_code=400, detail="Se debe proporcionar una sentencia de consulta SQL")

    # Verificación de seguridad: solo se permiten consultas SELECT
    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Solo se permiten consultas SELECT")

    with Database() as db:
        try:
            logging.info(f"SQL ejecutado en consulta de depuración: {sql}")

            cursor = db.execute(sql)
            rows = db.fetchall(cursor)

            return {
                "success": True,
                "row_count": len(rows),
                "data": rows[:100],
                "total": len(rows)
            }
        except Exception as error:
            logging.error(f"Error en la consulta de depuración: {str(error)}")
            return {
                "success": False,
                "error": str(error)
            }


@app.get("/")
async def get_index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# ✅ Agregar rutas para JS y CSS
@app.get("/script.js")
async def get_script():
    return FileResponse(os.path.join(BASE_DIR, "script.js"))

@app.get("/style.css")
async def get_style():
    return FileResponse(os.path.join(BASE_DIR, "style.css"))


if __name__ == "__main__":
    # Comprobar si se inició en modo depuración
    if DEBUG_MODE:
        print(f"Boot mode: DEBUG")
        print(f"Database: {DB_PATH} (type: sqlite by default, see ../config.json)")
        print(f"Config file: {CONFIG_PATH}")
        print(f"Log file: {LOG_PATH}")
        print(f"Languages Path: {LANGUAGES_DIR}")

    conf = load_config()
    # Configurar los parámetros de ejecución de uvicorn
    config = {
        "host": "0.0.0.0",
        "port": conf.get("backend_port", 8098),
        "log_config": None,  # Deshabilitar la configuración de log por defecto de uvicorn
        "access_log": DEBUG_MODE,  # Habilitar el log de acceso solo en modo depuración
        "log_level": "debug" if DEBUG_MODE else "warning"  # Establecer el nivel de log
    }

    logger.info(f"Start WebUI Service，127.0.0.1:{config['port']}")
    if conf.get("secret", "your_secret") == "your_secret":
        logger.warning("Using the default secret 'your_secret' — please update it for better security.")
    with open(READY_FILE, "w", encoding="utf-8"):
        pass

    uvicorn.run(app, **config)