# scq_generator_bank.py
# 新版本建題模組：以題庫 xlsx 為樣板，依科目+章隨機選題，以第 N 欄文字化敘述代入 LLM 產生新題。
# 參考 gen_questions_from_folder.py 作法，移植至 Agent 架構。
#
# Required when executed as the main program.
import os
import sys
import json
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])
###

import logging
logger = logging.getLogger(os.getenv('LOGGER_NAME'))

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel

from services.llm_service import Topic as LlmTopic

from generation.bank_loader import BankLoader


# 與 gen_questions_from_folder 相同的 prompt 與解析邏輯
GEN_PROMPT_TEMPLATE = """你是一位專業教師。請根據「樣板題」的題型與「教材子句」的內容，產生一題新的選擇題。

【樣板題】
題幹：{stem}
選項1：{opt1}
選項2：{opt2}
選項3：{opt3}
選項4：{opt4}
正確答案：{answer}

【教材子句】
{clauses}

【要求】
1. 難度：{difficulty_name}（{difficulty}）。
2. 新題目的「正確答案」必須與樣板題不同（若樣板題答案為 1，新題答案須為 2、3 或 4）。
3. 若有教材子句，請僅依子句內容出題；若無教材子句，請依樣板題型與風格自行出題，內容需合理。
4. 回傳「一個」JSON 物件，不要其他說明。格式如下：
{{
  "stem": "新題幹",
  "option1": "選項1內容",
  "option2": "選項2內容",
  "option3": "選項3內容",
  "option4": "選項4內容",
  "answer": "1 或 2 或 3 或 4"
}}
"""
CLAUSES_PLACEHOLDER = "（無教材子句，請依樣板題型與風格自行出題，內容需合理且符合該難度。）"
DIFFICULTY_NAMES = {1: "易", 2: "中", 3: "難"}


def _normalize_answer(a):
    if not a:
        return "1"
    a = str(a).strip().upper()
    if a in ("A", "1"):
        return "1"
    if a in ("B", "2"):
        return "2"
    if a in ("C", "3"):
        return "3"
    if a in ("D", "4"):
        return "4"
    return "1"


def _extract_json_object(text):
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                raw = text[start : i + 1]
                raw = re.sub(r",\s*}", "}", raw)
                raw = re.sub(r",\s*]", "]", raw)
                return raw
    return None


def parse_llm_question_json(response_text):
    if response_text is None:
        return None
    if isinstance(response_text, dict):
        response_text = response_text.get("content") or response_text.get("response") or str(response_text)
    text = (response_text or "").strip()
    if not text:
        return None

    def make_result(obj):
        a = _normalize_answer(obj.get("answer"))
        return {
            "stem": (obj.get("stem") or obj.get("題幹") or "").strip(),
            "option1": (obj.get("option1") or obj.get("選項1") or "").strip(),
            "option2": (obj.get("option2") or obj.get("選項2") or "").strip(),
            "option3": (obj.get("option3") or obj.get("選項3") or "").strip(),
            "option4": (obj.get("option4") or obj.get("選項4") or "").strip(),
            "answer": a,
        }

    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.lower().startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                try:
                    obj = json.loads(part)
                    return make_result(obj)
                except json.JSONDecodeError:
                    pass
            extracted = _extract_json_object(part)
            if extracted:
                try:
                    obj = json.loads(extracted)
                    return make_result(obj)
                except json.JSONDecodeError:
                    pass
    try:
        obj = json.loads(text)
        return make_result(obj)
    except json.JSONDecodeError:
        pass
    extracted = _extract_json_object(text)
    if extracted:
        try:
            obj = json.loads(extracted)
            return make_result(obj)
        except json.JSONDecodeError:
            pass
    return None


