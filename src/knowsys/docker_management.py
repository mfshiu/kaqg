import docker
import os
import socket
import shutil
import time
import requests


class DockerManager:
    """
    Docker 管理員。
    
    :param image: 使用的映像名稱
    :param ports: 映射的端口，格式為 {'container_port/protocol': host_port}
    :param volumes: 映射的資料儲存位置，格式為 {host_path: {'bind': container_path, 'mode': 'rw'}}
    :param detach: 是否在後台運行容器 (預設為 True)
    :return: Docker 回傳DokerManager instance
    """
    def __init__(self, hostname='localhost', base_volume_dir=None):
        # self.base_volume_dir = base_volume_dir if base_volume_dir else os.path.join(os.getcwd(), "src/knowsys/data")
        self.base_volume_dir = base_volume_dir if base_volume_dir else os.path.join(os.getcwd(), "src/knowsys/volumes")
        os.makedirs(self.base_volume_dir, exist_ok=True)
        print(f"base_volume_dir: {self.base_volume_dir}")
        self.hostname = hostname
        self.client = docker.from_env()
        self.image = "neo4j:community"
        # self.image = "neo4j:5.26.3-community-ubi9"
        self.detach = True


    # 檢查端口是否已被占用
    def is_port_in_use(self,port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((self.hostname, port)) == 0


    # 獲取空閒端口
    def get_free_port(self,start_port):
        port = start_port
        while self.is_port_in_use(port):
            port += 1
        return port


    def wait_for_KG(self, http_port, timeout=500):
        """檢查 Neo4j 是否在 7474 端口上啟動，最多等待 timeout 秒"""

        url = f"http://{self.hostname}:{http_port}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 嘗試連線到 Neo4j HTTP 端口
                response = requests.get(url)
                if response.status_code == 200:
                    #print(f"Neo4j is up and running at {url}")
                    print("")
                    return True
            except requests.ConnectionError:
                # 如果連線失敗則等候一段時間後重試
                pass
            time.sleep(1)
            print(f"\rNeo4j 仍在啟動中，已經過{int(time.time() - start_time):d}秒...",end="")

        print("\nTimed out waiting for Neo4j to start.")
        return False
    
    
    def get_ports(self, kgName):
        """
        取得指定 KG 容器的 HTTP 和 BOLT 端口
        
        :param kgName: 容器名稱
        :return: tuple, 包含 HTTP 和 BOLT 端口 (http_port, bolt_port)
        """
        running_kgs = self.list_running_KGs()
        for container_name, http_port, bolt_port in running_kgs:
            if container_name == kgName:
                return http_port, bolt_port
        return None, None  # KG 未運行


    def get_urls(self, kgName):
        """
        取得指定 KG 容器的 HTTP 和 BOLT URL
        
        :param kgName: 容器名稱
        :return: tuple, 包含 HTTP 和 BOLT URL
        """
        http_port, bolt_port = self.get_ports(kgName)
        if http_port and bolt_port:
            return f"http://{self.hostname}:{http_port}", f"bolt://{self.hostname}:{bolt_port}"
        return None, None  # KG 未運行
    
    
    def create_container(self, kgName):
        """
        若 kgName 的容器已存在則不建立；若未啟動先啟動，
        最後回傳 (http_url, bolt_url)。若無法取得連接埠則回傳 (None, None)。
        """
        # 先嘗試取得既有容器
        try:
            container = self.client.containers.get(kgName)

            # 若未啟動則啟動
            if container.status != 'running':
                container.start()
                # 重新抓一次屬性以取得最新連接埠映射
                container.reload()

            # 讀取既有的連接埠映射
            ports = container.attrs['NetworkSettings']['Ports'] or {}
            http_port = ports.get('7474/tcp', [{}])[0].get('HostPort')
            bolt_port = ports.get('7687/tcp', [{}])[0].get('HostPort')

            # 若映射缺失，嘗試用既有工具找
            if not http_port or not bolt_port:
                http_port, bolt_port = self.get_ports(kgName)

            if http_port and bolt_port:
                # 確認服務已就緒
                self.wait_for_KG(int(http_port), timeout=180)
                return (f"http://{self.hostname}:{http_port}",
                        f"bolt://{self.hostname}:{bolt_port}")
            else:
                print(f"Existing container '{kgName}' has no port bindings.")
                return None, None

        except docker.errors.NotFound:
            # 不存在則建立新容器
            print(f"Creating new container for {kgName}...")

            http_port = self.get_free_port(7474)
            bolt_port = self.get_free_port(7687)

            # 準備資料夾
            kg_path = os.path.join(self.base_volume_dir, kgName)
            kg_path = os.path.abspath(os.path.normpath(kg_path)).replace('\\', '/')
            os.makedirs(kg_path, exist_ok=True)

            try:
                container = self.client.containers.run(
                    image=self.image,
                    name=kgName,
                    ports={
                        '7474/tcp': http_port,
                        '7687/tcp': bolt_port
                    },
                    environment={
                        'NEO4J_AUTH': 'none',
                        'NEO4JLABS_PLUGINS': '["apoc", "graph-data-science"]',
                        'dbms.security.procedures.unrestricted': 'apoc.*,gds.*',
                        'dbms.security.procedures.allowlist': 'apoc.*,gds.*',
                        'apoc.export.file.enabled': 'true'
                    },
                    volumes={kg_path: {'bind': '/data', 'mode': 'rw'}},
                    detach=self.detach
                )

                self.wait_for_KG(http_port, timeout=180)
                print(f"Container {container.name} created and running. "
                    f"HTTP at: http://{self.hostname}:{http_port}, "
                    f"BOLT at: bolt://{self.hostname}:{bolt_port}")
                return (f"http://{self.hostname}:{http_port}",
                        f"bolt://{self.hostname}:{bolt_port}")

            except docker.errors.APIError as e:
                print(f"Error creating container: {e}")
                return None, None


    def open_KG(self, kgName):
        """
        開啟或建立指定名稱的neo4j KG(Container).
        若 KG 已在運行，則直接返回現有的 HTTP 和 BOLT 端口，不重新啟動。
        
        :param kgName: 欲開啟/建立的KG名稱.
        :return: tuple:
            (http_url, bolt_url)
        """
        print(f"Checking if KG '{kgName}' is already running...")

        # 取得所有正在運行的 KG
        running_kgs = self.list_running_KGs()

        # 檢查 KG 是否已在運行
        for container_name, http_port, bolt_port in running_kgs:
            if container_name == kgName:
                print(f"KG '{kgName}' is already running. HTTP at: http://{self.hostname}:{http_port}, BOLT at: bolt://{self.hostname}:{bolt_port}")
                return f"http://{self.hostname}:{http_port}", f"bolt://{self.hostname}:{bolt_port}"

        raise ValueError(f"KG '{kgName}' is not running. Please create it first.")
        # 若 KG 尚未運行，則創建它
        # print(f"KG '{kgName}' is not running. Creating a new container...")
        # return self.create_container(kgName)

        
    def stop_KG(self, kgName):
        """
        停止並刪除運行中的KG容器。
        
        :param kgName: 容器或KG名稱
        """
        try:
            container = self.client.containers.get(kgName)

            mounts = container.attrs['Mounts']  # 獲取容器掛載的卷詳細資訊
            volume_names = []
            for mount in mounts:
                if mount['Type'] == 'volume':
                    volume_names.append(mount['Name'])
            container.stop()
            container.remove()
            for volumn in volume_names:
                self.client.volumes.get(volumn).remove()
            print(f"Container {kgName} stopped.")
            
        except docker.errors.NotFound:
            print(f"無運作中{kgName}的Container")
            
        except docker.errors.APIError as e:
            print(f"Error stopping container: {e}")

    
    def list_containers(self, all=False):
        """
        回傳一個list包含所有正在運行所有的KG container。
        
        :param all: 是否列出所有容器，包含停止的 (預設 False)
        :return: 容器列表
        """
        containers = self.client.containers.list(all=True)
        names = []
        details =[]
        for container in containers:
            details.append(f"{container.name} - {container.status} -{container.attrs['NetworkSettings']['Ports']}- {container}")
            names.append(container.name)
        return details,names
    
    
    def list_KGs(self):
        """
        回傳一個list包含所有已建立的KG。
        資料儲存於data/neo4j_kgs下

        :param all: 是否列出所有容器，包含停止的 (預設 False)
        :return: 容器列表
        """
        directories = []
        # kgs_dir = os.path.join(self.base_volume_dir, 'neo4j_KGs')
        # os.makedirs(kgs_dir, exist_ok=True)
        items = os.listdir(self.base_volume_dir)
        # 過濾出資料夾
        directories = [item for item in items if os.path.isdir(os.path.join(self.base_volume_dir, item))]
        return directories


    def list_running_KGs(self):
        """
        回傳所有正在運行且映射 7474/tcp 端口的 KG 容器名稱及其對應的端口資訊。

        :return: list of tuples, 每個元素包含 (容器名稱, HTTP端口, BOLT端口)
        """
        running_kgs = []
        containers = self.client.containers.list()  # 只列出運行中的容器

        for container in containers:
            ports = container.attrs['NetworkSettings']['Ports']
            
            # 確保 7474/tcp 存在於映射端口中
            if '7474/tcp' in ports and ports['7474/tcp']:
                http_port = ports['7474/tcp'][0].get('HostPort', 'N/A')
                bolt_port = ports.get('7687/tcp', [{}])[0].get('HostPort', 'N/A')
                running_kgs.append((container.name, http_port, bolt_port))

        return running_kgs
    
    
    def stop_all(self):
        """
        停止所有正在運行的KG container.
        """
        for kgName in self.list_containers()[1]:
            if kgName in self.list_KGs():
                self.stop_KG(kgName)
        print("All KG containers have been stopped.")


    def delete_KG(self,kgName):
        """
        刪除指定的KG檔案.***此指令會完全清除該KG資料***
        """
        try:
            self.stop_KG(kgName)
            volume_dir = os.path.join(self.base_volume_dir, kgName)
            # directory = os.path.normpath(os.path.join(self.base_volume_dir,path))
            shutil.rmtree(volume_dir)
        except:
            pass


    def delete_all_KGs(self):
        """
        刪除所有data/neo4j_kgs目錄下的KG檔案.***此指令會完全清除所有data/neo4j_kgs目錄下的KG資料***
        """
        self.stop_all()
        for kgName in self.list_KGs():
            self.delete_KG(kgName)
