import os
import paramiko
import time
import threading
from flask import Flask, render_template, jsonify, request, redirect, url_for
import base64
import re

# Настройка SSH
SSH_HOST = "34.88.223.194"
SSH_PORT = 22
SSH_USER = "zokirjonovjavohir61"
SSH_KEY_PATH = "id_rsa"
LOG_FILE_PATH = "/home/zokirjonovjavohir61/.steam/steam/steamapps/common/Counter-Strike\\ Global\\ Offensive/game/bin/linuxsteamrt64/cs2_log.txt"

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

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

def list_files(path=None):
    """Получает список файлов и директорий по указанному пути"""
    if path is None:
        path = "/home/zokirjonovjavohir61"
    
    try:
        client = get_ssh_client()
        if not client:
            return {"error": "Ошибка подключения к серверу"}
        
        # Проверяем, существует ли путь
        stdin, stdout, stderr = client.exec_command(f"test -e {path} && echo 'exists' || echo 'not exists'")
        path_exists = stdout.read().decode().strip() == 'exists'
        
        if not path_exists:
            client.close()
            return {"error": f"Путь {path} не существует"}
        
        # Проверяем, является ли путь директорией
        stdin, stdout, stderr = client.exec_command(f"test -d {path} && echo 'directory' || echo 'file'")
        is_directory = stdout.read().decode().strip() == 'directory'
        
        if not is_directory:
            client.close()
            return {"error": f"Путь {path} не является директорией"}
        
        # Получаем список файлов с подробной информацией
        # Используем ls -la с экранированием пробелов в пути
        escaped_path = path.replace(' ', '\\ ')
        stdin, stdout, stderr = client.exec_command(f"ls -la {escaped_path}")
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if error:
            # Если есть ошибка, пробуем использовать find для получения списка файлов
            stdin, stdout, stderr = client.exec_command(f"find {escaped_path} -maxdepth 1 -printf '%M %u %g %s %TY-%Tm-%Td %TH:%TM %f\\n'")
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if error:
                client.close()
                return {"error": error}
        
        # Парсим вывод ls -la или find
        files = []
        lines = output.split('\n')
        
        # Пропускаем первую строку (total) если это вывод ls -la
        if lines and lines[0].startswith('total'):
            lines = lines[1:]
        
        for line in lines:
            # Пропускаем пустые строки
            if not line.strip():
                continue
                
            # Парсим строку в зависимости от формата (ls -la или find)
            if line.startswith('d') or line.startswith('-') or line.startswith('l'):
                # Формат ls -la
                parts = line.split(None, 8)
                if len(parts) >= 9:
                    permissions = parts[0]
                    size = parts[4]
                    date = f"{parts[5]} {parts[6]} {parts[7]}"
                    name = parts[8]
                    
                    # Пропускаем . и .. если это не корневая директория
                    if name in ['.', '..'] and path != '/':
                        continue
                    
                    is_dir = permissions.startswith('d')
                    is_link = permissions.startswith('l')
                    
                    # Если это символическая ссылка, извлекаем имя файла
                    if is_link and ' -> ' in name:
                        link_target = name.split(' -> ')[1]
                        # Если ссылка указывает на путь, заканчивающийся на /, это директория
                        if link_target.endswith('/'):
                            is_dir = True
                        name = name.split(' -> ')[0]
                    
                    # Дополнительная проверка для специальных директорий
                    special_dirs = ["root", "sdk64", "steam", ".steam", "steamapps"]
                    if name in special_dirs and not is_dir:
                        # Проверяем, является ли это директорией
                        full_path = f"{path}/{name}" if path != "/" else f"/{name}"
                        full_path = full_path.replace(' ', '\\ ')
                        stdin, stdout, stderr = client.exec_command(f"test -d {full_path} && echo 'yes' || echo 'no'")
                        is_directory = stdout.read().decode().strip() == 'yes'
                        if is_directory:
                            is_dir = True
                    
                    files.append({
                        "name": name,
                        "is_dir": is_dir,
                        "is_link": is_link,
                        "size": size,
                        "date": date,
                        "permissions": permissions
                    })
            else:
                # Формат find
                parts = line.split(None, 6)
                if len(parts) >= 7:
                    permissions = parts[0]
                    size = parts[3]
                    date = f"{parts[4]} {parts[5]}"
                    name = parts[6]
                    
                    # Пропускаем . и .. если это не корневая директория
                    if name in ['.', '..'] and path != '/':
                        continue
                    
                    is_dir = permissions.startswith('d')
                    is_link = permissions.startswith('l')
                    
                    # Дополнительная проверка для специальных директорий
                    special_dirs = ["root", "sdk64", "steam", ".steam", "steamapps"]
                    if name in special_dirs and not is_dir:
                        # Проверяем, является ли это директорией
                        full_path = f"{path}/{name}" if path != "/" else f"/{name}"
                        full_path = full_path.replace(' ', '\\ ')
                        stdin, stdout, stderr = client.exec_command(f"test -d {full_path} && echo 'yes' || echo 'no'")
                        is_directory = stdout.read().decode().strip() == 'yes'
                        if is_directory:
                            is_dir = True
                    
                    files.append({
                        "name": name,
                        "is_dir": is_dir,
                        "is_link": is_link,
                        "size": size,
                        "date": date,
                        "permissions": permissions
                    })
        
        # Если список файлов пуст, пробуем использовать другой метод
        if not files:
            # Используем find с другими параметрами
            stdin, stdout, stderr = client.exec_command(f"find {escaped_path} -maxdepth 1 -type f -o -type d | sort")
            output = stdout.read().decode().strip()
            
            if output:
                lines = output.split('\n')
                for line in lines:
                    if line == path:  # Пропускаем текущую директорию
                        continue
                    
                    name = os.path.basename(line)
                    full_path = line
                    
                    # Проверяем, является ли это директорией
                    stdin, stdout, stderr = client.exec_command(f"test -d {full_path.replace(' ', '\\ ')} && echo 'yes' || echo 'no'")
                    is_dir = stdout.read().decode().strip() == 'yes'
                    
                    # Проверяем, является ли это символической ссылкой
                    stdin, stdout, stderr = client.exec_command(f"test -L {full_path.replace(' ', '\\ ')} && echo 'yes' || echo 'no'")
                    is_link = stdout.read().decode().strip() == 'yes'
                    
                    # Получаем размер файла
                    stdin, stdout, stderr = client.exec_command(f"stat -c '%s' {full_path.replace(' ', '\\ ')}")
                    size = stdout.read().decode().strip()
                    
                    # Получаем дату модификации
                    stdin, stdout, stderr = client.exec_command(f"stat -c '%y' {full_path.replace(' ', '\\ ')}")
                    date = stdout.read().decode().strip()
                    
                    # Получаем права доступа
                    stdin, stdout, stderr = client.exec_command(f"stat -c '%A' {full_path.replace(' ', '\\ ')}")
                    permissions = stdout.read().decode().strip()
                    
                    files.append({
                        "name": name,
                        "is_dir": is_dir,
                        "is_link": is_link,
                        "size": size,
                        "date": date,
                        "permissions": permissions
                    })
        
        client.close()
        return {"files": files, "path": path}
    except Exception as e:
        print(f"Ошибка при получении списка файлов: {e}")
        return {"error": str(e)}

