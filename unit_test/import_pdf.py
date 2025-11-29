# import_pdf.py
import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import app_helper
app_helper.initialize()

import logging
logger: logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

import time
import unittest

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel, Parcel, TextParcel
from retrieval.pdf_retriever import PdfRetriever
from services.kg_service import Topic as KGTopic
from knowsys.docker_management import DockerManager


class TestAgent(unittest.TestCase):

    # test_files = ['Pdf01-台文.pdf']
    # test_files = [
    #     '2.專業技術人員職掌與工作倫理(甲乙丙級).pdf',
    #     '2.專業技術人員職掌與工作倫理(甲乙丙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '3.廢棄物回收與再利用概論(乙丙級).pdf',
    #     '3.廢棄物回收與再利用概論(乙丙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '4-1.廢棄物清理法(甲乙丙級).pdf',
    #     '4-2.資源回收再利用法(甲乙丙級).pdf',
    #     '4-3.公民營廢棄物清除處理機構許可管理辦法(甲乙丙級).pdf',
    #     '4-4.廢棄物清理專業技術人員管理辦法(甲乙丙級).pdf',
    #     '4-5.事業自行清除處理事業廢棄物許可管理辦法(甲乙丙級).pdf',
    #     '4-6.事業廢棄物輸出入管理辦法(甲乙丙級).pdf',
    #     ]
    # test_files = [
    #     '5.廢棄物清理許可及申報實務(甲乙丙級).pdf',
    #     '5.廢棄物清理許可及申報實務(甲乙丙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '6.廢棄物產源特性及減廢(乙級).pdf',
    #     '6.廢棄物產源特性及減廢(乙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '7.廢棄物採樣檢測及特性分析(乙級).pdf',
    #     '7.廢棄物採樣檢測及特性分析(乙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '8.廢棄物貯存清除技術(乙丙級).pdf',
    #     '8.廢棄物貯存清除技術(乙丙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '9.廢棄物理化生物處理技術(乙級).pdf',
    #     '9.廢棄物理化生物處理技術(乙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '10.廢棄物熱處理技術(乙級).pdf',
    #     '10.廢棄物熱處理技術(乙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '11.廢棄物最終處置技術(乙級).pdf',
    #     '11.廢棄物最終處置技術(乙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '12.廢棄物資源化與再利用技術(乙級).pdf',
    #     '12.廢棄物資源化與再利用技術(乙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '13.廢棄物貯存清除設備操作維護管理(乙丙級).pdf',
    #     '13.廢棄物貯存清除設備操作維護管理(乙丙級)-pptx.pdf',
    #     ]
    # test_files = [
    #     '14.廢棄物處理設施操作維護及營運管理(乙級).pdf',
    #     '14.廢棄物處理設施操作維護及營運管理(乙級)-pptx.pdf',
    #     ]
    test_files = [
        '15.作業安全衛生及緊急應變(乙丙級).pdf',
        '15.作業安全衛生及緊急應變(乙級)-pptx.pdf',
        ]
    kg_name = 'S15'
    file_ids = []
    filenames = []
    processed_count = 0

    total_files = len(test_files)
    start_time: float = time.time()

    class ValidationAgent(Agent):
        def __init__(self):
            super().__init__(name='main', agent_config=app_helper.get_agent_config())
            self.kg_name = TestAgent.kg_name
            kg_config = app_helper.config['service']['kg']
            self.docker_management = DockerManager(kg_config['hostname'], kg_config['datapath'])

        def on_activate(self):
            logger.info("ValidationAgent activated.")
            self.subscribe(PdfRetriever.TOPIC_RETRIEVED)

            # Create KG
            self.publish_sync(KGTopic.CREATE, TextParcel({'kg_name': self.kg_name}), timeout=600)

            # Publish all PDF files
            for filename in TestAgent.test_files:
                with open(os.path.join(os.getcwd(), 'unit_test', 'data', filename), 'rb') as file:
                    content = file.read()
                pcl = BinaryParcel({
                    'content': content,
                    'filename': filename,
                    'kg_name': self.kg_name
                })
                self.publish(PdfRetriever.TOPIC_FILE_UPLOAD, pcl)

        def on_message(self, topic: str, pcl: Parcel):
            logger.info(f"Received: {topic}, filename={pcl['filename']}")
            TestAgent.file_ids.append(pcl['file_id'])
            TestAgent.filenames.append(pcl['filename'])

            TestAgent.processed_count += 1

        def on_terminated(self):
            pass


    def setUp(self):
        TestAgent.processed_count = 0
        TestAgent.file_ids.clear()
        TestAgent.filenames.clear()

        TestAgent.start_time = time.time()

        self.validation_agent = TestAgent.ValidationAgent()
        self.validation_agent.start_thread()


    def test_1(self):
        timeout_sec = 3600*24  # 最多等 24 Hour
        last_progress = -1
        last_dot_time = time.time()

        print(f"Total files: {TestAgent.total_files}")
        print("Processing PDF files...\n")

        while True:
            processed = TestAgent.processed_count

            # 顯示進度
            if processed != last_progress:
                print(f"Progress: {processed+1}/{TestAgent.total_files} processed...")
                last_progress = processed
                
            # 每 5 秒印一個點，表示程式還活著
            now = time.time()
            if now - last_dot_time >= 5:
                print('.', end='', flush=True)
                last_dot_time = now

            # 全部完成
            if processed >= TestAgent.total_files:
                break

            # timeout 防護
            if time.time() - self.start_time > timeout_sec:
                self.fail(f"Timeout after {timeout_sec} seconds! Processed: {processed}/{TestAgent.total_files}")

            time.sleep(1)

        print("All files processed.")

        # 最終驗證
        logger.debug(f'file_ids: {TestAgent.file_ids}')
        self.assertEqual(len(TestAgent.file_ids), TestAgent.total_files)

        for testfile in TestAgent.test_files:
            self.assertIn(testfile, TestAgent.filenames)


    def tearDown(self):
        self.validation_agent.terminate()


if __name__ == '__main__':
    unittest.main()
