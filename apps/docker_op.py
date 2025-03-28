import argparse
import os, sys

from knowsys.docker_management import DockerManager


def create_container(container_name, hostname, datapath):
    print(f"Creating Docker container named '{container_name}' on host '{hostname}' with data storage at '{datapath}'")
    
    docker_manager = DockerManager(hostname=hostname, datapath=datapath)
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