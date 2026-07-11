"""
Cliente para la API de moderación de texto, con pruebas incluidas.

Requiere: pip install requests

Uso:
    python client.py <comando> <ip:puerto> [texto]

Comandos:
    moderate  <ip:puerto> <texto>   -> envía el texto indicado y muestra la respuesta
    allowed   <ip:puerto> [texto]   -> prueba con texto permitido (usa uno por defecto si se omite)
    bloqued   <ip:puerto> [texto]   -> prueba con texto que debería bloquearse
    error400  <ip:puerto>           -> prueba enviando texto vacío (esperado: 400)
    error500  <ip:puerto>           -> prueba enviando payload sin el campo 'text' (esperado: 500/422)
    all       <ip:puerto>           -> corre las 4 pruebas anteriores en orden

Ejemplos:
    python client.py moderate 127.0.0.1:8000 "hola mundo"
    python client.py allowed 127.0.0.1:8000
    python client.py bloqued 192.168.1.10:8080
    python client.py error400 127.0.0.1:8000
    python client.py error500 127.0.0.1:8000
    python client.py all 127.0.0.1:8000
"""

import sys
import requests

DEFAULT_ALLOWED_TEXT = "hola, este es un texto normal y sin problemas"
DEFAULT_BLOQUED_TEXT = "este texto contiene palabra_prohibida en el medio"


def build_url(ip_port: str) -> str:
    return f"http://{ip_port}/moderate"


def call_api(url: str, text=None, send_no_text=False):
    """Llama a la API y devuelve (status_code, body). Imprime la respuesta cruda."""
    payload = {} if send_no_text else {"text": text}

    print(f"URL:      {url}")
    print(f"Payload:  {payload}")

    try:
        response = requests.post(url, json=payload, timeout=10)
    except requests.exceptions.ConnectionError as exc:
        print(f"Error de conexión: no se pudo contactar {url}")
        print(exc)
        return None, None

    print(f"Status code: {response.status_code}")
    print(f"Reason:      {response.reason}")
    try:
        body = response.json()
        print(f"Respuesta:   {body}")
        if isinstance(body, dict) and "verdict" in body:
            print(f"  verdict:    {body.get('verdict')}")
            print(f"  confidence: {body.get('confidence')}")
            print(f"  reason:     {body.get('reason')}")
    except ValueError:
        body = response.text
        print(f"Respuesta (no JSON): {body}")

    return response.status_code, body


# ---------- Casos de prueba ----------

def test_moderate(url, text):
    print("=== Moderar texto ===")
    call_api(url, text=text)


def test_allowed(url, text=None):
    print("=== Test: allowed ===")
    call_api(url, text=text or DEFAULT_ALLOWED_TEXT)


def test_bloqued(url, text=None):
    print("=== Test: bloqued ===")
    call_api(url, text=text or DEFAULT_BLOQUED_TEXT)


def test_error400(url, text=None):
    print("=== Test: error 400 (texto vacío) ===")
    call_api(url, text="   ")


def test_error500(url, text=None):
    print("=== Test: error 500 (payload inválido, sin campo 'text') ===")
    call_api(url, send_no_text=True)


def test_all(url, text=None):
    for fn in (test_allowed, test_bloqued, test_error400, test_error500):
        fn(url)
        print()


COMMANDS = {
    "moderate": test_moderate,
    "allowed": test_allowed,
    "bloqued": test_bloqued,
    "error400": test_error400,
    "error500": test_error500,
    "all": test_all,
}


def print_usage():
    print(f"Uso: python {sys.argv[0]} <comando> <ip:puerto> [texto]")
    print(f"Comandos disponibles: {', '.join(COMMANDS)}")


def main():
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]
    ip_port = sys.argv[2]
    text = sys.argv[3] if len(sys.argv) > 3 else None

    if command not in COMMANDS:
        print(f"Comando desconocido: {command}")
        print_usage()
        sys.exit(1)

    if command == "moderate" and not text:
        print("El comando 'moderate' requiere un texto.")
        print_usage()
        sys.exit(1)

    url = build_url(ip_port)
    COMMANDS[command](url, text)


if __name__ == "__main__":
    main()