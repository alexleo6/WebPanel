from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import subprocess
import os
import socket
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import FileField, StringField
from wtforms.validators import InputRequired
from flask_socketio import SocketIO, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a secure secret key
app.config['CONSOLE_PIN'] = 'your_console_pin'  # Replace with your console pin
socketio = SocketIO(app)

# Ensure the SERVER_PATH is correctly set
SERVER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'minecraft_server_host', 'server'))

# Path to Java 11 executable
JAVA_PATH = "/usr/lib/jvm/java-11-openjdk-amd64/bin/java"

# Default Minecraft server port
MINECRAFT_PORT = 25565

def get_local_ip():
    try:
        # Create a temporary socket to get the local IP address
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_socket.connect(("8.8.8.8", 80))
        local_ip = temp_socket.getsockname()[0]
        temp_socket.close()
        return local_ip
    except Exception as e:
        return str(e)

class UploadForm(FlaskForm):
    plugin = FileField('plugin', validators=[InputRequired()])

class ConsolePinForm(FlaskForm):
    pin = StringField('PIN', validators=[InputRequired()])

@app.route('/')
def index():
    form = UploadForm()
    return render_template('index.html', form=form)

@app.route('/console', methods=['GET', 'POST'])
def console():
    form = ConsolePinForm()
    if form.validate_on_submit():
        if form.pin.data == app.config['CONSOLE_PIN']:
            session['authenticated'] = True
            return render_template('console.html')
        else:
            return "Invalid PIN", 403
    return render_template('console_pin.html', form=form)

@app.route('/start', methods=['POST'])
def start_server():
    try:
        with open(os.path.join(SERVER_PATH, 'server.log'), 'w') as log_file:
            subprocess.Popen([JAVA_PATH, '-Xmx1024M', '-Xms1024M', '-jar', 'paper-1.16.4-416.jar', 'nogui'], cwd=SERVER_PATH, stdout=log_file, stderr=log_file)
        local_ip = get_local_ip()
        return jsonify({"status": "started", "ip": local_ip, "port": MINECRAFT_PORT})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/stop', methods=['POST'])
def stop_server():
    try:
        subprocess.run(['pkill', '-f', 'paper-1.16.4-416.jar'], cwd=SERVER_PATH)
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/restart', methods=['POST'])
def restart_server():
    try:
        stop_server()
        start_server()
        return jsonify({"status": "restarted"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/upload_plugin', methods=['POST'])
def upload_plugin():
    form = UploadForm()
    if form.validate_on_submit():
        filename = secure_filename(form.plugin.data.filename)
        form.plugin.data.save(os.path.join(SERVER_PATH, 'plugins', filename))
        return jsonify({"status": "success", "message": f"Plugin {filename} uploaded successfully"})
    return jsonify({"status": "error", "message": "No plugin file provided"})

def tail_logs():
    log_file_path = os.path.join(SERVER_PATH, 'server.log')
    while True:
        try:
            with open(log_file_path, 'r') as log_file:
                log_file.seek(0, 2)  # Move to the end of the file
                while True:
                    line = log_file.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    socketio.emit('log_update', {'data': line})
        except Exception as e:
            print(f"Error reading log file: {e}")
            time.sleep(1)

if __name__ == '__main__':
    socketio.start_background_task(target=tail_logs)
    socketio.run(app, debug=True)