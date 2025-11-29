# Required when executed as the main program.
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

import json
from openai import OpenAI
import re
import time
# from transformers import AutoTokenizer, AutoModelForTokenClassification
# from transformers import pipeline

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))


class GptChat:
    def __init__(self, api_key, model="gpt-4o-mini"):
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
                # print(chunk.choices[0].delta.content, end="")
        return reply



class GptChatNoStream:
    def __init__(self, api_key, model="gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def __call__(self, message="Say this is a test"):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": message}],
            stream=False,  # Set stream to False
        )
        reply = response.choices[0].message.content
        # print(reply)  # Print the response
        return reply



class FactConceptExtractor:
    def __init__(self, chat=None):
        self.chat = chat if chat else GptChat(api_key=app_helper.config['service']['llm']['ChatGpt']['openai_api_key'])


    def get_concept_n_fact(self, context):
        query_concept_and_fact = f'''
Please structure the following context into triplets. 
The context will be divided into two levels: fact and concept. 
A fact refers to all entities that can be found in the context, 
while a concept refers to the higher-level categories of those facts.

For example:
"In the 104th year, the incineration bottom ash produced by various counties and cities accounted 
for about 15% of the incineration amount. 
Due to its relatively harmless nature, to reduce landfill load and promote resource recycling, 
the Ministry of Environment has provided funding to encourage local governments 
to sort and reuse it as alternative construction materials. 
Currently, cities such as Keelung, Taipei, New Taipei, Taoyuan, Hsinchu, Miaoli, Taichung, Changhua, Chiayi, 
Chiayi County, Tainan, Kaohsiung, and Pingtung have outsourced the reuse of incineration bottom ash. 
According to statistics, the amount of reused bottom ash in 104th year accounted 
for 89.3% of the total bottom ash produced that year, and the rest was disposed of by landfill."

This can be broken down into the following facts and concepts, and each fact needs to be categorized 
as one concept, as shown in the entity_hierarchy:
facts = [
    "104th year",
    "15%",
    "89.3%",
    "Ministry of Environment",
    "Keelung City",
    "Taipei City",
    "New Taipei City",
    "Taoyuan City",
    "Hsinchu City",
    "Miaoli County",
    "Taichung City",
    "Changhua County",
    "Chiayi City",
    "Chiayi County",
    "Tainan City",
    "Kaohsiung City",
    "Pingtung County",
    "incineration bottom ash",
    "landfill",
    "resource recycling",
    "alternative construction materials",
    "incineration plant",
    "general waste",
    "bottom ash",
    "sorting",
    "reuse",
    "landfilling",
    "final disposal"
]

concepts = [
    "year",
    "percentage",
    "government organization",
    "city",
    "county",
    "waste",
    "facility",
    "waste management",
    "construction materials",
    "waste treatment"
]

entity_hierarchy = {{
                    "year": ["104th year"],
                    "percentage": ["15%", "89.3%"],
                    "government organization": ["Ministry of Environment"],
                    "city": [
                        "Keelung City", "Taipei City", "New Taipei City", "Taoyuan City", "Hsinchu City",
                        "Taichung City", "Chiayi City", "Tainan City", "Kaohsiung City"
                    ],
                    "county": ["Miaoli County", "Changhua County", "Chiayi County", "Pingtung County"],
                    "waste": ["incineration bottom ash", "general waste", "bottom ash"],
                    "facility": ["landfill", "incineration plant"],
                    "waste management": ["resource recycling"],
                    "construction materials": ["alternative construction materials"],
                    "waste treatment": ["sorting", "reuse", "landfilling", "final disposal"]
                    }}

Please follow the rule as above and help me to extract the facts and concepts from the new context following the output format.
# context:
{context}

Following the output format below is very important. Do not return any context, just output.
# output format:
facts = []
concepts = []
entity_hierarchy = {{concept1:[fact_a, fact_b]}}

Note: "Please respond in the same language as the content provided."
'''
        answer_concept_and_fact = self.chat(message=query_concept_and_fact)
        answer_concept_and_fact = ''.join(answer_concept_and_fact)
        answer_concept_and_fact = re.sub(r'\s+', ' ', answer_concept_and_fact)

        answer_concept_and_fact = answer_concept_and_fact.split('facts = ')[-1].split('concepts = ')
        factes = json.loads(answer_concept_and_fact[0])

        text = answer_concept_and_fact[1].split('entity_hierarchy = ')
        concepts = text[0].replace('[', '').replace(']', '').replace('"', '').strip().split(',')
        # concepts = text[0].replace('[', '').replace(']', '').replace('"', '').replace(' ', '').strip().split(',')

        entity_hierarchy = text[1]
        # logger.verbose(f"entity_hierarchy:\n{entity_hierarchy}")
        try:
            entity_hierarchy = json.loads(app_helper.fix_json(entity_hierarchy))
        except Exception as e:
            raise ValueError(f"""{e}
    Error in parsing entity_hierarchy:
    {entity_hierarchy}

    answer_concept_and_fact:
    {answer_concept_and_fact}""")

        return factes, concepts, entity_hierarchy


    def get_aliases(self, aliases_keys):
        query_get_aliases = f'''
Please provide me with the aliases for each item in the array mentioned below. 
The aliases must be in English. 
Return them in the format of a dictionary, without including any additional context outside of the dictionary. 
It is very important to answer all of the items within the array.
# array:
{aliases_keys}
# example:
{{"application form": ["application form","formulario de solicitud"]}}
'''
        answer_get_aliases = self.chat(message=query_get_aliases)
        answer_get_aliases = ''.join(answer_get_aliases)
        answer_get_aliases = re.sub(r'\s+', ' ', answer_get_aliases).replace(' ', '')

        try:
            aliases_table = json.loads(answer_get_aliases)
        except Exception as e:
            logger.exception(e)
            aliases_table = {}

        return aliases_table


    def get_facts_pairs(self, facts, context):
        facts_relations_prompt = f'''
# entities: {facts} 
# context: {context}
These are the entities extracted from the context above. Please help me to extract the Knowledge Graph like entity|relationship|entity.
Following the output format below is very important. Do not return any context, just output.
# output:
[Taoyuan City|outsourced reuse|incineration plant bottom ash]
[15% of incineration amount|includes|incineration bottom ash produced in the 104th year across all cities]
Note: "Please respond in the same language as the content provided."
'''
        facts_relations = self.chat(message=facts_relations_prompt)
        facts_relations = ''.join(facts_relations)
        facts_relations = re.sub(r'\s+', ' ', facts_relations) #.replace(' ', '')
        data = [item.strip("[]").split("|") for item in facts_relations.split("][")]
        return data



