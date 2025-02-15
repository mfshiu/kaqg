"""
This module provides tools for extracting concepts and facts from text and building knowledge graphs.
It includes functionality for text analysis, concept categorization, and relationship mapping.
"""

from openai import OpenAI
import re
import json
import os
from transformers import AutoTokenizer, AutoModelForTokenClassification
from transformers import pipeline

# Get API key from environment variable
api_key = os.getenv('OPENAI_API_KEY')
if api_key is None:
    raise ValueError("Please set the OPENAI_API_KEY environment variable")

class GptChat:
    """
    A class to handle interactions with OpenAI's GPT models.
    Provides streaming chat completion functionality.
    """
    def __init__(self, api_key=api_key, model="gpt-4o-mini"):
        """
        Initialize the GPT chat client.
        
        Args:
            api_key (str): OpenAI API key
            model (str): Name of the GPT model to use
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def __call__(self, message="Say this is a test"):
        """
        Send a message to the GPT model and stream the response.
        
        Args:
            message (str): Input message to send to the model
            
        Returns:
            list: Accumulated response chunks from the model
        """
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": message}],
            stream=True,
        )
        reply = []
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                reply.append(chunk.choices[0].delta.content)
                print(chunk.choices[0].delta.content, end="")
        return reply
    
def get_concept_n_fact(chat, context):
    """
    Extract concepts and facts from given context and organize them into a hierarchy.
    
    Args:
        chat: GPT chat instance
        context (str): Input text to analyze
        
    Returns:
        tuple: (facts list, concepts list, entity hierarchy dictionary)
    """
    query_concept_and_fact =f'''
            Please structure the following context into triplets. The context will be divided into two levels: fact and concept. A fact refers to all entities that can be found in the context, while a concept refers to the higher-level categories of those facts.

            For example:
            "104 年全國各縣市焚化底渣產量約占焚化量之 15%，因其性質較無害，故為減少掩埋場負荷及推動資源回收再利用，環境部已提供經費補助，鼓勵縣市政府進行分選後供為營建替代級配材料再利用，目前基隆市、臺北市、新北市、桃園市、新竹市、苗栗縣、臺中市、彰化縣、嘉義市、嘉義縣、臺南市、高雄市、屏東縣等，已將所轄焚化廠底渣委外再利用，經統計 104 年度一般廢棄物底渣再利用量占該年度底渣總量之89.3%，其餘非採再利用部分則以掩埋方式進行最終處置。"

            This can be broken down into the following facts and concepts, and each fact need to be category as one concepts like result show in entity_hierarchy:
            facts = [
                "104 年",
                "15%",
                "89.3%",
                "環境部",
                "基隆市",
                "臺北市",
                "新北市",
                "桃園市",
                "新竹市",
                "苗栗縣",
                "臺中市",
                "彰化縣",
                "嘉義市",
                "嘉義縣",
                "臺南市",
                "高雄市",
                "屏東縣",
                "焚化底渣",
                "掩埋場",
                "資源回收再利用",
                "營建替代級配材料",
                "焚化廠",
                "一般廢棄物",
                "底渣",
                "分選",
                "再利用",
                "掩埋",
                "最終處置"]

            concepts = [
                "年份",
                "百分比",
                "政府機構",
                "城市",
                "縣",
                "廢棄物",
                "設施",
                "廢棄物管理",
                "建材",
                "廢棄物處理"]
                
            entity_hierarchy = {{
                                "年份": ["104 年"],
                                "百分比": ["15%", "89.3%"],
                                "政府機構": ["環境部"],
                                "城市": [
                                    "基隆市", "臺北市", "新北市", "桃園市", "新竹市",
                                    "臺中市", "嘉義市", "臺南市", "高雄市"
                                ],
                                "縣": ["苗栗縣", "彰化縣", "嘉義縣", "屏東縣"],
                                "廢棄物": ["焚化底渣", "一般廢棄物", "底渣"],
                                "設施": ["掩埋場", "焚化廠"],
                                "廢棄物管理": ["資源回收再利用"],
                                "建材": ["營建替代級配材料"],
                                "廢棄物處理": ["分選", "再利用", "掩埋", "最終處置"]
                                }}
            please following the rule as above and help me to extract the facts and concept from new context following the output format.
            # context:
            {context}
            Following the output format as below is very important do not return any context just output.
            # output format:
            facts = []
            concepts = []
            entity_hierarchy = {{concept1:[fact_a, fact_b]}}
            '''
    answer_concept_and_fact = chat(message=query_concept_and_fact)
    answer_concept_and_fact = ''.join(answer_concept_and_fact)
    answer_concept_and_fact = re.sub(r'\s+', ' ', answer_concept_and_fact)

    answer_concept_and_fact = answer_concept_and_fact.split('facts = ')[-1].split('concepts = ')
    factes = json.loads(answer_concept_and_fact[0])

    text = answer_concept_and_fact[1].split('entity_hierarchy = ')
    concepts = text[0].replace('[', '').replace(']', '').replace('"', '').replace(' ', '').strip().split(',')

    entity_hierarchy = text[1]
    entity_hierarchy = json.loads(entity_hierarchy)

    return factes, concepts, entity_hierarchy

def get_aliases(chat, aliases_keys):
    """
    Generate English aliases for given keywords.
    
    Args:
        chat: GPT chat instance
        aliases_keys (list): List of keywords to generate aliases for
        
    Returns:
        dict: Mapping of original terms to their English aliases
    """
    query_get_aliases = f'''
                        Please provide me with the aliases for each item in the array mentioned below. The aliases must be in English. Return them in the format of a dictionary, without including any additional context outside of the dictionary. It is very important to answer all of th items within array.
                        # array:
                        {aliases_keys}
                        # example:
                        {{"申請書": ["application form","formulario de solicitud"]}}
                        '''
    answer_get_aliases = chat(message=query_get_aliases)
    answer_get_aliases = ''.join(answer_get_aliases)
    answer_get_aliases = re.sub(r'\s+', ' ', answer_get_aliases).replace(' ', '')
    aliases_table = json.loads(answer_get_aliases)
    return aliases_table

def get_facts_pairs(facts, context):
    """
    Extract entity-relationship-entity triplets from the context.
    
    Args:
        facts (list): List of extracted facts
        context (str): Input text to analyze
        
    Returns:
        list: List of triplets representing relationships between entities
    """
    query_get_aliases = f'''
                        # entities: {facts} 
                        # context: {context}
                        These are the entities extract from the context above. Please help me to extract the Knowledge Graph like entity-relationship-entity.
                        Following the output format as below is very important do not return any context just output.
                        # output:
                        [桃園市-委外再利用-焚化廠底渣]
                        [焚化量之 15%-包含-104 年全國各縣市焚化底渣產量]
                        '''
    answer_get_aliases = chat(message=query_get_aliases)
    answer_get_aliases = ''.join(answer_get_aliases)
    answer_get_aliases = re.sub(r'\s+', ' ', answer_get_aliases).replace(' ', '')
    data = [item.strip("[]").split("-") for item in answer_get_aliases.split("][")]
    return data

class SectionPairer:
    """
    A class to establish relationships between different elements in the knowledge structure.
    Handles pairing of facts, concepts, and structural elements.
    """
    
    def __init__(self):
        """Initialize an empty result list to store relationships."""
        self.res = []

    def pair_sections_with_facts(self, sections, entity_hierarchy, aliases_table):
        """
        Create relationships between facts and their corresponding concepts.
        
        Args:
            sections (list): List of document sections
            entity_hierarchy (dict): Hierarchy of entities and their concepts
            aliases_table (dict): Mapping of terms to their aliases
        """
        for concept, facts in entity_hierarchy.items():
            for fact in facts:
                fact_dict = {'type': 'fact', 'name': fact, 'aliases': aliases_table.get(fact)}
                is_a_dict = {'name': 'is_a'}
                concept_dict = {'type': 'concept', 'name': concept, 'aliases': aliases_table.get(concept)}
                self.res.append((fact_dict, is_a_dict, concept_dict))

    def pair_sections_with_concepts(self, sections, concepts, aliases_table):
        """
        Create relationships between concepts and document sections.
        
        Args:
            sections (list): List of document sections
            concepts (list): List of identified concepts
            aliases_table (dict): Mapping of terms to their aliases
        """
        for concept in concepts:
            for section in sections:
                concept_dict = {'type': 'concept', 'name': concept, 'aliases': aliases_table.get(concept)}
                include_in_dict = {'name': 'include_in'}
                structure_dict = {'type': 'structure', 'name': section}
                self.res.append((concept_dict, include_in_dict, structure_dict))

    def pair_lower_to_higher_sections(self, sections):
        """
        Establish hierarchical relationships between document sections.
        
        Args:
            sections (list): List of document sections in hierarchical order
        """
        for section_p in range(len(sections) - 1):
            rest_sections = sections[section_p + 1:]
            
            for r_section in rest_sections:
                structure_dict_1 = {'type': 'structure', 'name': r_section}
                part_of_dict = {'name': 'part_of'}
                structure_dict_2 = {'type': 'structure', 'name': sections[section_p]}
                self.res.append((structure_dict_1, part_of_dict, structure_dict_2))
    
    def pair_facts_and_facts(self, facts_pair):
        """
        Create relationships between different facts.
        
        Args:
            facts_pair (list): List of fact pairs to be related
        """
        for pair in facts_pair:
            fact1 = pair[0]
            relatioship = pair[1]
            fact2 = pair[2]
            fact_dict_1 = {'type': 'structure', 'name': fact1}
            relationship_dict = {'name': relatioship}
            fact_dict_2 = {'type': 'structure', 'name': fact2}
            self.res.append((fact_dict_1, relationship_dict, fact_dict_2))
        
    def get_results(self):
        """
        Retrieve all established relationships.
        
        Returns:
            list: All relationship triplets
        """
        return self.res


if __name__ == "__main__":
    # Example usage of the module
    chat = GptChat()

    sections = ['chapter1', 'ch1-1', 'ch1-1-1']
    page_content = '''物質必有其來源，廢棄物也不例外，依據「廢棄物清理法」第 2 條規定，廢棄物指能以搬動方式移動之下列固態或液態物質或物品： 1.被拋棄者；2.減失原效用、被放棄原效用、不具效用或效用不明者；3.於營建、製造、加工、修理、販賣、使用過程所產生目的以外之產物；4.製程產出物不具可行之利用技術或不具市場經濟價值者；5.其他經中央主管機關公告，並分成一般廢棄物和事業廢棄物兩種。一般廢棄物指事業廢棄物以外之廢棄物，惟包括事業員工生活產生之廢棄物。事業廢棄物指事業活動產生非屬其員工生活產生之廢棄物，再分成一般事業廢棄物和有害事業廢棄物兩種。有害事業廢棄物是由事業所產生具有毒性、危險性，其濃度或數量足以影響人體健康或污染環境之廢棄物。至於一般事業廢棄物，則是由事業所產生有害事業廢棄物以外之廢棄物。以下分別介紹一般廢棄物和事業廢棄物的產源。'''

    # extract facts and concepts in LLM
    factes, concepts, entity_hierarchy = get_concept_n_fact(chat, page_content)
    # extract fact-relationship-fact in LLM
    facts_pairs = get_facts_pairs(factes, page_content)
    # get aliases and save as dict in LLM
    aliases_keys = factes + concepts
    aliases_table = get_aliases(chat, aliases_keys)

    # start to generate triplets
    pairer = SectionPairer()
    pairer.pair_sections_with_facts(sections, entity_hierarchy, aliases_table)
    pairer.pair_sections_with_concepts(sections, concepts, aliases_table)
    pairer.pair_lower_to_higher_sections(sections)
    pairer.pair_facts_and_facts(facts_pairs)

    triplets = pairer.get_results()
    for tri in triplets:
        print(tri)