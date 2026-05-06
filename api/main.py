import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# Inicialización de la App Flask
# Vercel requiere que el objeto se llame 'app' para encontrarlo automáticamente
app = Flask(__name__)

# --- CONFIGURACIÓN DE APIS (Variables de Entorno) ---
# Es CRÍTICO que estas variables estén cargadas en Vercel > Settings > Environment Variables
TOKKO_API_KEY = os.environ.get("e1cdb7d262bd3759f1f9f4a4ad2881693e37a3ee", "")
META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "KA_IZEN_VERIFY_2024")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Inicialización segura del cliente OpenAI
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Error inicializando OpenAI: {e}")
    client = None

# =====================================================================
# 1. FUNCIÓN PARA CONSULTAR PROPIEDADES EN TOKKO BROKER
# =====================================================================
def buscar_en_tokko(query_texto):
    if not TOKKO_API_KEY:
        return []
    url = "https://tokkobroker.com/api/v1/property/search/"
    params = {
        "key": TOKKO_API_KEY,
        "format": "json",
        "lang": "es",
        "data": f'{{"text": "{query_texto}", "current_localization_id": 0}}'
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get('objects', [])[:3]
        return []
    except Exception as e:
        print(f"Error en Tokko: {e}")
        return []

# =====================================================================
# 2. LÓGICA DE INTELIGENCIA ARTIFICIAL (OpenAI)
# =====================================================================
def procesar_con_ia(mensaje_usuario, propiedades_tokko):
    if not client or not OPENAI_API_KEY:
        return "Lo siento, el servicio de IA no está configurado correctamente."
    
    info = ""
    for p in propiedades_tokko:
        try:
            op = p['operations'][0]
            precio = f"{op['prices'][0]['currency']} {op['prices'][0]['price']}"
            info += f"- {p['publication_title']} | Precio: {precio}\n"
        except:
            continue

    prompt_sistema = f"""
    Eres el asistente inteligente de Kaizen Propiedades.
    Usa esta info de Tokko para responder: {info if info else 'No hay propiedades exactas ahora.'}
    Si no hay info, pide el teléfono para buscar manualmente.
    """
    
    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": mensaje_usuario}
            ]
        )
        return res.choices[0].message.content
    except Exception as e:
        print(f"Error en OpenAI: {e}")
        return "Gracias por tu mensaje. Un asesor de Kaizen te contactará a la brevedad."

# =====================================================================
# 3. FUNCIÓN PARA ENVIAR RESPUESTA A META (FB/IG)
# =====================================================================
def enviar_mensaje_meta(recipient_id, texto):
    if not META_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={META_ACCESS_TOKEN}"
    try:
        requests.post(url, json={
            "recipient": {"id": recipient_id},
            "message": {"text": texto}
        }, timeout=10)
    except Exception as e:
        print(f"Error enviando a Meta: {e}")

# =====================================================================
# 4. RUTAS DEL SERVIDOR
# =====================================================================
@app.route('/')
def home():
    return "Servidor Kaizen Propiedades OK"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # Validación de Webhook para el panel de Facebook/Instagram
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == META_VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token de verificación inválido", 403

    # Procesamiento de mensajes entrantes
    if request.method == 'POST':
        try:
            data = request.json
            if not data:
                return "No data received", 400

            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    if event.get('message') and event['message'].get('text'):
                        sender_id = event['sender']['id']
                        user_text = event['message']['text']
                        
                        # Ejecución de la lógica de negocio
                        props = buscar_en_tokko(user_text)
                        respuesta = procesar_con_ia(user_text, props)
                        enviar_mensaje_meta(sender_id, respuesta)
            
            return "EVENT_RECEIVED", 200
        except Exception as e:
            print(f"Error procesando webhook: {e}")
            return "Error interno", 500

# Vercel utiliza la variable 'app' directamente, por lo que no hace falta app.run() aquí
