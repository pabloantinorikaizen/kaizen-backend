import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# Inicialización de la App
app = Flask(__name__)

# Configuración de variables (Asegúrate de cargarlas en Vercel Settings)
TOKKO_API_KEY = os.environ.get("TOKKO_API_KEY", "")
META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "KA_IZEN_VERIFY_2024")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)

def buscar_en_tokko(query_texto):
    if not TOKKO_API_KEY: return []
    url = "https://tokkobroker.com/api/v1/property/search/"
    params = {
        "key": TOKKO_API_KEY,
        "format": "json",
        "lang": "es",
        "data": f'{{"text": "{query_texto}", "current_localization_id": 0}}'
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        return response.json().get('objects', [])[:3]
    except:
        return []

def procesar_con_ia(mensaje_usuario, propiedades_tokko):
    if not OPENAI_API_KEY: return "Error de configuración de IA."
    
    info = ""
    for p in propiedades_tokko:
        try:
            op = p['operations'][0]
            info += f"- {p['publication_title']} | {op['prices'][0]['currency']} {op['prices'][0]['price']}\n"
        except: continue

    prompt = f"Eres el asistente de Kaizen Propiedades. Usa esta info: {info}"
    
    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": mensaje_usuario}]
        )
        return res.choices[0].message.content
    except:
        return "Gracias por contactar a Kaizen. Un asesor te escribirá pronto."

def enviar_mensaje_meta(recipient_id, texto):
    if not META_ACCESS_TOKEN: return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={META_ACCESS_TOKEN}"
    requests.post(url, json={"recipient": {"id": recipient_id}, "message": {"text": texto}}, timeout=10)

@app.route('/')
def home():
    return "Servidor Kaizen Propiedades OK"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == META_VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token incorrecto", 403

    if request.method == 'POST':
        data = request.json
        try:
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    if event.get('message') and event['message'].get('text'):
                        sid = event['sender']['id']
                        msg = event['message']['text']
                        props = buscar_en_tokko(msg)
                        resp = procesar_con_ia(msg, props)
                        enviar_mensaje_meta(sid, resp)
            return "EVENT_RECEIVED", 200
        except:
            return "OK", 200

# Vercel necesita que el objeto se llame 'app'
