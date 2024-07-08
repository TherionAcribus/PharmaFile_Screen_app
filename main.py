from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QVBoxLayout, QWidget, 
                                QLineEdit, QPushButton, QDialog, QLabel, QFormLayout, 
                                QMenuBar, QMessageBox, QHBoxLayout)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QSettings, QThread, Signal, QUrl, Slot
from PySide6.QtGui import QAction
from PySide6.QtMultimedia import QMediaPlayer
from requests.exceptions import RequestException
import requests
import json
import time
import sys
import os
from pydub import AudioSegment # Nécessite d'installer FFMPeg + path. A Voir pour linux
import simpleaudio as sa  
import tempfile

from websocket_client import WebSocketClient


default_unlockpass = "aa"


class SSEClient(QThread):
    play_sound = Signal(object)

    def run(self):
        while True:
            try:
                response = requests.get('http://127.0.0.1:5000/events/update_screen_app', stream=True)
                client = response.iter_lines()
                for line in client:
                    if line:
                        print("LINE", line)
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            json_data = decoded_line[5:].strip()
                            data = json.loads(json_data)
                            print(data)
                            print("DATA", data["type"])
                            if data['type'] == 'update_audio':
                                print("Playing sound:", data['data'])
                                self.play_sound.emit(data['data'])
            except RequestException as e:
                print(f"Connection lost: {e}")
                time.sleep(5)  # Wait for 5 seconds before attempting to reconnect
                print("Attempting to reconnect...")

def resource_path(relative_path):
    """ Obtenez le chemin d'accès absolu aux ressources pour le mode PyInstaller. """
    try:
        # PyInstaller crée un dossier temporaire et y stocke le chemin dans _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Préférences")

        self.main_layout = QVBoxLayout(self)

        self.secret_input = QLineEdit(self)
        form_layout = QFormLayout()
        form_layout.addRow("Mot pour débloquer le plein écran:", self.secret_input)

        self.web_url_input = QLineEdit(self)
        form_layout.addRow("URL de la page web:", self.web_url_input)

        self.save_button = QPushButton("Enregistrer", self)
        self.save_button.clicked.connect(self.save_preferences)

        self.main_layout.addLayout(form_layout)
        self.main_layout.addWidget(self.save_button)

        self.setLayout(self.main_layout)
    
    def load_preferences(self):
        settings = QSettings()
        self.web_url_input.setText(settings.value("web_url", "http://localhost:5000"))
        self.secret_input.setText(settings.value("unlockpass", default_unlockpass))

    def save_preferences(self):
        settings = QSettings()
        url = self.web_url_input.text()
        secret = self.secret_input.text()

        if not url:
            QMessageBox.warning(self, "Erreur", "L'URL ne peut pas être vide")
            return
        if not secret:
            QMessageBox.warning(self, "Erreur", "Le mot de passe ne peut pas être vide")
            return
        
        settings.setValue("web_url", url)
        settings.setValue("unlockpass", secret)
        self.accept()

    def get_secret_sequence(self):
        return self.secret_input.text()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.audio_queue = []
        self.is_playing = False        

        self.load_preferences()
        #self.sse_client = SSEClient()
        #self.sse_client.play_sound.connect(self.play_sound)
        #self.sse_client.start()
        self.start_socket_io_client(self.web_url)


        self.web_view = QWebEngineView()
        url = self.web_url + "/display"
        self.web_view.setUrl(url)
        self.setCentralWidget(self.web_view)

        # Fullscreen mode
        self.showFullScreen()

        # Set up shortcut to unlock configuration menu
        self.typed_sequence = ""
        
        # Create Preferences Dialog
        self.preferences_dialog = PreferencesDialog(self)
        self.preferences_dialog.load_preferences()
        
        # Create Menu
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        self.config_menu = QMenu("Menu", self)
        self.menu_bar.addMenu(self.config_menu)

        self.preferences_action = QAction("Préférences", self)
        self.preferences_action.triggered.connect(self.open_preferences)
        self.config_menu.addAction(self.preferences_action)

        self.fullscreen_action = QAction("Plein Écran", self)
        self.fullscreen_action.triggered.connect(self.enter_fullscreen)
        self.config_menu.addAction(self.fullscreen_action)
        
        self.menu_bar.hide()  # Hide the menu bar initially

        
    @Slot(object)
    def queue_sound(self, data):
        self.audio_queue.append(data)
        if not self.is_playing:
            self.play_next_sound()
    
    def play_next_sound(self):
        if not self.audio_queue:
            self.is_playing = False
            return
        
        self.is_playing = True
        data = self.audio_queue.pop(0)
        self.play_sound(data)

    def play_sound(self, sound_url):
        print(sound_url)
        # Télécharger le fichier MP3 depuis l'URL
        response = requests.get(sound_url)
        response.raise_for_status()

        # Stocker le fichier MP3 temporairement
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_mp3:
            temp_mp3.write(response.content)
            temp_mp3_path = temp_mp3.name

        # Lire le fichier MP3 temporaire
        self.sound = AudioSegment.from_mp3(temp_mp3_path)
        self.play_obj = sa.play_buffer(self.sound.raw_data, num_channels=self.sound.channels, bytes_per_sample=self.sound.sample_width, sample_rate=self.sound.frame_rate)
        self.play_obj.wait_done()  # Attendre la fin de la lecture
        self.is_playing = False
        self.play_next_sound()
        
    def start_socket_io_client(self, url):
        print(f"Starting Socket.IO client with URL: {url}")
        self.socket_io_client = WebSocketClient(url)
        self.socket_io_client.signal_sound.connect(self.play_sound)
        #self.socket_io_client.new_notification.connect(self.show_notification)
        #self.socket_io_client.my_patient.connect(self.update_my_patient)
        self.socket_io_client.start() 

    def load_preferences(self):
        settings = QSettings()
        self.web_url = settings.value("web_url", "http://localhost:5000")
        self.unlockpass = settings.value("unlockpass", default_unlockpass)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.ignore()  # Ignore the escape key to prevent exit from fullscreen
        
        # Capture keystrokes for unlocking configuration
        self.typed_sequence += event.text()
        if self.unlockpass in self.typed_sequence:
            self.typed_sequence = ""  # Reset sequence after successful match
            self.showNormal()  # Exit fullscreen mode to show menu bar
            self.menu_bar.show()
        
        super().keyPressEvent(event)
    
    def open_preferences(self):
        if self.preferences_dialog.exec() == QDialog.Accepted:
            new_secret = self.preferences_dialog.get_secret_sequence()
            if new_secret:
                self.unlockpass = new_secret
                settings = QSettings()
                settings.setValue("unlockpass", self.unlockpass)
                print(f"New secret sequence set: {self.unlockpass}")

    def enter_fullscreen(self):
        self.menu_bar.hide()
        self.showFullScreen()

if __name__ == "__main__":
    app = QApplication([])

    app.setApplicationName("ScreenPage")
    app.setOrganizationName("PharmaFile")
    app.setOrganizationDomain("mycompany.com")

    window = MainWindow()
    window.show()
    app.exec()