class BankQuestionGenerator(Agent):
    TOPIC_CREATE = "Create/SCQ/Generation"  # 與 SingleChoiceGenerator 相同，可替換

    def __init__(self, config: dict):
        super().__init__(name="scq.generation.bank", agent_config=config)
        self._bank = BankLoader()

    def on_activate(self):
        logger.verbose("on_activate")
        self.subscribe(BankQuestionGenerator.TOPIC_CREATE, topic_handler=self.handle_create)

    def handle_create(self, topic, pcl: TextParcel):
        question_criteria = pcl.content
        logger.debug("question_criteria: %s", question_criteria)

        subject = question_criteria.get("subject") or question_criteria.get("科目")
        if not subject:
            return self._error_assessment(question_criteria, "缺少 subject")

        chapter = question_criteria.get("章") or question_criteria.get("chapter") or question_criteria.get("section")
        if isinstance(chapter, list):
            chapter = chapter[0] if chapter else None

        template = self._bank.pick_template(str(subject).strip(), chapter)
        if not template:
            return self._error_assessment(question_criteria, f"題庫無科目 {subject} 或章 {chapter} 的題目")

        logger.debug("樣板題 章=%s 節=%s", template.get("章"), template.get("節"))

        result = self._generate_one(template)
        if not result:
            return self._error_assessment(question_criteria, "LLM 生成失敗")

        assessment = {
            "question_criteria": question_criteria,
            "question": self._to_question_format(result),
        }
        assessment["question_criteria"]["章"] = template.get("章")
        assessment["question_criteria"]["節"] = template.get("節")
        assessment["question_criteria"]["頁碼"] = template.get("頁碼")
        assessment["question_criteria"]["難度"] = template.get("難度")
        logger.info("generated_question: %s", assessment)
        return assessment

    def _generate_one(self, template, max_retries=3):
        use_difficulty = template.get("難度")
        if use_difficulty not in (1, 2, 3):
            use_difficulty = 1
        template_answer = (template.get("answer") or "1").strip()
        if template_answer not in ("1", "2", "3", "4"):
            template_answer = "1"
        difficulty_name = DIFFICULTY_NAMES.get(use_difficulty, str(use_difficulty))
        clauses_text = (template.get("clauses") or "").strip()
        if not clauses_text:
            clauses_text = CLAUSES_PLACEHOLDER

        prompt = GEN_PROMPT_TEMPLATE.format(
            stem=template.get("stem", ""),
            opt1=template.get("opt1", ""),
            opt2=template.get("opt2", ""),
            opt3=template.get("opt3", ""),
            opt4=template.get("opt4", ""),
            answer=template_answer,
            clauses=clauses_text,
            difficulty=use_difficulty,
            difficulty_name=difficulty_name,
        )

        return_topic = self.agent_id
        self.subscribe(return_topic)
        pcl = TextParcel(
            {"messages": [{"role": "user", "content": prompt}]},
            topic_return=return_topic,
        )

        for attempt in range(max_retries):
            try:
                resp = self.publish_sync(LlmTopic.LLM_PROMPT.value, pcl, timeout=90)
            except TimeoutError:
                logger.warning("LLM 逾時")
                continue
            content = resp.content if resp else {}
            response = content.get("response") if isinstance(content, dict) else None
            if not response:
                continue
            parsed = parse_llm_question_json(response)
            if parsed:
                return {
                    "stem": parsed.get("stem", ""),
                    "option1": parsed.get("option1", ""),
                    "option2": parsed.get("option2", ""),
                    "option3": parsed.get("option3", ""),
                    "option4": parsed.get("option4", ""),
                    "answer": parsed.get("answer", "1"),
                    "章": template.get("章"),
                    "節": template.get("節"),
                    "頁碼": template.get("頁碼"),
                    "難度": use_difficulty,
                }
        return None

    def _to_question_format(self, result: dict) -> dict:
        """轉換為 scq_generator 的 question 格式（option_A/B/C/D）。"""
        return {
            "stem": result.get("stem", ""),
            "option_A": result.get("option1", ""),
            "option_B": result.get("option2", ""),
            "option_C": result.get("option3", ""),
            "option_D": result.get("option4", ""),
            "answer": result.get("answer", "1"),
        }

    def _error_assessment(self, question_criteria: dict, message: str) -> dict:
        return {
            "question_criteria": question_criteria,
            "question": {
                "stem": f"【系統錯誤】{message}",
                "option_A": "系統產生試題失敗。",
                "option_B": "請稍後再試。",
                "option_C": "請聯絡系統管理員。",
                "option_D": "以上皆是。",
                "answer": "D",
            },
        }


if __name__ == "__main__":
    agent = BankQuestionGenerator(app_helper.get_agent_config())
    agent.start_process()
    app_helper.wait_agent(agent)
