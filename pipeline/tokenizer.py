import os
import logging
from ff3 import FF3Cipher

logger = logging.getLogger(__name__)
_cipher_instance = None


def _get_cipher():
    global _cipher_instance
    if _cipher_instance is None:
        key       = os.environ.get("FPE_KEY",   "6f8b3d2a1e9c4f7b0d5a2e8c3f6b9d1a")
        tweak     = os.environ.get("FPE_TWEAK", "tfmt2024")
        tweak_hex = tweak.encode("utf-8").hex().upper().ljust(16, "0")[:16]
        _cipher_instance = FF3Cipher(key, tweak_hex, 10)
        logger.info("FF3-1 cipher inicializado (radix=10)")
    return _cipher_instance


def tokenize_cedula(cedula):
    if not cedula:
        return None
    c = str(cedula).strip()
    if not c.isdigit() or len(c) != 10:
        return None
    try:
        return _get_cipher().encrypt(c)
    except Exception as e:
        logger.error("Error al tokenizar cedula: %s", e)
        return None


def detokenize_cedula(token):
    if not token or not str(token).isdigit() or len(str(token)) != 10:
        return None
    try:
        return _get_cipher().decrypt(str(token))
    except Exception as e:
        logger.error("Error al destokenizar: %s", e)
        return None


def verify_fpe_roundtrip(test_cedula="1712345678"):
    token     = tokenize_cedula(test_cedula)
    recovered = detokenize_cedula(token)
    ok        = (recovered == test_cedula)
    if ok:
        logger.info("FPE roundtrip OK: %s -> %s -> %s", test_cedula, token, recovered)
    else:
        logger.error("FPE roundtrip FALLO: %s -> %s -> %s", test_cedula, token, recovered)
    return ok