"""
SCQ Question Generator Script
-----------------------------

This script is designed to generate Single Choice Questions (SCQs) based on user-defined criteria,
including subject, document, chapter, and difficulty level. It utilizes an agent-based architecture
from the `agentflow` framework to handle the generation asynchronously.

Usage:
    python script_name.py -s SUBJECT -doc DOCUMENT -c CHAPTER -d DIFFICULTY

Arguments:
    -s / --subject     : The name of the subject (e.g., "Math")
    -doc / --document  : The name of the document or textbook (e.g., "Wastepro02")
    -c / --chapter     : The chapter within the document (e.g., "Chapter 1")
    -d / --difficulty  : Difficulty level: 1 (Easy), 2 (Medium), 3 (Hard). Default is 2.

Example:
    python gen_scq.py -s "Math" -doc "Wastepro02" -c "Chapter 1" -d 3

Features:
    - Initializes configuration via `app_helper`
    - Uses `ExecutionAgent` to publish SCQ generation requests
    - Waits for a response within a 10-second timeout
    - Gracefully handles interruption with Ctrl+C

Author: [Your Name]
Date: [Optional Date]
"""
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app_helper
app_helper.initialize(os.path.splitext(os.path.basename(__file__))[0])

import argparse
import csv
import signal
import os
import time

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel, Parcel
from generation.scq_generator import SingleChoiceGenerator


is_running = True



class QuizBankMaker(Agent):
    def __init__(self, config):
        super().__init__(name='execution', agent_config=config)
        self.quiz_bank = []  # Initialize an empty list to store quiz questions
        
        
    def _gen_quiz(self):
        topic_return = 'Return/' + self.agent_id
        self.subscribe(topic_return)

        question_criteria = {
            'question_id': f'Q{int(time.time())}',                                      # 使用者自訂題目 ID
            'subject': self.config['subject'],                                          # 考試科目(KG Name)
            'section': [self.config['chapter']] if self.config['chapter'] else None,    # 指定章節
            'document': self.config['document'],                                        # 文件(教材)名稱
            'difficulty': [30, 50, 70][self.config['difficulty']-1],                    # 難度 30, 50, 70
        }
        self.publish(SingleChoiceGenerator.TOPIC_CREATE, TextParcel(question_criteria, topic_return))


    def on_activate(self):
        topic_return = 'Return/' + self.agent_id
        self.subscribe(topic_return)

        self._gen_quiz()


    def on_message(self, topic: str, pcl: Parcel):
        """Example of pcl:
        {
            "version": 3,
            "content": {
                "question_criteria": {
                    "question_id": "Q1744699538",
                    "subject": "Question_01",
                    "section": null,
                    "document": "Q01",
                    "difficulty": 50,
                    "feature_levels": {
                        "stem_length": 1,
                        "stem_technical_term_density": 1,
                        "stem_cognitive_level": 3,
                        "option_average_length": 3,
                        "option_similarity": 2,
                        "stem_option_similarity": 1,
                        "high_distractor_count": 1
                    },
                    "weighted_grade": 13.7
                },
                "question": {
                    "stem": "What is indicated by the audience's reaction during the performance?",
                    "option_A": "Care is taken in the performance",
                    "option_B": "Purists react with disgust",
                    "option_C": "Thoughtfulness is shown through depth",
                    "option_D": "Joyous roller coaster of a ride is experienced",
                    "answer": "B"
                }
            },
            "topic_return": null,
            "error": null
        }"""
        print(self.M(f"topic: {topic}\npcl:\n{pcl}"))
        
        qc = pcl.content['question_criteria']
        qn = pcl.content['question']
        
        question_text = f"{qn['stem']}\n\nA: {qn['option_A']}\nB: {qn['option_B']}\nC: {qn['option_C']}\nD: {qn['option_D']}\n"
        quiz = [qc['subject'], question_text, qn['answer']]
        quiz.extend(qc['feature_levels'].values())
        quiz.append(qc['weighted_grade'])
        self.quiz_bank.append(quiz)
        print(f"({len(self.quiz_bank)}) Quiz: {quiz}")
        
        if len(self.quiz_bank) < self.config['number_of_quizzes']:
            self._gen_quiz()
        else:
            header = ['Passage', 'Question Text', 'Answer', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'Grade']
            with open(self.config['output'], 'w', encoding='utf-8', newline='') as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(self.quiz_bank)
            self.terminate()


def generate_quizbank(args:dict):
    config = app_helper.get_agent_config()
    config.update(args)
    agent = QuizBankMaker(config)
    agent.start_thread()

    timeout_seconds = 300
    while is_running and timeout_seconds and agent.is_active():
        time.sleep(1)
        timeout_seconds -= 1
        print(f"Countdown: {timeout_seconds}  ", end="\r", flush=True)
    print()

    if agent.is_active():
        agent.terminate()
        print(f"Timeout: The process has been terminated.")

    print(f"Completed.")


def main():
    parser = argparse.ArgumentParser(description="Generate Exam Questions Bank")
    parser.add_argument('-s', '--subject', type=str, required=True, help='Subject name (e.g., "Math")')
    parser.add_argument('-doc', '--document', type=str, required=True, help='Document name (e.g., "Wastepro02")')
    parser.add_argument('-c', '--chapter', type=str, help='Chapter name (e.g., "Chapter 1")')
    parser.add_argument('-d', '--difficulty', type=int, default=2, help='1: Easy, 2: Medium, 3: Difficult')
    parser.add_argument('-n', '--number_of_quizzes', type=int, default=10, help='Number of quizzes to generate (default: 10)')
    parser.add_argument('-o', '--output', type=str, default=f'quizbank-{time.time()}.csv', help='Output file name (default: quizbank-<timestamp>.csv)')

    args = parser.parse_args()
    print(f"Generating Exam Questions Bank for Subject: {args.subject}, Document: {args.document}, Chapter (optional): {args.chapter}, Difficulty: {args.difficulty}")

    if args.difficulty < 1 or args.difficulty > 3:
        print("Error: Difficulty level must be between 1 and 3.")
        return
    
    quizbank_file = generate_quizbank(vars(args))
    print(f"Generated Quizbank File: {quizbank_file}")
    print("\nDone.")


if __name__ == '__main__':
    def signal_handler(signal, frame):
        global is_running
        is_running = False
        print("Ctrl-C for Exiting...")
    signal.signal(signal.SIGINT, signal_handler)

    main()
