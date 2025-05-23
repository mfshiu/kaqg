"""
文件名稱：document_ingest.py

功能說明：
本程式為文件導入工具，負責將 PDF 文件（及其章節目錄 TOC）上傳至知識圖譜系統。系統基於 Agent 架構設計，
透過訂閱與發布機制，協助文件解析與建構語意知識。可從命令列指定任務參數進行導入任務。

主要功能：
1. 支援命令列參數以指定文件路徑、主題名稱（subject_name）、章節目錄（TOC）檔案。
2. 使用 AgentFlow 框架的 Agent 機制執行導入任務。
3. 將文件內容包裝為 BinaryParcel，並透過發佈機制送出給 PdfRetriever 處理。
4. 可透過 Ctrl+C 中斷任務執行。

使用方法：
python document_ingest.py ingest -subject_name <主題名稱> -file_path <文件路徑> [-toc <TOC檔案路徑>]

參數說明：
- subject_name：導入知識的主題名稱，會作為知識圖譜分類。
- file_path：PDF 文件檔案路徑。
- toc：選填，用 pprint 格式編寫的章節目錄 TOC 檔案路徑。
"""

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])

import argparse
import ast
import signal
import os
import time

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel, Parcel
from retrieval.pdf_retriever import PdfRetriever


is_running = True



class ExecutionAgent(Agent):
    def __init__(self, config, toc):
        super().__init__(name='execution', agent_config=config)
        self.mission = config['mission']
        self.subject_name = config['subject_name']
        self.file_path = config['file_path']
        self.toc = toc  
        
        
    def _ingest_document(self):
        self.subscribe(PdfRetriever.TOPIC_RETRIEVED)
        
        filename = os.path.basename(self.file_path)
        meta = {
            'title': os.path.splitext(filename)[0],
        }
        
        with open(self.file_path, 'rb') as file:
            file_content = file.read()
        pcl_content = {
            'filename': filename,
            'kg_name': self.subject_name,
            'meta': meta,
            'content': file_content,
        }
        if self.toc:
            pcl_content['toc'] = self.toc
        pcl = BinaryParcel(pcl_content)
        self.publish(PdfRetriever.TOPIC_FILE_UPLOAD, pcl)


    def on_activate(self):
        print(self.M("Broker is connected."))

        # time.sleep(.5)
        if self.mission == 'ingest_document':
            self._ingest_document()
        else:
            print(self.M(f"Invalid mission: {self.mission}"))
            self.terminate()


    def on_message(self, topic: str, pcl: Parcel):
        print(self.M(f"topic: {topic}\npcl:\n{pcl}"))
        self.terminate()


def load_toc(toc_file):
    """ 從 pprint 格式的文件讀取 toc """
    if not os.path.exists(toc_file):
        print(f"Error: The TOC file '{toc_file}' does not exist.")
        sys.exit(1)

    with open(toc_file, "r", encoding="utf-8") as file:
        try:
            return ast.literal_eval(file.read())
        except (SyntaxError, ValueError) as e:
            print(f"Error: Invalid TOC format in '{toc_file}': {e}")
            sys.exit(1)


def ingest_document(subject_name, file_path, toc_file=None):
    """
    :param subject_name: The subject or category of the knowledge graph.
    :param file_path: The path to the document to be imported.
    :param toc_file: The path to the TOC file in pprint format.
    """
    if not os.path.exists(file_path):
        print(f"Error: The file at '{file_path}' does not exist.")
        return
    file_size = os.path.getsize(file_path)

    toc = load_toc(toc_file) if toc_file else None
    print(f"TOC: {toc}")
    print(f"Importing '{file_path}' into the knowledge graph under the subject '{subject_name}'...")

    config = app_helper.get_agent_config()
    config['mission'] = 'ingest_document'
    config['subject_name'] = subject_name
    config['file_path'] = file_path
    agent = ExecutionAgent(config, toc)
    agent.start_thread()

    timeout_sec = file_size // 1024 * 2  # 2 seconds per KB
    while is_running and timeout_sec and agent.is_active():
        time.sleep(1)
        timeout_sec -= 1
        print(f"Countdown: {timeout_sec}", end="\r", flush=True)
    print()
    if agent.is_active():
        agent.terminate()
        print(f"Timeout: The {config['mission']} has been terminated.")

    print("Ingest finished.")


def main():
    parser = argparse.ArgumentParser(description="Document KG Tool")
    subparsers = parser.add_subparsers(dest='command')

    ingest_parser = subparsers.add_parser('ingest', help='Import documents into a Knowledge Graph')
    ingest_parser.add_argument('-subject_name', type=str, required=True, help='Subject or category for the KG')
    ingest_parser.add_argument('-file_path', type=str, required=True, help='Path to the document file to be imported')
    ingest_parser.add_argument('-toc', type=str, help='Path to the Table of Contents file in pprint format')

    args = parser.parse_args()

    if args.command == 'ingest':
        ingest_document(args.subject_name, args.file_path, args.toc)
    else:
        print("Unknown command. Use -h for help.")
        sys.exit(1)


if __name__ == '__main__':
    def signal_handler(signal, frame):
        print("Ctrl-C for Exiting...")
        global is_running
        is_running = False
    signal.signal(signal.SIGINT, signal_handler)

    main()
