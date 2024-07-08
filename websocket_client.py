import socketio
import json
import time
from PySide6.QtCore import Signal, QThread


class WebSocketClient(QThread):
    signal_sound = Signal(str)

    def __init__(self, web_url):
        super().__init__()
        if "https" in web_url:
            self.web_url = web_url.replace("https", "wss")
        else:
            self.web_url = web_url.replace("http", "ws")

        self.sio = socketio.Client(logger=True, engineio_logger=True)

        # Connexion aux événements WebSocket
        self.sio.on('connect', self.on_connect, namespace='/socket_app_screen')
        self.sio.on('disconnect', self.on_disconnect, namespace='/socket_app_screen')
        self.sio.on('update', self.on_update, namespace='/socket_app_screen')      


    def run(self):
        while True:
            try:
                self.sio.connect(self.web_url, namespaces=['/socket_app_screen'])
                self.sio.wait()  # Maintenir la connexion ouverte
            except socketio.exceptions.ConnectionError as e:
                print(f"Connection lost: {e}")
                time.sleep(5)  # Attendre 5 secondes avant de tenter une reconnexion
                print("Attempting to reconnect...")

    def stop(self):
        self.sio.disconnect()
        self.quit()
        self.wait()

    def on_connect(self):
        print('WebSocket connected et c cool')

    def on_disconnect(self):
        print('WebSocket disconnected')


    def on_update(self, data):
        print("Received update:", data)
        try:
            if isinstance(data, str):
                data = json.loads(data)
            print(data)
            if data['flag'] == 'sound':
                print("Emitting signal with message:", data['data'])
                self.signal_sound.emit(data['data'])
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON: {e}")
            

