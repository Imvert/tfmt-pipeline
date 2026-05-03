import random
import logging
from datetime import date
from typing import Any, List, Optional
from faker import Faker

logger   = logging.getLogger(__name__)
faker    = Faker("es")
faker_en = Faker("en_US")

CALLES_EC = [
    "Av. Amazonas", "Av. Shyris", "Av. America", "Calle Bolivar",
    "Calle Sucre", "Av. 10 de Agosto", "Av. Colon", "Calle Olmedo",
    "Av. Republica", "Calle Garcia Moreno", "Av. 6 de Diciembre",
]
CIUDADES_EC = [
    "Quito", "Guayaquil", "Cuenca", "Ambato", "Riobamba",
    "Ibarra", "Manta", "Loja", "Esmeraldas", "Portoviejo",
]
DOMINIOS_FAKE = [
    "empresa-fake.ec", "test-corp.com.ec", "demo-biz.ec",
    "prueba-qa.net", "example-test.org",
]


def shuffle_column(values):
    shuffled = values.copy()
    random.shuffle(shuffled)
    for i in range(len(shuffled)):
        if shuffled[i] == values[i]:
            j = (i + 1) % len(shuffled)
            shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    return shuffled


def generate_fake_value(fake_type, original=None):
    generators = {
        "first_name": lambda: faker.first_name()[:10],
        "last_name":  lambda: faker.last_name()[:20],
        "full_name":  lambda: f"{faker.first_name()} {faker.last_name()}"[:60],
        "email":      lambda: f"{faker_en.user_name()[:20]}.qa@{random.choice(DOMINIOS_FAKE)}"[:80],
        "phone_ec":   _generate_phone_ec,
        "address_ec": _generate_address_ec,
        "company":    lambda: faker.company()[:80],
    }
    gen = generators.get(fake_type)
    if gen is None:
        return None
    return gen()


def _generate_phone_ec():
    tipo = random.choice(["fijo_quito", "fijo_gye", "celular"])
    if tipo == "fijo_quito":
        return f"022-{random.randint(200,999):03d}-{random.randint(1000,9999)}"
    elif tipo == "fijo_gye":
        return f"042-{random.randint(200,999):03d}-{random.randint(1000,9999)}"
    else:
        prefijo = random.choice(["09", "098", "099", "096", "097"])
        return f"{prefijo}{random.randint(1000000, 9999999)}"


def _generate_address_ec():
    calle  = random.choice(CALLES_EC)
    numero = f"N{random.randint(10,99)}-{random.randint(10,999)}"
    ciudad = random.choice(CIUDADES_EC)
    return f"{calle} {numero}, {ciudad}"


def partial_mask(value, mask_char="*", keep_start=3, keep_end=2):
    if not value:
        return value
    s = str(value)
    if len(s) <= keep_start + keep_end:
        return mask_char * len(s)
    middle_len = len(s) - keep_start - keep_end
    return s[:keep_start] + (mask_char * middle_len) + s[-keep_end:]


def add_noise(value, noise_pct=10):
    if value is None:
        return None
    factor = 1 + random.uniform(-noise_pct / 100, noise_pct / 100)
    return round(float(value) * factor, 2)


def generalize_date(value, granularity="year"):
    if value is None:
        return None
    if isinstance(value, date):
        if granularity == "year":
            return date(value.year, 1, 1)
    return value


def suppress(_value):
    return None