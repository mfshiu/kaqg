# Required when executed as the main program.
import os, sys
from urllib import response
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel, Parcel, TextParcel
from services.file_service import FileService
from services.kg_service import Topic
from services.llm_service import LlmService
from retrieval import part_str
# import retrieval.extract_tool as et
from retrieval.extract_tool import FactConceptExtractor, SectionPairer
from retrieval.pdf_tool import PdfImport



class PdfRetriever(Agent):
    TOPIC_FILE_UPLOAD = "FileUpload/Pdf/Retrieval"
    TOPIC_RETRIEVED = "Retrieved/Pdf/Retrieval"


    def __init__(self, config:dict):
        logger.info(f"config: {config}")
        super().__init__(name='pdf.retrieval.wp', agent_config=config)


    def on_connected(self):
        logger.debug(f"on_connected")
        self.subscribe(PdfRetriever.TOPIC_FILE_UPLOAD, topic_handler=self._handle_retrieval)


    def _handle_retrieval(self, topic, pcl:BinaryParcel):
        # Upload the file
        kg_name = pcl.content.get('kg_name', 0)
        # logger.info(f"topic: {topic}, pcl: {pcl}")
        
        pcl_file:Parcel = self.publish_sync(FileService.TOPIC_FILE_UPLOAD, pcl, timeout=40)
        file_info = pcl_file.content
        logger.info(f"file_info: {file_info}")
        # file_info: {
            # 'file_id': file_id,
            # 'filename': filename,
            # 'mime_type': mime_type,
            # 'encoding': encoding,
            # 'file_path': file_path,
            # 'toc': {..},  # json
            # 'meta': {..}, # dict
        # }
        
        topic_triplets_add = f'{kg_name}/{Topic.TRIPLETS_ADD.value}'
        logger.verbose(f"topic_triplets_add: {topic_triplets_add}")

        pages = self.read_pages(file_info['file_path'])

        meta = file_info.get('meta', {})
        meta['filename'] = file_info['filename']
        meta['mime_type'] = file_info['mime_type']
        meta['encoding'] = file_info['encoding']
        meta['file_path'] = file_info['file_path']
        meta['title'] = meta['title'] if 'title' in meta else file_info['filename']
            
        toc = [(meta['title'], 
                0, 
                len(pages), 
                file_info['toc'] if 'toc' in file_info else [])]
        logger.debug(f"toc: {toc}")

        def process_page(page_number, page_content, file_info, kg_name, topic_triplets_add):
            """Process a single page, extracting and publishing triplets."""
            logger.info(f"Page {page_number}: {part_str(page_content, 150)}")
            sections = self.locate_sections(page_number, toc)
            logger.debug(f"sections: {sections}")
            triplets = self.extract_triplets(page_content, sections, meta)
            logger.verbose(f"triplets: {triplets[:5]}..")
            self.publish(topic_triplets_add, {
                'file_id': file_info['file_id'],
                'page_number': page_number,
                'kg_name': kg_name,
                'triplets': triplets,
            })

        for page_number, page_content in enumerate(pages):
            max_attempts = 3
            attempt = 0
            # Retry processing the page if an error occurs in max_attempts times.
            while attempt < max_attempts:
                try:
                    process_page(page_number, page_content, file_info, kg_name, topic_triplets_add)
                    break  # Exit loop if successful
                except Exception as e:
                    attempt += 1
                    logger.warning(f"Error processing page {page_number} (Attempt {attempt}/{max_attempts}):\n{e}")
                    if attempt == max_attempts:
                        logger.error(f"Skipping page {page_number} after {max_attempts} failed attempts.")
        

    chapter = tuple[str, int, int, list['chapter']]
    def locate_sections(self, page_number: int, toc: list[chapter], parent_hierarchy: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
        """
        遞迴查找多層章節結構，根據頁碼返回所有匹配的層級，並以 list of tuples 格式返回。
        
        :param page_number: 查詢的頁碼
        :param toc: 目錄結構 (遞迴形式)
        :param parent_hierarchy: 當前章節的父層級，用於組合完整層次
        :return: 包含所有匹配層級的 list of tuples

        Example:
        toc = [
            ('chapter1', 1, 9, [
                ('ch1-1', 1, 4, [
                    ('ch1-1-1', 1, 2, []),
                    ('ch1-1-2', 2, 4, [])
                ]),
                ('ch1-2', 4, 9, [])
            ]),
            ('chapter2', 10, 15, [
                ('ch2-1', 10, 12, []),
                ('ch2-2', 13, 15, [])
            ])
        ]
        
        Result of toc:
        Page 2 belongs to: [('chapter1',), ('chapter1', 'ch1-1'), ('chapter1', 'ch1-1', 'ch1-1-1'), ('chapter1', 'ch1-1', 'ch1-1-2')]
        Page 5 belongs to: [('chapter1',), ('chapter1', 'ch1-2')]
        Page 12 belongs to: [('chapter2',), ('chapter2', 'ch2-1')]
        Page 20 belongs to: []
        """
        def find_sections(page_number: int, toc: list[PdfRetriever.chapter], parent_hierarchy: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
            matches = []
            for ch in toc:
                name, start_page, end_page, subchapters = ch
                current_hierarchy = parent_hierarchy + (name,)
                
                if start_page <= page_number <= end_page:
                    matches.append(current_hierarchy)   # 當前章節匹配，加入結果
                    # 檢查子章節是否也匹配
                    if subchapters:
                        matches.extend(find_sections(page_number, subchapters, current_hierarchy))
            
            return matches
        
        sections = find_sections(page_number, toc, parent_hierarchy)
        if not sections:
            sections = [('Root',)]
        return sections


    def read_pages(self, file_path) -> list[str]:
        """
        Reads a PDF file from the given file into a list.
        
        Args:
            file_path (str): The absolute file path.
        Returns:
            list: A list of texts, including page content, table explanations, and image descriptions. The items in the list correspond to the page order.
        """
        
        pdf_import = PdfImport(file_path)
        return pdf_import.extract_pages()
        # Example of return.
        # return [
        #     '104 年全國各縣市焚化底渣產量約占焚化量之 15%。',
        #     '環境部已提供經費補助，鼓勵縣市政府進行分選後供為營建替代級配材料再利用。',
        #     '垃圾焚化廠焚化底渣再利用管理方式：此公告內容係針對底渣之再利用機構、產品分類、用途及使用地點進行管理要求。',
        # ]


    def extract_triplets(self, page_content, sections, meta) -> list[tuple[dict, dict, dict]]:
        extractor = FactConceptExtractor(PdfRetriever.LlmChat(self))
        
        # extract facts and concepts in LLM
        logger.info("Start to extract facts and concepts in LLM..")
        factes, concepts, entity_hierarchy = extractor.get_concept_n_fact(page_content)
        logger.debug(f"\nfactes: {factes[:5]}..\nconcepts: {concepts[:5]}..\nentity_hierarchy: {entity_hierarchy}")
        
        # extract fact-relationship-fact in LLM
        logger.info("Start to extract fact-relationship-fact in LLM..")
        facts_pairs = extractor.get_facts_pairs(factes, page_content)
        logger.debug(f"facts_pairs: {facts_pairs[:5]}..")
        
        # get aliases and save as dict in LLM
        aliases_keys = factes + concepts
        logger.info("Start to get aliases in LLM..")
        aliases_table = extractor.get_aliases(aliases_keys)
        logger.debug(f"aliases_table: {aliases_table}")

        # start to generate triplets
        logger.debug("Start to generate triplets..")
        pairer = SectionPairer()
        pairer.pair_concepts_with_facts(sections, entity_hierarchy, aliases_table)
        pairer.pair_sections_with_concepts(sections, concepts, aliases_table)
        pairer.pair_lower_to_higher_sections(sections, meta)
        pairer.pair_facts_and_facts(facts_pairs)

        triplets = pairer.get_results()
        # logger.verbose(f"triplets: {triplets}")
        return triplets



    class LlmChat:
        def __init__(self, agent:Agent):
            self.agent = agent


        def __call__(self, message:str):
            messages = [
                {"role": "user", "content": message},
                # {"role": "user", "content": f"{message}\nPlease provide your response in JSON format."}
            ]            
            params = {
                'messages': messages,
            }            
            pcl = TextParcel(params)
            logger.verbose(f"pcl: {pcl}")

            chat_response = self.agent.publish_sync(LlmService.TOPIC_LLM_PROMPT, pcl, timeout=20)
            response = chat_response.content['response']
            logger.verbose(f"response: {response}")
            
            return response


        # def __call__(self, message:str):
        #     pcl = TextParcel({'prompt': message})
        #     logger.verbose(f"pcl: {pcl}")
            
        #     chat_response = self.agent.publish_sync(LlmService.TOPIC_LLM_PROMPT, pcl, timeout=20)
        #     # logger.debug(f"chat_response: {chat_response}")
        #     return chat_response.content['response']



if __name__ == '__main__':
    agent = PdfRetriever(app_helper.get_agent_config())
    agent.start_process()
    app_helper.wait_agent(agent)
