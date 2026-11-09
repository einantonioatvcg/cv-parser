"""Ciudad y país a partir de los segmentos finales de una línea."""

from __future__ import annotations

import re
from dataclasses import dataclass

from cv_parser.lines import fold, normalize_text


@dataclass(frozen=True)
class Place:
    city: str | None
    country_code: str
    country_name: str


COUNTRIES: dict[str, tuple[str, str]] = {}
_COUNTRY_NAMES = {
    "MX": ("México", ["mexico", "mex", "mx", "republica mexicana"]),
    "US": ("Estados Unidos", ["estados unidos", "estados unidos de america", "eeuu", "ee uu", "usa", "us", "u s a",
                              "u s", "united states", "united states of america"]),
    "ES": ("España", ["espana", "spain"]),
    "CO": ("Colombia", ["colombia"]), "AR": ("Argentina", ["argentina"]), "CL": ("Chile", ["chile"]),
    "PE": ("Perú", ["peru"]), "VE": ("Venezuela", ["venezuela"]), "EC": ("Ecuador", ["ecuador"]),
    "GT": ("Guatemala", ["guatemala"]), "HN": ("Honduras", ["honduras"]), "SV": ("El Salvador", ["el salvador"]),
    "NI": ("Nicaragua", ["nicaragua"]), "CR": ("Costa Rica", ["costa rica"]), "PA": ("Panamá", ["panama"]),
    "CU": ("Cuba", ["cuba"]), "DO": ("República Dominicana", ["republica dominicana", "dominican republic"]),
    "PR": ("Puerto Rico", ["puerto rico"]), "BO": ("Bolivia", ["bolivia"]), "PY": ("Paraguay", ["paraguay"]),
    "UY": ("Uruguay", ["uruguay"]), "BR": ("Brasil", ["brasil", "brazil"]), "CA": ("Canadá", ["canada"]),
    "FR": ("Francia", ["francia", "france"]), "DE": ("Alemania", ["alemania", "germany"]),
    "IT": ("Italia", ["italia", "italy"]), "PT": ("Portugal", ["portugal"]),
    "GB": ("Reino Unido", ["reino unido", "united kingdom", "uk", "inglaterra", "england"]),
    "NL": ("Países Bajos", ["paises bajos", "holanda", "netherlands"]), "CN": ("China", ["china"]),
    "JP": ("Japón", ["japon", "japan"]), "IN": ("India", ["india"]), "KR": ("Corea del Sur", ["corea del sur", "south korea"]),
    "AU": ("Australia", ["australia"]), "IE": ("Irlanda", ["irlanda", "ireland"]), "CH": ("Suiza", ["suiza", "switzerland"]),
}
for _code, (_name, _aliases) in _COUNTRY_NAMES.items():
    for _alias in _aliases:
        COUNTRIES[_alias] = (_code, _name)

# Estados o regiones: alias plegado -> código de país.
REGIONS: dict[str, str] = {}
_MX_STATES = [
    "aguascalientes", "ags", "baja california", "bc", "baja california sur", "bcs", "campeche", "camp", "chiapas",
    "chis", "chihuahua", "chih", "coahuila", "coah", "colima", "col", "durango", "dgo", "guanajuato", "gto",
    "guerrero", "gro", "hidalgo", "hgo", "jalisco", "jal", "estado de mexico", "edo de mexico", "edo mex", "edomex",
    "michoacan", "mich", "morelos", "mor", "nayarit", "nay", "nuevo leon", "n l", "nl", "oaxaca", "oax", "puebla",
    "pue", "queretaro", "qro", "quintana roo", "q roo", "san luis potosi", "slp", "s l p", "sinaloa", "sin",
    "sonora", "son", "tabasco", "tab", "tamaulipas", "tamps", "tlaxcala", "tlax", "veracruz", "ver", "yucatan",
    "yuc", "zacatecas", "zac", "distrito federal", "df", "d f",
]
_US_STATES = [
    "texas", "tx", "california", "arizona", "az", "new york", "ny", "florida", "fl", "illinois", "il", "nevada",
    "nv", "new mexico", "nm", "colorado", "georgia", "north carolina", "washington", "oregon", "utah",
    "new jersey", "massachusetts", "pennsylvania", "ohio", "michigan",
]
_ES_REGIONS = ["comunidad de madrid", "cataluna", "andalucia", "comunidad valenciana", "castilla-la mancha",
               "pais vasco", "galicia", "aragon"]
for _alias in _MX_STATES:
    REGIONS[_alias] = "MX"
for _alias in _US_STATES:
    REGIONS[_alias] = "US"
for _alias in _ES_REGIONS:
    REGIONS[_alias] = "ES"

