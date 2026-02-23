# 整合測試：試題命名實體 → KG fact 節點 → 關聯 → 主謂賓子句
# 需先啟動 kg_service、llm_service 與 MQTT broker。
# 用法：在專案根目錄執行
#   python -m unit_test.test_question_entities_facts
#
# 或指定 KG 名稱（預設 kg01）：
#   python -m unit_test.test_question_entities_facts kg01

import json
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import app_helper
app_helper.initialize()

import logging
logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel, Parcel

from services.kg_service import Topic as KgTopic
from services.llm_service import Topic as LlmTopic
from knowsys.knowledge_graph import KnowledgeGraph


# 試題 A
QUESTION_A = """廢棄物管理方式之演變，從過去之管末管制，逐漸朝向資源回收、源頭減量之管理方式，其最終目標期能達成何種概念？
(A) 生命週期管理
(B) 永續物質管理
(C) 綠色產品管理
(D) 物質不變管理
正確答案： (B) 永續物質管理"""

# 請 LLM 抽出命名實體，回傳 JSON：{"named_entities": ["實體1", "實體2", ...]}
NER_PROMPT = """請從以下試題文字中，抽出「命名實體」（專有名詞、重要概念、術語），不要選項代號或題幹中的 (A)(B)(C)(D)。
只回傳一個 JSON 物件，格式為：{"named_entities": ["實體1", "實體2", ...]}，不要其他說明。

試題文字：
---
""" + QUESTION_A.strip() + """
---"""


def extract_entities_from_llm_response(response_text):
    """從 LLM 回傳文字解析出 named_entities 列表。"""
    if not response_text:
        return []
    text = response_text.strip()
    # 允許外包 ```json ... ```
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                try:
                    obj = json.loads(p)
                    return obj.get("named_entities", obj.get("entities", []))
                except json.JSONDecodeError:
                    continue
    try:
        obj = json.loads(text)
        return obj.get("named_entities", obj.get("entities", []))
    except json.JSONDecodeError:
        pass
    return []


class QuestionEntitiesFactsAgent(Agent):
    """單一 Agent：依序呼叫 LLM（命名實體）→ KG ACCESS_POINT → KG 查詢，並輸出主謂賓子句。"""

    def __init__(self, agent_config, kg_name="kg01"):
        super().__init__(name="question_entities_facts", agent_config=agent_config)
        self.kg_name = kg_name
        self.entities = []
        self.clauses = []
        self.bolt_url = None

    def run(self):
        """執行：LLM 抽實體 → 取 KG 連線 → 查 fact 節點與關聯 → 輸出子句。"""
        return_topic = self.agent_id
        self.subscribe(return_topic)

        # 1) LLM 抽取命名實體
        logger.info("Step 1: 呼叫 LLM 抽取命名實體 ...")
        pcl_llm = TextParcel(
            {"messages": [{"role": "user", "content": NER_PROMPT}]},
            topic_return=return_topic,
        )
        try:
            resp_llm = self.publish_sync(LlmTopic.LLM_PROMPT.value, pcl_llm, timeout=60)
        except TimeoutError as e:
            logger.error(f"LLM 逾時: {e}")
            return
        content = resp_llm.content if resp_llm else {}
        response_text = content.get("response") if isinstance(content, dict) else None
        if isinstance(response_text, dict):
            response_text = response_text.get("content", str(response_text))
        self.entities = extract_entities_from_llm_response(response_text or "")
        logger.info(f"命名實體: {self.entities}")

        if not self.entities:
            logger.warning("未取得任何命名實體，結束。")
            return

        # 2) KG ACCESS_POINT 取得 bolt_url
        logger.info("Step 2: 向 KG 取得連線位址 ...")
        pcl_ap = TextParcel({"kg_name": self.kg_name}, topic_return=return_topic)
        try:
            resp_ap = self.publish_sync(KgTopic.ACCESS_POINT.value, pcl_ap, timeout=30)
        except TimeoutError as e:
            logger.error(f"KG ACCESS_POINT 逾時: {e}")
            return
        ap_content = resp_ap.content if resp_ap else {}
        self.bolt_url = ap_content.get("bolt_url") if isinstance(ap_content, dict) else None
        if not self.bolt_url:
            logger.error("未取得 bolt_url，結束。")
            return

        # 3) 連上 KG，查 fact 名稱為命名實體的節點，再取所有關聯並建主謂賓子句
        logger.info("Step 3: 查詢 KG 中 fact 節點與關聯，建立主謂賓子句 ...")
        self.clauses = []
        seen = set()
        with KnowledgeGraph(uri=self.bolt_url) as kg:
            for entity in self.entities:
                nodes = kg.query_nodes_by_name(entity, label="fact")
                if not nodes:
                    # 若 fact 無，可改查不限定 label
                    nodes = kg.query_nodes_by_name(entity)
                for node in nodes:
                    eid = node.get("element_id")
                    if not eid:
                        continue
                    for subj, rel, obj in kg.query_all_relationships(eid):
                        if (subj, rel, obj) in seen:
                            continue
                        seen.add((subj, rel, obj))
                        self.clauses.append((subj, rel, obj))

        # 4) 輸出
        print("\n========== 主謂賓子句 ==========")
        for i, (s, p, o) in enumerate(self.clauses, 1):
            print(f"  {i}. {s} --[{p}]--> {o}")
        print(f"共 {len(self.clauses)} 條子句。\n")


def main():
    kg_name = "S01"
    if len(sys.argv) > 1:
        kg_name = sys.argv[1].strip()

    config = app_helper.get_agent_config()
    agent = QuestionEntitiesFactsAgent(config, kg_name=kg_name)
    agent.start_thread()
    time.sleep(1)
    # 在 thread 內執行 run()：用一個訂閱與單次發送觸發
    agent.run()
    time.sleep(2)
    agent.terminate()


if __name__ == "__main__":
    main()
