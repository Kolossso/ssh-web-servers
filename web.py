import os
import paramiko
import time
from flask import Flask, render_template, jsonify, request

# Настройка SSH
SSH_HOST = "34.88.223.194"
SSH_PORT = 22
SSH_USER = "zokirjonovjavohir61"
SSH_KEY_PATH = "id_rsa"
LOG_FILE_PATH = "/home/zokirjonovjavohir61/.steam/steam/steamapps/common/Counter-Strike\\ Global\\ Offensive/game/bin/linuxsteamrt64/cs2_log.txt"

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

def get_ssh_client():
    """Создает и возвращает SSH клиент"""
    try:
        key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, pkey=key)
        return client
    except Exception as e:
        print(f"Ошибка SSH подключения: {e}")
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
        
        return output if output else error
    except Exception as e:
        print(f"Ошибка при выполнении команды: {e}")
        return f"Ошибка: {str(e)}"

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

def get_logs(lines=100):
    """Получает последние строки лога"""
    try:
        client = get_ssh_client()
        if not client:
            return ["Ошибка подключения к серверу"]
        
        # Проверяем существование файла
        check_cmd = f"ls -la {LOG_FILE_PATH} 2>/dev/null || echo 'File not found'"
        stdin, stdout, stderr = client.exec_command(check_cmd)
        result = stdout.read().decode().strip()
        
        if 'File not found' in result:
            client.close()
            return ["Лог-файл не найден. Возможно, сервер не запущен."]
        
        # Получаем последние строки лога
        stdin, stdout, stderr = client.exec_command(f"tail -n {lines} {LOG_FILE_PATH}")
        log_content = stdout.read().decode().strip()
        client.close()
        
        if not log_content:
            return ["Лог-файл пуст."]
        
        return log_content.split('\n')
    except Exception as e:
        print(f"Ошибка при получении логов: {e}")
        return [f"Ошибка: {str(e)}"]

@app.route('/')
def index():
    """Главная страница"""
    status = get_server_status()
    logs = get_logs(50)
    return render_template('index.html', status=status, logs=logs, host=SSH_HOST)

@app.route('/api/status')
def api_status():
    """API для получения статуса сервера"""
    status = get_server_status()
    return jsonify({'status': status})

@app.route('/api/logs')
def api_logs():
    """API для получения логов"""
    lines = request.args.get('lines', 50, type=int)
    logs = get_logs(lines)
    return jsonify({'logs': logs})

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

