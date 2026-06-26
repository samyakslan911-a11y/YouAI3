"""
Agente de investigación botánica: Gemini + Google Search grounding.
Busca información precisa y actualizada sobre el tema ANTES de generar
los slides, para que el contenido sea veraz y detallado.
"""
import logging
import os
import re

log = logging.getLogger(__name__)

_RESEARCH_PROMPT = """\
Eres un botánico experto con acceso a fuentes científicas actualizadas.
Investiga exhaustivamente sobre: "{topic}"

Usa Google Search para obtener información precisa y actual. Luego proporciona:

## DATOS CIENTÍFICOS
- Nombre científico completo (género, especie, familia)
- Origen geográfico y hábitat natural
- Descripción botánica (forma, tamaño, características distintivas)

## CUIDADOS PRECISOS
- LUZ: tipo exacto (directa intensa / indirecta brillante / sombra parcial / etc.), horas recomendadas
- RIEGO: frecuencia específica por estación, señales de exceso y déficit
- HUMEDAD: porcentaje ideal, métodos para mantenerla
- TEMPERATURA: rango mínimo y máximo en °C, tolerancia a heladas
- SUELO: composición exacta (% turba, perlita, sustrato, pH ideal)
- FERTILIZACIÓN: tipo, frecuencia, dosis
- TRASPLANTE: frecuencia, señales de que lo necesita

## PROBLEMAS COMUNES (con soluciones específicas)
- Plagas más frecuentes y cómo eliminarlas
- Enfermedades comunes (hongos, bacterias) y tratamiento
- Problemas por cuidado incorrecto (hojas amarillas, caída, manchas) y causas exactas

## DATOS CURIOSOS Y VALOR
- 3-5 datos sorprendentes o poco conocidos
- Beneficios reales (purificación de aire con datos si existen, feng shui, medicinal)
- Historia o curiosidades culturales

## VARIEDADES POPULARES
- Lista de las 3-5 variedades más buscadas con sus diferencias

## SEGURIDAD
- Toxicidad exacta para humanos, perros, gatos (sí/no y qué parte)

## TIPS DE PROPAGACIÓN
- Métodos (esquejes, semillas, división, acodos) con tasas de éxito

Responde en español. Sé específico con datos numéricos. Evita generalidades.
Si no encuentras información para algún punto, dilo claramente.
"""


def research_topic(topic: str) -> str:
    """
    Investiga el tema con Gemini + Google Search grounding.
    Devuelve el contexto experto como string para pasar a generate_content().
    Nunca falla: si hay error, devuelve string vacío (el pipeline continúa).
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        log.warning("GOOGLE_API_KEY no encontrada, saltando investigación")
        return ""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model  = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        prompt = _RESEARCH_PROMPT.format(topic=topic)

        log.info(f"[research] Buscando información sobre: {topic}")
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=4096,
            ),
        )

        text = response.text.strip()
        if not text:
            log.warning("[research] Respuesta vacía de Gemini")
            return ""

        log.info(f"[research] Contexto obtenido: {len(text)} chars")
        return text

    except Exception as e:
        log.warning(f"[research] Error (pipeline continúa sin contexto): {e!r}")
        return ""
