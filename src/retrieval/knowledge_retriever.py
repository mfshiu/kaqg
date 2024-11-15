import signal
import time

from agentflow.core.agent import Agent
from agentflow.core.parcel import Parcel
import app_helper


from logging import Logger
logger:Logger = __import__('wastepro').get_logger()



class KnowledgeRetriever(Agent):
    def __init__(self, config:dict):
        logger.info(f"config: {config}")
        super().__init__(name='retrieval.wp', agent_config=config)


    def on_connected(self):
        logger.debug(f"on_connected")
        self._subscribe('FileUpload/Retrieval', topic_handler=self._handle_fileupload)
        
        
    def _handle_fileupload(self, topic, data):
        this = self
        pcl = Parcel.from_bytes(data)
        # mdata = pcl.managed_data
        # logger.debug(f"topic: {topic}, filename: {mdata.get('filename')}")

        def handle_file_saved(_, data_uploaded):
            mdata_uploaded = Parcel.from_text(data_uploaded).managed_data
            logger.debug(f"topic: {topic}, filename: {mdata_uploaded.get('filename')}")
            this._publish('001/Test', data_uploaded)

        home_topic=f'{self.tag}-{int(time.time()*1000)}/{topic}'
        self._subscribe(home_topic, topic_handler=handle_file_saved)
        
        # pcl = Parcel(content=mdata['content'], home_topic=home_topic)
        pcl.set('home_topic', home_topic)
        self._publish('FileUpload/FileService/Services', pcl.payload())
        
        
        # file_info = pickle.loads(payload)
        # if not 'file_id' in file_info:
        #     file_info['file_id'] = ""
        # filename = file_info['filename']
        # content = file_info['content']
        


if __name__ == '__main__':
    main_agent = KnowledgeRetriever(app_helper.get_agent_config())
    logger.debug(f'***** {main_agent.__class__.__name__} *****')
    

    def signal_handler(signal, frame):
        main_agent.terminate()
    signal.signal(signal.SIGINT, signal_handler)


    main_agent.start_process()

    time.sleep(1)
    while main_agent.is_active():
        print('.', end='')
        time.sleep(1)
