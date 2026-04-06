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
    # Find Home Assistant container
    stdin, stdout, stderr = client.exec_command("docker ps --filter name=home-assistant --format '{{.ID}}'")
    ha_id = stdout.read().decode().strip()
    if ha_id:
        print(f"Home Assistant container ID: {ha_id}")
        stdin, stdout, stderr = client.exec_command(f"docker logs {ha_id} --tail 100 2>&1 | grep -E '(ya2dlna|Ya2DLNA|ERROR|WARN|Config flow)' | head -30")
        output = stdout.read().decode().strip()
        print("=== Home Assistant logs (filtered) ===")
        print(output if output else "(no matching logs)")
    else:
        print("Home Assistant container not found")
    # Find addon containers (maybe named addon_* or ya2dlna*)
    stdin, stdout, stderr = client.exec_command("docker ps --format '{{.Names}}' | grep -i ya2dlna")
    addon_names = stdout.read().decode().strip().split()
    if addon_names:
        for name in addon_names:
            print(f"\nAddon container: {name}")
            stdin, stdout, stderr = client.exec_command(f"docker logs {name} --tail 30")
            logs = stdout.read().decode().strip()
            print(logs)
    else:
        print("\nNo addon containers with 'ya2dlna' in name")
        # List all containers
        stdin, stdout, stderr = client.exec_command("docker ps --format '{{.Names}}'")
        all_containers = stdout.read().decode().strip()
        print("All containers:", all_containers)
    client.close()
except Exception as e:
    print(f"SSH connection failed: {e}")
    sys.exit(1)