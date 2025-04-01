import os
import paramiko
import time
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
import threading
import logging
from datetime import datetime
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация SSH
SSH_HOST = os.environ.get('SSH_HOST', '34.88.223.194')
SSH_PORT = int(os.environ.get('SSH_PORT', 22))
SSH_USER = os.environ.get('SSH_USER', 'zokirjonovjavohir61')
SSH_KEY_PATH = os.environ.get('SSH_KEY_PATH', 'id_rsa')
LOG_FILE_PATH = "/home/zokirjonovjavohir61/.steam/steam/steamapps/common/Counter-Strike\\ Global\\ Offensive/game/bin/linuxsteamrt64/cs2_log.txt"

# Конфигурация Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальные переменные
ssh_client = None
log_thread = None
stop_thread = False
last_log_position = 0

def get_ssh_client():
    """Создает и возвращает SSH клиент"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Пробуем загрузить ключ
        try:
            key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
            client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, pkey=key)
        except Exception as e:
            logger.error(f"Ошибка при подключении с ключом: {e}")
            # Если не удалось подключиться с ключом, пробуем без него
            # (для тестирования или если ключ добавлен в authorized_keys)
            client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER)
            
        return client
    except Exception as e:
        logger.error(f"Ошибка SSH подключения: {e}")
        return None

def execute_ssh_command(command):
    """Выполняет команду на сервере по SSH"""
    try:
        client = get_ssh_client()
        if not client:
            return "Ошибка подключения к серверу"
        
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        client.close()
        
        if error:
            logger.error(f"Ошибка выполнения команды: {error}")
            return error
        return output
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды: {e}")
        return f"Ошибка: {str(e)}"

def tail_log_file():
    """Читает лог-файл и отправляет обновления через WebSocket"""
    global stop_thread, last_log_position
    
    while not stop_thread:
        try:
            client = get_ssh_client()
            if not client:
                socketio.emit('log_error', {'error': 'Не удалось подключиться к серверу'})
                time.sleep(5)
                continue
            
            # Проверяем существование файла
            check_cmd = f"ls -la {LOG_FILE_PATH} 2>/dev/null || echo 'File not found'"
            stdin, stdout, stderr = client.exec_command(check_cmd)
            result = stdout.read().decode().strip()
            
            if 'File not found' in result:
                socketio.emit('log_update', {'lines': ['Лог-файл не найден. Возможно, сервер не запущен.']})
                time.sleep(5)
                client.close()
                continue
            
            # Получаем размер файла
            stdin, stdout, stderr = client.exec_command(f"stat -c %s {LOG_FILE_PATH}")
            file_size = int(stdout.read().decode().strip())
            
            # Если файл уменьшился (был перезаписан), начинаем читать сначала
            if file_size < last_log_position:
                last_log_position = 0
            
            # Если есть новые данные, читаем их
            if file_size > last_log_position:
                stdin, stdout, stderr = client.exec_command(f"tail -c +{last_log_position + 1} {LOG_FILE_PATH}")
                new_content = stdout.read().decode()
                
                # Обновляем позицию
                last_log_position = file_size
                
                # Разбиваем на строки и отправляем
                if new_content:
                    lines = new_content.splitlines()
                    # Форматируем логи для лучшего отображения
                    formatted_lines = []
                    for line in lines:
                        # Добавляем цветовое форматирование для важных сообщений
                        if "error" in line.lower() or "critical" in line.lower():
                            line = f"<span class='text-danger'>{line}</span>"
                        elif "warning" in line.lower():
                            line = f"<span class='text-warning'>{line}</span>"
                        elif "connected" in line.lower() or "success" in line.lower():
                            line = f"<span class='text-success'>{line}</span>"
                        formatted_lines.append(line)
                    
                    socketio.emit('log_update', {'lines': formatted_lines})
            
            client.close()
            time.sleep(1)  # Пауза между проверками
            
        except Exception as e:
            logger.error(f"Ошибка при чтении лога: {e}")
            socketio.emit('log_error', {'error': str(e)})
            time.sleep(5)

def get_server_status():
    """Проверяет статус сервера"""
    output = execute_ssh_command("screen -ls | grep cs2_console")
    return "running" if "cs2_console" in output else "stopped"

def start_cs2_server():
    """Запускает CS2 сервер в screen cs2_console"""
    command = (
        "screen -dmS cs2_console bash -c '"
        "cd /home/zokirjonovjavohir61/.steam/steam/steamapps/common/Counter-Strike\\ Global\\ Offensive/game/bin/linuxsteamrt64/ && "
        "chmod +x start.sh && ./start.sh > cs2_log.txt 2>&1'"
    )
    return execute_ssh_command(command)

def stop_cs2_server():
    """Останавливает CS2 сервер"""
    return execute_ssh_command("screen -S cs2_console -X quit")

def update_cs2_server():
    """Обновляет CS2 сервер"""
    return execute_ssh_command("steamcmd +login anonymous +app_update 730 +quit")

@app.route('/')
def index():
    """Главная страница"""
    status = get_server_status()
    return render_template('index.html', status=status)

@app.route('/api/status')
def api_status():
    """API для получения статуса сервера"""
    status = get_server_status()
    return jsonify({'status': status})

@app.route('/api/start', methods=['POST'])
def api_start():
    """API для запуска сервера"""
    result = start_cs2_server()
    return jsonify({'result': 'success', 'message': 'Сервер запущен'})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """API для остановки сервера"""
    result = stop_cs2_server()
    return jsonify({'result': 'success', 'message': 'Сервер остановлен'})

@app.route('/api/update', methods=['POST'])
def api_update():
    """API для обновления сервера"""
    result = update_cs2_server()
    return jsonify({'result': 'success', 'message': 'Сервер обновлен'})

@app.route('/api/command', methods=['POST'])
def api_command():
    """API для отправки команды на сервер"""
    command = request.json.get('command')
    if not command:
        return jsonify({'result': 'error', 'message': 'Команда не указана'})
    
    result = execute_ssh_command(f"screen -S cs2_console -X stuff '{command}\n'")
    return jsonify({'result': 'success', 'message': f'Команда "{command}" отправлена'})

@socketio.on('connect')
def handle_connect():
    """Обработчик подключения WebSocket"""
    global log_thread, stop_thread
    
    # Запускаем поток для чтения логов, если он еще не запущен
    if log_thread is None or not log_thread.is_alive():
        stop_thread = False
        log_thread = threading.Thread(target=tail_log_file)
        log_thread.daemon = True
        log_thread.start()

@socketio.on('disconnect')
def handle_disconnect():
    """Обработчик отключения WebSocket"""
    # Мы не останавливаем поток, так как могут быть другие подключения
    pass

@app.route('/api/clear_logs', methods=['POST'])
def api_clear_logs():
    """API для очистки лог-файла"""
    result = execute_ssh_command(f"> {LOG_FILE_PATH}")
    global last_log_position
    last_log_position = 0
    return jsonify({'result': 'success', 'message': 'Логи очищены'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)