# Ciudades: (nombre canónico, país). Si un nombre existe en varios países, el primero es el de uso más probable.
_CITIES: list[tuple[str, str, list[str]]] = [
    ("Ciudad de México", "MX", ["ciudad de mexico", "cdmx", "cd de mexico", "mexico city", "mexico df", "mexico d f"]),
    ("Guadalajara", "MX", []), ("Zapopan", "MX", []), ("Tlaquepaque", "MX", ["san pedro tlaquepaque"]),
    ("Tonalá", "MX", []), ("Tlajomulco", "MX", ["tlajomulco de zuniga"]), ("Monterrey", "MX", []),
    ("San Pedro Garza García", "MX", []), ("Guadalupe", "MX", []), ("Apodaca", "MX", []),
    ("San Nicolás de los Garza", "MX", []), ("Puebla", "MX", []), ("León", "MX", []), ("Querétaro", "MX", ["santiago de queretaro"]),
    ("Mérida", "MX", []), ("Cancún", "MX", []), ("Tijuana", "MX", []), ("Mexicali", "MX", []), ("Ensenada", "MX", []),
    ("Chihuahua", "MX", []), ("Ciudad Juárez", "MX", ["cd juarez"]), ("Hermosillo", "MX", []), ("Culiacán", "MX", []),
    ("Mazatlán", "MX", []), ("Aguascalientes", "MX", []), ("Morelia", "MX", []), ("Toluca", "MX", []),
    ("Metepec", "MX", []), ("Naucalpan", "MX", []), ("Ecatepec", "MX", []), ("Nezahualcóyotl", "MX", []),
    ("Tlalnepantla", "MX", []), ("Saltillo", "MX", []), ("Torreón", "MX", []), ("Durango", "MX", []),
    ("San Luis Potosí", "MX", []), ("Zacatecas", "MX", []), ("Tepic", "MX", []), ("Colima", "MX", []),
    ("Manzanillo", "MX", []), ("Puerto Vallarta", "MX", []), ("Acapulco", "MX", []), ("Chilpancingo", "MX", []),
    ("Oaxaca", "MX", ["oaxaca de juarez"]), ("Tuxtla Gutiérrez", "MX", []), ("Villahermosa", "MX", []),
    ("Campeche", "MX", []), ("Chetumal", "MX", []), ("Playa del Carmen", "MX", []), ("Veracruz", "MX", []),
    ("Xalapa", "MX", ["jalapa"]), ("Boca del Río", "MX", []), ("Coatzacoalcos", "MX", []), ("Cuernavaca", "MX", []),
    ("Pachuca", "MX", []), ("Tlaxcala", "MX", []), ("Celaya", "MX", []), ("Irapuato", "MX", []),
    ("Salamanca", "MX", []), ("Silao", "MX", []), ("La Paz", "MX", []), ("Los Cabos", "MX", []),
    ("Cabo San Lucas", "MX", []), ("Reynosa", "MX", []), ("Matamoros", "MX", []), ("Nuevo Laredo", "MX", []),
    ("Tampico", "MX", []), ("Ciudad Victoria", "MX", ["cd victoria"]), ("Ciudad Obregón", "MX", ["cd obregon"]),
    ("Los Mochis", "MX", []), ("Lagos de Moreno", "MX", []), ("Tepatitlán", "MX", []), ("Ocotlán", "MX", []),
    ("Austin", "US", []), ("Houston", "US", []), ("Dallas", "US", []), ("San Antonio", "US", []),
    ("El Paso", "US", []), ("Los Angeles", "US", ["los angeles"]), ("San Diego", "US", []), ("Chicago", "US", []),
    ("New York", "US", ["nueva york", "new york city", "nyc"]), ("Miami", "US", []), ("Phoenix", "US", []),
    ("Las Vegas", "US", []), ("San Francisco", "US", []), ("Seattle", "US", []), ("Denver", "US", []),
    ("Madrid", "ES", []), ("Barcelona", "ES", []), ("Valencia", "ES", []), ("Sevilla", "ES", []),
    ("Bilbao", "ES", []), ("Málaga", "ES", []), ("Zaragoza", "ES", []), ("Guadalajara", "ES", []),
    ("Bogotá", "CO", []), ("Medellín", "CO", []), ("Cali", "CO", []), ("Barranquilla", "CO", []),
    ("Buenos Aires", "AR", []), ("Córdoba", "AR", []), ("Rosario", "AR", []), ("Santiago", "CL", ["santiago de chile"]),
    ("Lima", "PE", []), ("Caracas", "VE", []), ("Quito", "EC", []), ("Guayaquil", "EC", []),
    ("Ciudad de Guatemala", "GT", []), ("San José", "CR", []), ("Ciudad de Panamá", "PA", []),
    ("Toronto", "CA", []), ("Vancouver", "CA", []), ("Montreal", "CA", []), ("London", "GB", ["londres"]),
    ("París", "FR", ["paris"]),
]
CITIES: dict[str, list[tuple[str, str]]] = {}
for _name, _code, _aliases in _CITIES:
    for _alias in [fold(_name)] + _aliases:
        CITIES.setdefault(_alias, []).append((_name, _code))

