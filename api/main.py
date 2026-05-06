import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# Inicializamos la aplicación Flask
app = Flask(__name__)

# --- CONFIGURACIÓN DE APIS (Variables de Entorno) ---
# En Vercel, estas se configuran en el panel de 'Environment Variables'
TOKKO_API_KEY = os.environ.get("TOKKO_API_KEY", "")
META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "KA_IZEN_VERIFY_2024")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Cliente de OpenAI para la Inteligencia Artificial
client = OpenAI(api_key=OPENAI_API_KEY)

# =====================================================================
# 1. FUNCIÓN PARA CONSULTAR PROPIEDADES EN TOKKO BROKER
# =====================================================================
def buscar_en_tokko(query_texto):
    """Consulta la API de Tokko Broker para obtener propiedades reales."""
    url = "https://tokkobroker.com/api/v1/property/search/"
    params = {
        "key": TOKKO_API_KEY,
        "format": "json",
        "lang": "es",
        "data": f'{{"text": "{query_texto}", "current_localization_id": 0}}'
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        # Retornamos los primeros 3 resultados para no saturar el mensaje
        return data.get('objects', [])[:3]
    except Exception as e:
        print(f"Error consultando Tokko: {e}")
        return []

# =====================================================================
# 2. LÓGICA DE INTELIGENCIA ARTIFICIAL (OpenAI)
# =====================================================================
def procesar_con_ia(mensaje_usuario, propiedades_tokko):
    """Genera una respuesta profesional usando GPT-4o."""
    # Estructuramos la información de las propiedades para el modelo de IA
    info_propiedades = ""
    for p in propiedades_tokko:
        try:
            op = p['operations'][0]
            precio = f"{op['prices'][0]['currency']} {op['prices'][0]['price']}"
            info_propiedades += f"- {p['publication_title']} | Precio: {precio} | Link: https://www.kaizen.com.ar/p/{p['id']}\n"
        except:
            continue

    prompt_sistema = f"""
    Eres el asistente inteligente de Kaizen Propiedades. Tu tono debe ser servicial, profesional y ejecutivo.
    Usa la siguiente información de propiedades obtenida de Tokko Broker para responder:
    
    {info_propiedades if info_propiedades else "No se encontraron propiedades específicas en esta búsqueda."}
    
    Reglas:
    1. Si hay propiedades que coincidan, preséntalas de forma atractiva.
    2. Si no hay propiedades, ofrece buscar alternativas y solicita su número de WhatsApp para contactarlo personalmente.
    3. Tu meta final es coordinar una visita o conseguir el contacto telefónico.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": mensaje_usuario}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error en OpenAI: {e}")
        return "¡Hola! Gracias por contactar a Kaizen. Un asesor se comunicará contigo a la brevedad."

# =====================================================================
# 3. FUNCIÓN PARA ENVIAR RESPUESTA A META (FB/IG)
# =====================================================================
def enviar_mensaje_meta(recipient_id, texto_respuesta):
    """Envía el mensaje generado de vuelta al usuario a través de la API de Graph."""
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={META_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": texto_respuesta}
    }
    requests.post(url, json=payload)

# =====================================================================
# 4. RUTAS DEL SERVIDOR (Webhooks)
# =====================================================================
@app.route('/')
def home():
    return "Servidor Kaizen Propiedades OK"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # Verificación del Webhook por parte de Meta
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == META_VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token de verificación incorrecto", 403

    # Recepción de mensajes en tiempo real
    if request.method == 'POST':
        data = request.json
        try:
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    if event.get('message') and event['message'].get('text'):
                        sender_id = event['sender']['id']
                        user_message = event['message']['text']

                        # Lógica de procesamiento
                        propiedades = buscar_en_tokko(user_message)
                        respuesta = procesar_con_ia(user_message, propiedades)
                        
                        # Respuesta al usuario
                        enviar_mensaje_meta(sender_id, respuesta)
            
            return "EVENT_RECEIVED", 200
        except Exception as e:
            print(f"Error en Webhook POST: {e}")
            return "OK", 200

# Esta línea es para ejecución local, Vercel ignora esto y usa 'app'
if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)))
