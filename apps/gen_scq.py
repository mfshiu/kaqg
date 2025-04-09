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
import ast
import signal
import os
import time

from agentflow.core.agent import Agent
from agentflow.core.parcel import TextParcel, Parcel
from generation.scq_generator import SingleChoiceGenerator


is_running = True



class ExecutionAgent(Agent):
    def __init__(self, config):
        super().__init__(name='execution', agent_config=config)


    def on_activate(self):
        topic_return = 'Return/' + self.agent_id
        self.subscribe(topic_return)
        
        question_criteria = {
            'question_id': f'Q{int(time.time())}',                      # 使用者自訂題目 ID
            'subject': self.config['subject'],                          # 考試科目(KG Name)
            'section': [self.config['chapter']],                        # 指定章節
            'document': self.config['document'],                        # 文件(教材)名稱
            'difficulty': [30, 50, 70][self.config['difficulty']-1],    # 難度 30, 50, 70
        }
        self.publish(SingleChoiceGenerator.TOPIC_CREATE, TextParcel(question_criteria, topic_return))


    def on_message(self, topic: str, pcl: Parcel):
        print(self.M(f"topic: {topic}\npcl:\n{pcl}"))
        self.terminate()


def generate_question(subject, document, chapter, difficulty):
    """
    Generate a question based on the subject, chapter, and difficulty level.
    parameters:
    subject (str): The name of the subject (e.g., "Math")
    document (str): The name of the document (e.g., "Wastepro02")
    chapter (str): The name of the chapter (e.g., "Chapter 1")
    difficulty (int): The difficulty level (1: Easy, 2: Medium, 3: Difficult)    
    """

    config = app_helper.get_agent_config()
    config['subject'] = subject
    config['document'] = document
    config['chapter'] = chapter
    config['difficulty'] = difficulty
    agent = ExecutionAgent(config)
    agent.start_thread()

    timeout_seconds = 30
    while is_running and timeout_seconds and agent.is_active():
        time.sleep(1)
        timeout_seconds -= 1
        print(f"Countdown: {timeout_seconds}", end="\r", flush=True)
    print()
    if agent.is_active():
        agent.terminate()
        print(f"Timeout: The process has been terminated.")

    print(f"Question generation completed.")


def main():
    parser = argparse.ArgumentParser(description="Generate SCQ Questions")
    parser.add_argument('-s', '--subject', type=str, required=True, help='Subject name (e.g., "Math")')
    parser.add_argument('-doc', '--document', type=str, required=True, help='Document name (e.g., "Wastepro02")')
    parser.add_argument('-c', '--chapter', type=str, required=True, help='Chapter name (e.g., "Chapter 1")')
    parser.add_argument('-d', '--difficulty', type=int, default=2, help='1: Easy, 2: Medium, 3: Difficult')

    args = parser.parse_args()
    print(f"Generating SCQ for Subject: {args.subject}, Document: {args.document}, Chapter: {args.chapter}, Difficulty: {args.difficulty}")
    
    if args.difficulty < 1 or args.difficulty > 3:
        print("Error: Difficulty level must be between 1 and 3.")
        return
    
    print("Please wait...")

    question = generate_question(args.subject, args.document, args.chapter, args.difficulty)
    print(f"Generated Question:\n{question}\n")
    print("Finished generating SCQ questions.")


if __name__ == '__main__':
    def signal_handler(signal, frame):
        global is_running
        is_running = False
        print("Ctrl-C for Exiting...")
    signal.signal(signal.SIGINT, signal_handler)

    main()
