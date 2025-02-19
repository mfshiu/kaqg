import os, sys

from openai import timeout
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])

import argparse
import signal
import os
import time

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel, Parcel
from retrieval.pdf_retriever import PdfRetriever


is_running = True
toc = [
    ('chapter1', 0, 9, [
        ('ch1-1', 0, 4, [
            ('ch1-1-1', 0, 1, []),
            ('ch1-1-2', 1, 4, [])
        ]),
        ('ch1-2', 5, 9, [])
    ]),
    ('chapter2', 10, 25, [
        ('ch2-1', 10, 12, []),
        ('ch2-2', 13, 25, [])
    ])
]



class ExecutionAgent(Agent):
    def __init__(self, config):
        super().__init__(name='execution', agent_config=config)
        self.mission = config['mission']
        self.subject_name = config['subject_name']
        self.file_path = config['file_path']
        
        
    def _ingest_document(self):
        self._subscribe(PdfRetriever.TOPIC_RETRIEVED)
        
        filename = os.path.basename(self.file_path)
        meta = {
            'title': os.path.splitext(filename)[0],
        }
        
        with open(self.file_path, 'rb') as file:
            content = file.read()
        pcl = BinaryParcel({
            'filename': filename,
            'kg_name': self.subject_name,
            'toc': toc,
            'meta': meta,
            'content': content,})
        self._publish(PdfRetriever.TOPIC_FILE_UPLOAD, pcl)


    def on_active(self):
        print(self.M("Broker is connected."))

        time.sleep(.5)
        if self.mission == 'ingest_document':
            self._ingest_document()
        else:
            print(self.M(f"Invalid mission: {self.mission}"))
            self.terminate()
            

    def on_message(self, topic:str, pcl:Parcel):
        print(self.M(f"topic: {topic}\npcl:\n{pcl}"))        
        self.terminate()



def ingest_document(subject_name, file_path):
    """
    :param subject_name: The subject or category of the knowledge graph.
    :param file_path: The path to the document to be imported.
    """
    if not os.path.exists(file_path):
        print(f"Error: The file at '{file_path}' does not exist.")
        return
    file_size = os.path.getsize(file_path)
    
    print(f"Importing '{file_path}' into the knowledge graph under the subject '{subject_name}'...")

    config = app_helper.get_agent_config()
    config['mission'] = 'ingest_document'
    config['subject_name'] = subject_name
    config['file_path'] = file_path
    agent = ExecutionAgent(config)
    agent.start_thread()

    timeout_sec = file_size // 1024
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
    ingest_parser.add_argument('-subject_name', type=str, help='Subject or category for the KG')
    ingest_parser.add_argument('-file_path', type=str, help='Path to the document file to be imported')
    
    args = parser.parse_args()

    if args.command == 'ingest':
        ingest_document(args.subject_name, args.file_path)
    else:
        print("Unknown command. Use -h for help.")
        sys.exit(1)


if __name__ == '__main__':
    def signal_handler(signal, frame):
        global is_running
        is_running = False
        print("Ctrl-C for Exiting...")
    signal.signal(signal.SIGINT, signal_handler)

    main()


# Command line example:
r"""
python apps\dockg.py ingest -subject_name Wastepro01 -file_path D:\Work\NCU\計畫\國環院廢棄物\wastepro\doc\單頁.pdf
"""