class SectionPairer:
    """
    A class to establish relationships between different elements in the knowledge structure.
    Handles pairing of facts, concepts, and structural elements.
    """
    
    def __init__(self):
        """Initialize an empty result list to store relationships."""
        self.res = []


    def pair_concepts_with_facts(self, sections, entity_hierarchy, aliases_table, factes):
        fact_set = set(factes)
        is_a_dict = {'name': 'is_a'}
        
        for concept, facts in entity_hierarchy.items():
            for fact in facts:
                fact_dict = {'type': 'fact', 'name': fact, 'aliases': aliases_table.get(fact)}
                concept_dict = {'type': 'concept', 'name': concept, 'aliases': aliases_table.get(concept)}
                self.res.append((fact_dict, is_a_dict, concept_dict))
                fact_set.discard(fact)
                # logger.warning(f"{fact} -> {concept}")
                
        for fact in fact_set:
            fact_dict = {'type': 'fact', 'name': fact, 'aliases': aliases_table.get(fact)}
            concept_dict = {'type': 'concept', 'name': 'others', 'aliases': []}
            self.res.append((fact_dict, is_a_dict, concept_dict))


    def pair_sections_with_concepts(self, sections, concepts, aliases_table):
        """
        Create relationships between concepts and document sections.
        
        Args:
            sections (list): List of document sections
            concepts (list): List of identified concepts
            aliases_table (dict): Mapping of terms to their aliases
        """
        structure_type = 'document' if len(sections) == 1 else 'structure'
        structure_dict = {'type': structure_type, 'name': sections[-1][-1]}
        include_in_dict = {'name': 'include_in'}
        
        for concept in concepts:
            concept_dict = {'type': 'concept', 'name': concept, 'aliases': aliases_table.get(concept)}
            self.res.append((concept_dict, include_in_dict, structure_dict))


    def pair_lower_to_higher_sections(self, sections, meta):
        sections = sections[-1]
        logger.verbose(f"pair sections: {sections}, meta: {meta}")
        
        part_of_dict = {'name': 'part_of'}
        for i in range(len(sections)-1):
            if i == 0:
                structure_dict_0 = {'type': 'document', 'name': sections[i], 'meta': meta}
            else:
                structure_dict_0 = {'type': 'structure', 'name': sections[i]}
            structure_dict_1 = {'type': 'structure', 'name': sections[i+1]}
            self.res.append((structure_dict_1, part_of_dict, structure_dict_0))
            logger.verbose(f"append sections: {(structure_dict_1, part_of_dict, structure_dict_0)}")
   
    
    def pair_facts_and_facts(self, facts_pair):
        """
        Create relationships between different facts.
        
        Args:
            facts_pair (list): List of fact pairs to be related
        """
        for pair in facts_pair:
            if len(pair) != 3:
                logger.warning(f"Skip for wrong facts relation: {pair}")
                continue
            try:
                fact1 = pair[0]
                relatioship = pair[1]
                fact2 = pair[2]
                fact_dict_1 = {'type': 'fact', 'name': fact1}
                relationship_dict = {'name': relatioship}
                fact_dict_2 = {'type': 'fact', 'name': fact2}
                self.res.append((fact_dict_1, relationship_dict, fact_dict_2))
            except Exception as e:
                logger.error(f"pair: {pair}")
                logger.exception(e)
        
        
    def get_results(self):
        """
        Retrieve all established relationships.
        
        Returns:
            list: All relationship triplets
        """
        return self.res



