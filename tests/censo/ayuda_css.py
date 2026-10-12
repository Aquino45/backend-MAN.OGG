"""Lectura mínima de `identidad.css` para los tests: bloques, variables y contraste WCAG."""

import re

COLOR_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
MEZCLA = re.compile(r"color-mix\(\s*in srgb\s*,\s*(.+?)\s+(\d+(?:\.\d+)?)%\s*,\s*(.+)\)$")
VARIABLE = re.compile(r"var\(\s*(--[\w-]+)\s*\)")
NOMBRADOS = {"black": (0, 0, 0), "white": (255, 255, 255)}


def sin_comentarios(texto):
    return re.sub(r"/\*.*?\*/", "", texto, flags=re.S)


def bloques(texto):
    """Lista de (selector, declaraciones) de las reglas de la hoja, en orden."""
    resultado = []
    for selector, cuerpo in re.findall(r"([^{}@]+)\{([^{}]*)\}", sin_comentarios(texto)):
        pares = re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", cuerpo)
        declaraciones = {nombre: " ".join(valor.split()) for nombre, valor in pares}
        resultado.append((" ".join(selector.split()), declaraciones))
    return resultado


def variables_del_tema(texto, tema):
    """Variables de un tema: las de `:root` y, en oscuro, las de `html.dark` encima."""
    mapa = {}
    for selector, declaraciones in bloques(texto):
        if selector == ":root" or (tema == "oscuro" and selector == "html.dark"):
            mapa.update(declaraciones)
    return mapa


def color_de(variable, mapa):
    """Resuelve una variable a (r, g, b) en 0-255, siguiendo var() y color-mix()."""
    return resolver(mapa[variable], mapa)


def resolver(valor, mapa):
    valor = valor.strip()
    if enlace := VARIABLE.fullmatch(valor):
        return resolver(mapa[enlace.group(1)], mapa)
    if valor in NOMBRADOS:
        return NOMBRADOS[valor]
    if COLOR_HEX.fullmatch(valor):
        digitos = valor.lstrip("#")
        return tuple(int(digitos[i : i + 2], 16) for i in (0, 2, 4))
    if mezcla := MEZCLA.match(valor):
        primero = resolver(mezcla.group(1), mapa)
        segundo = resolver(mezcla.group(3), mapa)
        parte = float(mezcla.group(2)) / 100
        return tuple(
            round(a * parte + b * (1 - parte)) for a, b in zip(primero, segundo, strict=True)
        )
    raise ValueError(f"No se puede resolver el color: {valor}")


def _luminancia(color):
    def canal(valor):
        valor /= 255
        return valor / 12.92 if valor <= 0.03928 else ((valor + 0.055) / 1.055) ** 2.4

    rojo, verde, azul = (canal(c) for c in color)
    return 0.2126 * rojo + 0.7152 * verde + 0.0722 * azul


def contraste(primero, segundo):
    claro, oscuro = sorted((_luminancia(primero), _luminancia(segundo)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)