def get_file_content(path):
    """Получает содержимое файла"""
    try:
        client = get_ssh_client()
        if not client:
            return {"error": "Ошибка подключения к серверу"}
        
        # Сначала проверяем, является ли путь директорией
        stdin, stdout, stderr = client.exec_command(f"test -d {path} && echo 'directory' || echo 'file'")
        path_type = stdout.read().decode().strip()
        
        if path_type == 'directory':
            client.close()
            return {"error": "Это директория, а не файл", "is_dir": True, "path": path}
        
        # Проверяем, что это текстовый файл
        stdin, stdout, stderr = client.exec_command(f"file -i {path}")
        file_type = stdout.read().decode().strip()
        
        # Если это не текстовый файл, возвращаем ошибку
        if "text/" not in file_type and "application/json" not in file_type and "application/xml" not in file_type:
            client.close()
            return {"error": "Файл не является текстовым"}
        
        # Получаем содержимое файла
        stdin, stdout, stderr = client.exec_command(f"cat {path}")
        content = stdout.read().decode()
        error = stderr.read().decode().strip()
        
        client.close()
        
        if error:
            return {"error": error}
        
        return {"content": content, "path": path}
    except Exception as e:
        print(f"Ошибка при получении содержимого файла: {e}")
        return {"error": str(e)}