if __name__ == "__main__":
    start_time = time.time()
    # chat = GptChat(api_key=app_helper.config['service']['llm']['ChatGpt']['openai_api_key'])
    # chat = GptChatNoStream()

    sections = ['chapter1', 'ch1-1', 'ch1-1-1']
    page_content = '''物質必有其來源，廢棄物也不例外，依據「廢棄物清理法」第 2 條規定，廢棄物指能以搬動方式移動之下列固態或液態物質或物品： 1.被拋棄者；2.減失原效用、被放棄原效用、不具效用或效用不明者；3.於營建、製造、加工、修理、販賣、使用過程所產生目的以外之產物；4.製程產出物不具可行之利用技術或不具市場經濟價值者；5.其他經中央主管機關公告，並分成一般廢棄物和事業廢棄物兩種。一般廢棄物指事業廢棄物以外之廢棄物，惟包括事業員工生活產生之廢棄物。事業廢棄物指事業活動產生非屬其員工生活產生之廢棄物，再分成一般事業廢棄物和有害事業廢棄物兩種。有害事業廢棄物是由事業所產生具有毒性、危險性，其濃度或數量足以影響人體健康或污染環境之廢棄物。至於一般事業廢棄物，則是由事業所產生有害事業廢棄物以外之廢棄物。以下分別介紹一般廢棄物和事業廢棄物的產源。'''


    et = FactConceptExtractor()
    # extract facts and concepts in LLM
    factes, concepts, entity_hierarchy = et.get_concept_n_fact(page_content)
    # extract fact-relationship-fact in LLM
    facts_pairs = et.get_facts_pairs(factes, page_content)
    # get aliases and save as dict in LLM
    aliases_keys = factes + concepts
    aliases_table = et.get_aliases(aliases_keys)

    # start to generate triplets
    pairer = SectionPairer()
    pairer.pair_concepts_with_facts(sections, entity_hierarchy, aliases_table)
    pairer.pair_sections_with_concepts(sections, concepts, aliases_table)
    pairer.pair_lower_to_higher_sections(sections)
    pairer.pair_facts_and_facts(facts_pairs)

    triplets = pairer.get_results()
    for tri in triplets:
        print(tri)

    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Total execution time: {elapsed_time:.2f} seconds")
