#!/usr/bin/env python3
import paramiko
import sys

host = "192.168.31.2"
port = 22
username = "root"
password = "test"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(host, port, username, password)
    # Get Home Assistant logs
    stdin, stdout, stderr = client.exec_command("docker logs homeassistant --tail 50 2>&1 | grep -E '(ya2dlna|Ya2DLNA|ERROR|WARN)'")
    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()
    print("=== Home Assistant logs (last 50 lines with ya2dlna/ERROR/WARN) ===")
    print(output)
    if error:
        print("Stderr:", error)
    # Get addon logs
    stdin, stdout, stderr = client.exec_command("docker ps --filter name=ya2dlna --format '{{.ID}}'")
    container_id = stdout.read().decode().strip()
    if container_id:
        stdin, stdout, stderr = client.exec_command(f"docker logs {container_id} --tail 30")
        addon_logs = stdout.read().decode().strip()
        print("\n=== Addon ya2dlna logs (last 30 lines) ===")
        print(addon_logs)
    else:
        print("\nAddon ya2dlna container not found")
    client.close()
except Exception as e:
    print(f"SSH connection failed: {e}")
    sys.exit(1)