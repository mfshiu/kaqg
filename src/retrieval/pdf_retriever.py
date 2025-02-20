# Required when executed as the main program.
import os, sys
from turtle import title
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import BinaryParcel, Parcel, TextParcel
from services.file_service import FileService
from services.kg_service import KnowledgeGraphService, Action
from services.llm_service import LlmService
from retrieval import ensure_size
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
        self._subscribe(PdfRetriever.TOPIC_FILE_UPLOAD, topic_handler=self._handle_retrieval)


    def _handle_retrieval(self, topic, pcl:BinaryParcel):
        # Upload the file
        kg_name = pcl.content.get('kg_name', 0)
        # logger.info(f"topic: {topic}, pcl: {pcl}")
        
        pcl_file:Parcel = self._publish_sync(FileService.TOPIC_FILE_UPLOAD, pcl, timeout=40)
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
        
        # kg_info = self._publish_sync(KnowledgeGraphService.TOPIC_CREATE)
        # kg_info: {
        #     'kg_name': kg_name,
        #     'topic_triplets_add': topic_triplets_add,
        # }
        topic_triplets_add = KnowledgeGraphService.get_topic(Action.TRIPLETS_ADD, kg_name)
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
            logger.info(f"Page {page_number}: {ensure_size(page_content, 150)}")
            sections = self.locate_sections(page_number, toc)
            logger.debug(f"sections: {sections}")
            triplets = self.extract_triplets(page_content, sections, meta)
            logger.verbose(f"triplets: {triplets[:5]}..")
            self._publish(topic_triplets_add, {
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
        """
        Convert the page content into triplets. The triplets should contain below types of relationships:
        1. The relationship from the sub-structure node to the structure node. (part_of)
        2. The relationship from concept node to the structure node. (include_in)
        3. The relationship from fact node to the concept node. (is_a)
        4. The relationship from start fact node to end node.
        Note:
            1. Each concept node must be at least part of a structure node.
            2. Each fact node must be at least a concept node.
            3. There are no nodes without any relationships.

        Args:
            page_content (str): The text content of a single page.
            sections (list of tuples): [(chapter, section, sub-section, ..), ..]
                ex: [('chapter1',), ('chapter1', 'ch1-1'), ('chapter1', 'ch1-1', 'ch1-1-1')]
            
        Returns:
            list: A list of tuples, each tuple containing three dictionaries,
            representing the starting node, directed relationship, and target node (Subject, Predicate, Object).
            
            Example of a node dict:
            node = {
                'type': 'fact',   # concept, structure, fact
                'name': '申請書',
                'aliases': ['application form','formulario de solicitud'],
                }

            Example of a relation dict:
            relation = {
                'name': 'contain',
                }
        """
        
        # 範例內容：
        """
        104 年全國各縣市焚化底渣產量約占焚化量之 15%，因其性質較無害，
        故為減少掩埋場負荷及推動資源回收再利用，環境部已提供經費補助，
        鼓勵縣市政府進行分選後供為營建替代級配材料再利用，目前基隆市、
        臺北市、新北市、桃園市、新竹市、苗栗縣、臺中市、彰化縣、嘉義市
        、嘉義縣、臺南市、高雄市、屏東縣等，已將所轄焚化廠底渣委外再利用
        ，經統計 104 年度一般廢棄物底渣再利用量占該年度底渣總量之89.3%
        ，其餘非採再利用部分則以掩埋方式進行最終處置。 
        """
        # Example of return.   
        """
        triplets = [
            ({'type': 'structure', 'name': '(三) 垃圾焚化灰渣再利用'}, 
            {'name': 'part_of'}, 
            {'type': 'structure', 'name': '二、一般廢棄物再利用體系'}),

            ({'type': 'concept', 'name': '焚化底渣', 'aliases': ['incineration bottom ash']}, 
            {'name': 'include_in'}, 
            {'type': 'structure', 'name': '(三) 垃圾焚化灰渣再利用'}),

            ({'type': 'fact', 'name': '104 年全國各縣市焚化底渣產量約占焚化量之 15%', 'aliases': ['15% incineration bottom ash production']}, 
            {'name': 'is_a'}, 
            {'type': 'concept', 'name': '焚化底渣', 'aliases': ['incineration bottom ash']}),

            ({'type': 'fact', 'name': '焚化量之 15%', 'aliases': ['15% of the incineration amount']}, 
            {'name': '包含'}, 
            {'type': 'fact', 'name': '104 年全國各縣市焚化底渣產量', 'aliases': ['Incineration bottom ash in 104 year across all cities']}),

            ({'type': 'fact', 'name': '桃園市', 'aliases': ['Taoyuan']}, 
            {'name': '委外再利用'}, 
            {'type': 'fact', 'name': '焚化廠底渣', 'aliases': ['incineration plant bottom ash']}),
        ]
        """

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
        pairer = SectionPairer()
        pairer.pair_concepts_with_facts(sections, entity_hierarchy, aliases_table)
        pairer.pair_sections_with_concepts(sections, concepts, aliases_table)
        pairer.pair_lower_to_higher_sections(sections, meta)
        pairer.pair_facts_and_facts(facts_pairs)

        triplets = pairer.get_results()
        return triplets



    class LlmChat:
        def __init__(self, agent:Agent):
            self.agent = agent


        def __call__(self, message:str):
            pcl = TextParcel({'prompt': message})
            logger.verbose(f"pcl: {pcl}")
            
            chat_response = self.agent._publish_sync(LlmService.TOPIC_LLM_PROMPT, pcl, timeout=20)
            # logger.debug(f"chat_response: {chat_response}")
            return chat_response.content['response']



if __name__ == '__main__':
    agent = PdfRetriever(app_helper.get_agent_config())
    agent.start_process()
    app_helper.wait_agent(agent)
