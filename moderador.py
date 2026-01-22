import os
import time
import logging
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class YouTubeModerator:
    def __init__(self):
        self.youtube = self.get_authenticated_service()
        self.bot_channel_id = self.get_my_channel_id() # Identificamos al bot
        self.live_chat_id = None
        self.next_page_token = None
        
        self.keywords_respuestas = {
            "horarios": "Nuestras reuniones son: Domingos 10:00 AM y Miércoles 7:00 PM.",
            "reunion": "Las reuniones principales son los domingos a las 10:00 AM.",
            "ubicacion": "Estamos ubicados en Calle Falsa 123."
        }
        self.insultos = ["tonto", "idiota"]
        self.user_cooldowns = {}
        self.COOLDOWN_SECONDS = 0 

    def get_authenticated_service(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json', 
            scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
        )
        credentials = flow.run_local_server(port=0)
        return build('youtube', 'v3', credentials=credentials)

    def get_my_channel_id(self):
        """Obtiene el ID del bot para que no se responda a sí mismo."""
        res = self.youtube.channels().list(part="id", mine=True).execute()
        return res['items'][0]['id']

    def get_live_chat_id(self, video_id):
        try:
            response = self.youtube.videos().list(part='liveStreamingDetails', id=video_id).execute()
            return response['items'][0]['liveStreamingDetails'].get('activeLiveChatId')
        except: return None

    def sincronizar_inicio(self):
        response = self.youtube.liveChatMessages().list(liveChatId=self.live_chat_id, part='snippet').execute()
        self.next_page_token = response.get('nextPageToken')

    def enviar_mensaje(self, texto):
        try:
            self.youtube.liveChatMessages().insert(
                part='snippet',
                body={'snippet': {'liveChatId': self.live_chat_id, 'type': 'textMessageEvent', 'textMessageDetails': {'messageText': texto}}}
            ).execute()
        except Exception as e: logging.error(f"Error envío: {e}")

    def borrar_mensaje(self, message_id):
        try: self.youtube.liveChatMessages().delete(id=message_id).execute()
        except: pass

    def procesar_mensajes(self):
        try:
            response = self.youtube.liveChatMessages().list(
                liveChatId=self.live_chat_id,
                part='snippet,authorDetails',
                pageToken=self.next_page_token
            ).execute()

            self.next_page_token = response.get('nextPageToken')
            messages = response.get('items', [])
            ahora = time.time()

            for msg in messages:
                user_id = msg['authorDetails']['channelId']
                
                # REGLA DE ORO: El bot solo se ignora a SÍ MISMO
                if user_id == self.bot_channel_id:
                    continue

                texto = msg['snippet']['displayMessage'].lower()
                autor = msg['authorDetails']['displayName']

                # Moderación
                if any(insulto in texto for insulto in self.insultos):
                    self.borrar_mensaje(msg['id'])
                    continue

                # Cooldown check
                if user_id in self.user_cooldowns:
                    if ahora - self.user_cooldowns[user_id] < self.COOLDOWN_SECONDS:
                        continue # Ignora si spamea antes de 60 seg

                for clave, respuesta in self.keywords_respuestas.items():
                    if clave in texto:
                        self.enviar_mensaje(f"@{autor} {respuesta}")
                        self.user_cooldowns[user_id] = ahora # Bloquea al usuario por 60s
                        break 

        except Exception as e: logging.error(f"Error ciclo: {e}")

    def ejecutar(self, video_id):
        self.live_chat_id = self.get_live_chat_id(video_id)
        if not self.live_chat_id: return
        self.sincronizar_inicio()
        print("🚀 Bot en línea. Te responderá a ti también (pero solo una vez por minuto).")
        while True:
            self.procesar_mensajes()
            time.sleep(5) # Bajamos a 5s para que sea más ágil

if __name__ == "__main__":
    v_id = input("ID Video: ")
    YouTubeModerator().ejecutar(v_id)