_COUNTRY_DISPLAY = {code: name for code, (name, _) in _COUNTRY_NAMES.items()}
_SPLIT = re.compile(r"\s*[,|;·/]\s*|\s+[-–]\s+")


def _key(segment: str) -> str:
    folded = fold(segment)
    folded = re.sub(r"\b(c\.?\s?p\.?|zip|cp)\b\.?", " ", folded)   # código postal
    folded = re.sub(r"\d+", " ", folded)
    folded = re.sub(r"[.\-]", " ", folded)
    return " ".join(re.sub(r"[^a-z ]", " ", folded).split())


def _segments(text: str) -> list[str]:
    return [s for s in _SPLIT.split(normalize_text(text)) if s.strip()]


def _classify(segment: str) -> tuple[str, object] | None:
    key = _key(segment)
    if not key:
        return ("empty", None)
    if key in COUNTRIES:
        return ("country", COUNTRIES[key][0])
    if key in CITIES:
        return ("city", CITIES[key], key)
    if key in REGIONS:
        return ("region", REGIONS[key])
    return None


def _resolve(classified: list[tuple]) -> Place | None:
    # "Córdoba, Veracruz": tras el primer lugar, un nombre que también es estado se lee como estado.
    classified = [("region", REGIONS[c[2]]) if i > 0 and c[0] == "city" and c[2] in REGIONS else c
                  for i, c in enumerate(classified)]
    country = next((c[1] for c in classified if c[0] == "country"), None)
    region = next((c[1] for c in classified if c[0] == "region"), None)
    cities = [c[1] for c in classified if c[0] == "city"]
    code = country or region
    city = None
    if cities:
        options = cities[0]
        if code:
            match = [name for name, c in options if c == code]
            city = match[0] if match else None
        else:
            city, code = options[0]
    if code is None:
        return None
    return Place(city=city, country_code=code, country_name=_COUNTRY_DISPLAY.get(code, code))


def _trailing(text: str) -> tuple[list[tuple[str, object]], int, int]:
    segments = _segments(text)
    classified: list[tuple[str, object]] = []
    for segment in reversed(segments):
        result = _classify(segment)
        if result is None:
            break
        if result[0] != "empty":
            classified.insert(0, result)
    consumed = len(classified)
    return classified, consumed, len([s for s in segments if _key(s)])


def find_place(text: str) -> Place | None:
    """Mira solo los segmentos finales tras una coma, o la línea entera si es un lugar."""
    classified, consumed, total = _trailing(text)
    if not classified:
        return None
    if consumed < total:
        # Hay texto antes del lugar: debe ir separado por coma, nunca dentro de una oración.
        if not re.search(r"[,|;·/]|\s[-–]\s", normalize_text(text)):
            return None
    return _resolve(classified)


def is_place_line(text: str) -> bool:
    classified, consumed, total = _trailing(text)
    return bool(classified) and consumed == total and _resolve(classified) is not None


def split_place(text: str) -> tuple[str, Place | None]:
    """Separa el lugar final de una línea: ("Clínica San Rafael", Place(Zapopan, MX))."""
    original = normalize_text(text)
    spans: list[tuple[int, int]] = []
    cursor = 0
    for sep in _SPLIT.finditer(original):
        spans.append((cursor, sep.start()))
        cursor = sep.end()
    spans.append((cursor, len(original)))
    spans = [(a, b) for a, b in spans if original[a:b].strip()]
    classified: list[tuple[str, object]] = []
    first_consumed = len(spans)
    for i in range(len(spans) - 1, -1, -1):
        result = _classify(original[spans[i][0]:spans[i][1]])
        if result is None:
            break
        first_consumed = i
        if result[0] != "empty":
            classified.insert(0, result)
    place = _resolve(classified) if classified else None
    if place is None:
        return original, None
    rest = original[:spans[first_consumed][0]] if first_consumed < len(spans) else ""
    return rest.rstrip(" ,|;·/-–"), place


_LOOSE_SKIP = {"col", "sin", "son", "ver", "mor", "tab", "camp", "pue", "us", "cp", "nay", "zac", "dgo", "nl", "bc"}


def find_place_loose(text: str) -> Place | None:
    """Para direcciones sin comas: busca un estado o país en las últimas palabras ("... Pachuca de Soto Hgo.")."""
    found = find_place(text)
    if found is not None:
        return found
    words = _key(text).split()
    for n in range(min(4, len(words)), 0, -1):
        tail = " ".join(words[-n:])
        if tail in _LOOSE_SKIP:
            continue
        if tail in COUNTRIES:
            code = COUNTRIES[tail][0]
        elif tail in REGIONS:
            code = REGIONS[tail]
        else:
            continue
        return Place(city=None, country_code=code, country_name=_COUNTRY_DISPLAY.get(code, code))
    return None
