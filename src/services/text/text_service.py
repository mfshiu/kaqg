from agentflow.core.agent import Agent
from agentflow.core.parcel import Parcel
from services.text.pdf import PdfReader

from logging import Logger
logger:Logger = __import__('src').get_logger()


class TextService(Agent):
    NAME = 'text_service.services.wastepro'
    TOPIC_TEXT_EXTRACT = "TextExtract/TextService/Services"
    
    
    def __init__(self, cfg):
        super().__init__(TextService.NAME, cfg)


    def on_connected(self):
        self._subscribe(TextService.TOPIC_TEXT_EXTRACT, "str", self.handle_text_extract)


    def _on_start(self):
        PdfReader(self.config).start_thread()


    def handle_text_extract(self, topic:str, pcl:Parcel):
        file_info = pcl.content
        logger.verbose(f"topic: {topic}, data: {file_info}")

        self._notify_children("TextExtract", file_info)
        
        
    def on_children_message(self, _, child_info):
        if "TextExtract" == child_info['subject']:
            return child_info['data']
