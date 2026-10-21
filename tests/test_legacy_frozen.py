"""
La copia congelada del script de nivel 3 (versión del 01/10/2026) es el
oráculo del test de no regresión y no se puede editar. Si este test falla,
alguien la ha modificado, o git ha convertido sus finales de línea (ver
.gitattributes).

Respecto a la versión desplegada (sha256 6420fc62…4f662c), la copia solo
cambia un comentario, generalizado al publicar el repositorio; se comprobó
que su salida es idéntica en todos los casos (decisión 0006).
"""

import hashlib

from helpers import LEGACY_SCRIPT

LEGACY_SHA256 = "f669f044fbe441c8429b295738de40c7a736ef15cf041f46fb2ddff1f7c77454"


def test_legacy_copy_is_untouched():
    assert hashlib.sha256(LEGACY_SCRIPT.read_bytes()).hexdigest() == LEGACY_SHA256
