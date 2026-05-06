import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# --- CONFIGURACIÓN DE APIS (Estas las obtienes de tus paneles) ---
TOKKO_API_KEY = "e1cdb7d262bd3759f1f9f4a4ad2881693e37a3ee"
META_VERIFY_TOKEN = "Kaizen2024"
OPENAI_API_KEY = "TU_API_KEY_DE_OPENAI"

client = OpenAI(api_key=OPENAI_API_KEY)

# =====================================================================
# 1. FUNCIÓN PARA CONSULTAR PROPIEDADES EN TOKKO BROKER
# =====================================================================
def buscar_en_tokko(query_texto):
    """
    Busca propiedades en la API real de Tokko filtrando por texto.
    Documentación: https://tokkobroker.com/api/v1/
    """
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
        # Retornamos las primeras 3 propiedades encontradas
        return data.get('objects', [])[:3]
    except Exception as e:
        print(f"Error en Tokko: {e}")
        return []

# =====================================================================
# 2. LÓGICA DE INTELIGENCIA ARTIFICIAL (OpenAI)
# =====================================================================
def procesar_con_ia(mensaje_usuario, propiedades_tokko):
    """
    Toma el mensaje del cliente y las propiedades de Tokko para generar una respuesta.
    """
    # Convertimos la lista de propiedades a un texto que la IA entienda
    lista_propiedades = ""
    for p in propiedades_tokko:
        lista_propiedades += f"- {p['publication_title']} (Precio: {p['operations'][0]['prices'][0]['price']} {p['operations'][0]['prices'][0]['currency']})\n"

    prompt_sistema = f"""
    Eres el asistente estrella de Kaizen Propiedades. 
    Tu objetivo es ser amable y profesional. 
    Si hay propiedades disponibles, ofrécelas. Si no hay, pide el WhatsApp.
    Propiedades actuales en stock:
    {lista_propiedades}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": mensaje_usuario}
        ]
    )
    
    return response.choices[0].message.content

# =====================================================================
# 3. WEBHOOK PARA META (Facebook / Instagram)
# =====================================================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # Verificación inicial de Meta (esto se hace una sola vez)
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == META_VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token de verificación inválido", 403

    # Recepción de mensajes reales
    if request.method == 'POST':
        data = request.json
        # Extraemos el mensaje (la estructura depende de si es FB o IG)
        try:
            mensaje = data['entry'][0]['messaging'][0]['message']['text']
            remitente_id = data['entry'][0]['messaging'][0]['sender']['id']
            
            print(f"Mensaje de {remitente_id}: {mensaje}")

            # 1. Buscamos en Tokko según lo que pidió el cliente
            propiedades = buscar_en_tokko(mensaje)
            
            # 2. Generamos respuesta con IA
            respuesta_final = procesar_con_ia(mensaje, propiedades)
            
            # 3. Aquí iría el código para ENVIAR el mensaje de vuelta a Meta
            # enviar_mensaje_meta(remitente_id, respuesta_final)
            
            return jsonify({"status": "success", "ai_response": respuesta_final}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 200

if __name__ == '__main__':
    # Ejecutamos el servidor en el puerto 5000
    app.run(port=5000, debug=True)