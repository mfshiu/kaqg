"""
文件名稱：docker_utility.py

功能說明：
本程式提供命令列介面來建立 Neo4j 的 Docker 容器。透過指定容器名稱、主機名稱與資料儲存路徑，
程式會透過 DockerManager 類別建立一個配置好的 Neo4j 容器，並回傳 HTTP 與 Bolt 的連線網址。

主要功能：
1. 使用命令列指令 `create` 建立 Docker 容器。
2. 指定容器名稱、主機名稱與資料儲存路徑。
3. 自動回傳容器啟動後的 HTTP 與 Bolt 連線網址。

使用方式：
python docker_utility.py create <container_name> [-hostname <主機名稱>] [-datapath <資料儲存路徑>]

參數說明：
- container_name：要建立的 Docker 容器名稱（必填）。
- -hostname：Docker 主機名稱，預設為 localhost。
- -datapath：資料存放路徑，預設為目前資料夾。

範例：
python apps\docker_utility.py create my_neo4j -hostname localhost -datapath _neo4j_volumes
python docker_utility.py create my_neo4j -hostname 127.0.0.1 -datapath /data/neo4j

需搭配模組：
- knowsys.docker_management.DockerManager：實作實際的容器建立與設定邏輯。
"""

import argparse
import os, sys

from knowsys.docker_management import DockerManager


def create_container(container_name, hostname, datapath):
    print(f"Creating Docker container named '{container_name}' on host '{hostname}' with data storage at '{datapath}'")
    
    docker_manager = DockerManager(hostname=hostname, base_volume_dir=datapath)
    http_url, bolt_url = docker_manager.create_container(container_name)
    print(f"Neo4j is up and running at \n{http_url} (HTTP) \nand \n{bolt_url} (Bolt)")


def main():
    parser = argparse.ArgumentParser(description="Docker Utility Tool")
    # Sub-command setup
    subparsers = parser.add_subparsers(dest='command')

    # Create container sub-command
    create_parser = subparsers.add_parser('create', help='Create a Docker container with specified settings')
    create_parser.add_argument('container_name', type=str, help='Name of the Docker container to create')
    create_parser.add_argument('-hostname', type=str, default='localhost', help='Hostname for the Docker container (default: localhost)')
    create_parser.add_argument('-datapath', type=str, default=os.getcwd(), help='Data storage path for the container (default: current folder)')

    args = parser.parse_args()

    if args.command == 'create':
        create_container(args.container_name, args.hostname, args.datapath)
    else:
        print("Unknown command. Use -h for help.")
        sys.exit(1)


if __name__ == '__main__':
    main()