def save_file_content(path, content):
    """Сохраняет содержимое файла"""
    try:
        client = get_ssh_client()
        if not client:
            return {"error": "Ошибка подключения к серверу"}
        
        # Создаем временный файл на сервере
        temp_file = f"/tmp/edit_{int(time.time())}.txt"
        sftp = client.open_sftp()
        
        with sftp.file(temp_file, 'w') as f:
            f.write(content)
        
        # Копируем временный файл в целевой файл
        stdin, stdout, stderr = client.exec_command(f"cat {temp_file} > {path} && rm {temp_file}")
        error = stderr.read().decode().strip()
        
        sftp.close()
        client.close()
        
        if error:
            return {"error": error}
        
        return {"success": True, "message": "Файл успешно сохранен"}
    except Exception as e:
        print(f"Ошибка при сохранении файла: {e}")
        return {"error": str(e)}

def create_file_or_directory(path, name, is_dir=False):
    """Создает файл или директорию"""
    try:
        client = get_ssh_client()
        if not client:
            return {"error": "Ошибка подключения к серверу"}
        
        full_path = os.path.join(path, name).replace('\\', '/')
        
        if is_dir:
            command = f"mkdir -p {full_path}"
        else:
            command = f"touch {full_path}"
        
        stdin, stdout, stderr = client.exec_command(command)
        error = stderr.read().decode().strip()
        
        client.close()
        
        if error:
            return {"error": error}
        
        return {"success": True, "message": f"{'Директория' if is_dir else 'Файл'} успешно создан(а)"}
    except Exception as e:
        print(f"Ошибка при создании файла/директории: {e}")
        return {"error": str(e)}

def delete_file_or_directory(path, is_dir=False):
    """Удаляет файл или директорию"""
    try:
        client = get_ssh_client()
        if not client:
            return {"error": "Ошибка подключения к серверу"}
        
        if is_dir:
            command = f"rm -rf {path}"
        else:
            command = f"rm {path}"
        
        stdin, stdout, stderr = client.exec_command(command)
        error = stderr.read().decode().strip()
        
        client.close()
        
        if error:
            return {"error": error}
        
        return {"success": True, "message": f"{'Директория' if is_dir else 'Файл'} успешно удален(а)"}
    except Exception as e:
        print(f"Ошибка при удалении файла/директории: {e}")
        return {"error": str(e)}

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

@app.route('/api/files')
def api_files():
    """API для получения списка файлов"""
    path = request.args.get('path', '/home/zokirjonovjavohir61')
    result = list_files(path)
    return jsonify(result)

@app.route('/api/file/content')
def api_file_content():
    """API для получения содержимого файла"""
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'Путь к файлу не указан'})
    
    result = get_file_content(path)
    return jsonify(result)

@app.route('/api/file/save', methods=['POST'])
def api_file_save():
    """API для сохранения содержимого файла"""
    path = request.json.get('path')
    content = request.json.get('content')
    
    if not path or content is None:
        return jsonify({'error': 'Путь к файлу или содержимое не указаны'})
    
    result = save_file_content(path, content)
    return jsonify(result)

@app.route('/api/file/create', methods=['POST'])
def api_file_create():
    """API для создания файла или директории"""
    path = request.json.get('path')
    name = request.json.get('name')
    is_dir = request.json.get('is_dir', False)
    
    if not path or not name:
        return jsonify({'error': 'Путь или имя не указаны'})
    
    result = create_file_or_directory(path, name, is_dir)
    return jsonify(result)

@app.route('/api/file/delete', methods=['POST'])
def api_file_delete():
    """API для удаления файла или директории"""
    path = request.json.get('path')
    is_dir = request.json.get('is_dir', False)
    
    if not path:
        return jsonify({'error': 'Путь не указан'})
    
    result = delete_file_or_directory(path, is_dir)
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

