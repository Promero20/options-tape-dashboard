"""
Las copias congeladas del script de nivel 3 son los oráculos del test de no
regresión y de la validación de los nivel 3 guardados, y no se pueden editar.
Si este test falla, alguien ha modificado una copia, o git ha convertido sus
finales de línea (ver .gitattributes).

Respecto a la versión desplegada (sha256 6420fc62…4f662c), la copia del
01/10/2026 solo cambia un comentario, generalizado al publicar el
repositorio; se comprobó que su salida es idéntica en todos los casos
(decisión 0006). The copy of 21/10/2026 is the script byte for byte as it was
deployed before the grouping rule of 16/11/2026 (decision 0036).
"""

import hashlib

import pytest

from helpers import LEGACY_SCRIPT, PREVIOUS_SCRIPT

FROZEN = {
    LEGACY_SCRIPT: "f669f044fbe441c8429b295738de40c7a736ef15cf041f46fb2ddff1f7c77454",
    PREVIOUS_SCRIPT: "aea159f50faf93ed6b7fef345d884e6ac8e38247275287c3ebc542b64d8c571a",
}


@pytest.mark.parametrize("script", FROZEN, ids=lambda p: p.stem)
def test_frozen_copy_is_untouched(script):
    assert hashlib.sha256(script.read_bytes()).hexdigest() == FROZEN[script]
