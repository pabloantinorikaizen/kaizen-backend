import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# Inicialización de la App Flask
# Vercel busca este objeto 'app' dentro de la carpeta 'api'
app = Flask(__name__)

# --- CONFIGURACIÓN DE APIS (Variables de Entorno) ---
TOKKO_API_KEY = os.environ.get("e1cdb7d262bd3759f1f9f4a4ad2881693e37a3ee", "")
META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "KA_IZEN_VERIFY_2024")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Cliente de OpenAI con manejo de errores
try:
    if OPENAI_API_KEY:
        client = OpenAI(api_key=OPENAI_API_KEY)
    else:
        client = None
except Exception:
    client = None

# --- FUNCIONES DE APOYO ---
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
        response = requests.get(url, params=params, timeout=5)
        return response.json().get('objects', [])[:3]
    except:
        return []

def procesar_con_ia(mensaje_usuario, propiedades_tokko):
    if not client:
        return "Servicio de IA temporalmente no disponible."
    
    info = ""
    for p in propiedades_tokko:
        try:
            op = p['operations'][0]
            precio = f"{op['prices'][0]['currency']} {op['prices'][0]['price']}"
            info += f"- {p['publication_title']} | Precio: {precio}\n"
        except:
            continue

    prompt_sistema = f"Eres el asistente de Kaizen Propiedades. Info: {info}"
    
    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": mensaje_usuario}
            ]
        )
        return res.choices[0].message.content
    except:
        return "Gracias por tu interés. Un asesor te contactará."

def enviar_mensaje_meta(recipient_id, texto):
    if not META_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={META_ACCESS_TOKEN}"
    try:
        requests.post(url, json={"recipient": {"id": recipient_id}, "message": {"text": texto}}, timeout=5)
    except:
        pass

# --- RUTAS ---
@app.route('/')
def home():
    return "Servidor Kaizen Propiedades OK - Vercel Funcionando"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Validación de Meta
        verify_token = request.args.get("hub.verify_token")
        if verify_token == META_VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token Inválido", 403

    if request.method == 'POST':
        data = request.json
        try:
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    if 'message' in event and 'text' in event['message']:
                        sid = event['sender']['id']
                        text = event['message']['text']
                        props = buscar_en_tokko(text)
                        resp = procesar_con_ia(text, props)
                        enviar_mensaje_meta(sid, resp)
            return "EVENT_RECEIVED", 200
        except:
            return "OK", 200

# Vercel necesita que el archivo termine sin app.run() para usar su propio manejador.