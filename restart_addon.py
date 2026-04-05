#!/usr/bin/env python3
"""
Скрипт для перезапуска аддона Ya2DLNA через SSH на Home Assistant.
Использует paramiko для подключения к хосту 192.168.31.2.
"""

import paramiko
import sys
import time

def restart_addon():
    host = "192.168.31.2"
    username = "root"
    password = "test"
    
    print(f"Подключаемся к {host}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(host, username=username, password=password, timeout=10)
        print("Подключение успешно.")
        
        # Останавливаем аддон (используем apps вместо addons)
        print("Останавливаем аддон Ya2DLNA Streaming...")
        stdin, stdout, stderr = client.exec_command("ha apps stop 14047b0c_ya2dlna")
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        if output:
            print(f"Output: {output}")
        if error:
            print(f"Error: {error}")
        
        # Ждём остановки
        time.sleep(5)
        
        # Пересобираем аддон
        print("Пересобираем аддон Ya2DLNA Streaming...")
        stdin, stdout, stderr = client.exec_command("ha apps rebuild 14047b0c_ya2dlna")
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        if output:
            print(f"Output: {output}")
        if error:
            print(f"Error: {error}")
        
        # Ждём завершения сборки
        time.sleep(10)
        
        # Запускаем аддон
        print("Запускаем аддон Ya2DLNA Streaming...")
        stdin, stdout, stderr = client.exec_command("ha apps start 14047b0c_ya2dlna")
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        if output:
            print(f"Output: {output}")
        if error:
            print(f"Error: {error}")
        
        # Проверяем статус
        print("Проверяем статус аддона...")
        stdin, stdout, stderr = client.exec_command("ha apps info 14047b0c_ya2dlna")
        output = stdout.read().decode().strip()
        if output:
            print(f"Статус аддона:\n{output}")
        
        print("✅ Аддон перезапущен.")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    restart_addon()