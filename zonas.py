"""Registro central de zonas: nombre lindo -> cómo se filtra en cada fuente.

Una sola fuente de verdad para las zonas. El config (filtros.zonas) usa los
nombres de acá; main.py resuelve a los ids/slugs de cada portal.

- lavoz: id de location (tid_location_should) de la API de La Voz.
- argenprop: slug de búsqueda (None si esa zona no existe en Argenprop).
"""

# Para sumar una zona nueva: conseguir su id de location en La Voz (aparece en la
# agregación ss... 'Barrio' de su API) y su slug de Argenprop. Pedímelo y lo agrego.
ZONAS = {
    "Nueva Córdoba": {"lavoz": 5034, "argenprop": "nueva-cordoba"},
    "Centro":        {"lavoz": 4910, "argenprop": "centro"},
    "Güemes":        {"lavoz": 4958, "argenprop": None},
    "General Paz":   {"lavoz": 4951, "argenprop": "general-paz"},
}

# Nombres disponibles para ofrecer en el wizard del bot.
NOMBRES = list(ZONAS.keys())


def resolver(nombres, fuente):
    """Devuelve los ids/slugs de `fuente` para la lista de nombres de zona dada."""
    out = []
    for n in nombres or []:
        z = ZONAS.get(n)
        if z and z.get(fuente):
            out.append(z[fuente])
    return out
