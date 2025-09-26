# KAQG: Knowledge‑Graph‑Enhanced RAG for Difficulty‑Controlled Question Generation

![License](https://img.shields.io/github/license/mfshiu/kaqg)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![LLM](https://img.shields.io/badge/LLM-Compatible-green)
![Graph](https://img.shields.io/badge/Neo4j-5.x-orange)

# Introduction
KAQG is an open-source educational AI framework that integrates Knowledge Graphs (KG), Retrieval-Augmented Generation (RAG), and Assessment Theory to generate high-quality, difficulty-calibrated exam questions. It supports explainable multi-step reasoning and aligns generated items with Bloom’s Taxonomy and Item Response Theory (IRT).

---

## 🔍 Features

- **Knowledge Graph Construction**: Extracts SPO triples and concept hierarchies from multimodal educational materials.
- **Semantic Retrieval**: Uses KG-aware fact chaining for more coherent context selection.
- **Question Generation**: Employs LLMs and PageRank for ranking concepts, aligned with cognitive difficulty levels.
- **Assessment Integration**: Quantifies difficulty using Bloom’s levels and validates questions through IRT.
- **Multi-Agent System (MAS)**: Distributed agents coordinate retrieval, generation, and evaluation via DDS-based pub-sub.

---

## 📐 System Architecture

The system comprises:
- `KAQG-Retriever`: Builds domain-isolated KGs from documents (PDF, video, web).
- `KAQG-Generator`: Creates and validates exam questions with psychometric calibration.
- `AI Agents Framework`: Manages autonomous tasks using DDS communication.

![KAQG Architecture](docs/architecture.png)

---

## 📁 Repository Structure

```bash
kaqg/
├── apps/             # Utility tools
├── doc/             # Documents
├── know-edit/          # KG editor
├── src/             # Source codes
    ├── evluation/          # Question assessment
    ├── generation/          # Question generation
    ├── knowsys/             # KG library
    ├── retrieval/            # Material retrieval
    └── services/          # Services agents
├── unit_test/              # Unit tests
└── README.md
```

# Environment Setup

- Docker  
- MQTT

# Installation

## **Environment**

```bash
git clone https://github.com/mfshiu/kaqg.git
cd kaqg
conda create -n kaqg python=3.12
conda activate kaqg
pip install -r requirements.txt
```

## **Configuration**

```bash
cp kaqg-sample.toml kaqg.toml
```
Modify the settings according to the inline comments for your environment.

## **Launch Tools**

### Start MQTT broker

Example:
```bash
cd "C:\Program Files\mosquitto"
mosquitto -c mosquitto.conf
```

## **Agent Concepts**

KAQG adopts the following perception–thinking–action view of agents:

- **Perception** in KAQG includes messages **proactively pushed via APIs**.
- **Thinking** in KAQG includes **rule‑following reactive behaviors**, which we treat as a broad definition of “thinking.”
- **Action** is unchanged from standard agent definitions.

A **self-contained agent** is an agent that does **not depend on other agents** and completes the full perception–thinking–action loop. In this system, examples include **File Service** and **LLM Service**.

# Start and Test Retrieval Agents

## File Service

### Overview

FileService is an autonomous agent that handles file uploads by generating unique IDs, storing files, and returning structured metadata for downstream processing.

### Details

The **FileService** is an autonomous agent that manages file uploads within the KAQG multi-agent system. Built on the `Agent` framework, it subscribes to the `FileUpload/FileService/Services` topic and processes incoming binary parcels containing file data. When a file is received, FileService generates a unique file ID using a SHA-1 hash combined with a timestamp and random seed, determines its MIME type and encoding, and saves it to a structured directory under its configured home path. It then returns metadata—such as file ID, name, type, encoding, and storage path—excluding raw content. This service provides the foundational file storage and identification mechanism that other agents (e.g., `PdfRetriever`, `KnowledgeGraphService`) depend on for further knowledge extraction and processing.

### Start

```bash
python src\services\file_service.py
```

### Test (in another terminal)

```bash
python unit_test\test_file_upload.py
```
Verify that the response is **OK**.

## LLM Service

### Overview

LlmService is an agent that processes natural language prompts by invoking a configured large language model (e.g., ChatGPT, Claude, or LLaMA) and returning generated responses.

### Details

The **LlmService** is a core agent in the KAQG framework responsible for managing interactions with large language models. It subscribes to the topic `Prompt/LlmService/Services`, listens for incoming text parcels containing user prompts, and delegates them to the appropriate LLM backend (such as ChatGPT, Claude, or LLaMA) based on configuration. Using a standardized interface (`ChatLLM`), the service generates responses and returns them as structured outputs to the requesting agent. This modular design allows seamless switching between LLM providers and ensures scalability by integrating into the multi-agent publish–subscribe system.

### Start

```bash
python src\services\llm_service.py
```

### Test (in another terminal)

```bash
python unit_test\test_llm_service.py
```
Verify that the response is **OK**.

## KG Service

### Overview

KnowledgeGraphService is an agent that manages the lifecycle and access of Neo4j-based knowledge graphs, supporting creation, data insertion, and semantic queries.

### Details

The **KnowledgeGraphService** acts as the central controller for knowledge graph operations within the KAQG multi-agent system. It leverages Docker-managed Neo4j containers to create and maintain isolated knowledge graphs for different subjects or domains. Through a publish–subscribe interface, the service listens on dedicated topics to handle graph creation, return access points (HTTP and Bolt URLs), insert extracted triplets, and query concepts or sections linked to documents. By orchestrating container management and graph queries transparently, it ensures scalability, modularity, and reliable integration of structured knowledge into downstream tasks such as question generation and retrieval.

### Start

```bash
python src\services\kg_service.py
```

### Test (in another terminal)

```bash
python unit_test\test_kg_service.py
```
Verify that the response is **OK**.

## PDF Retrieval Service

### Overview

PdfRetriever is an agent that processes uploaded PDF files by extracting text, identifying facts, concepts, and relationships, and converting them into structured knowledge graph triplets.

### Details

The **PdfRetriever** agent automates knowledge extraction from PDF documents for integration into the KAQG system. Upon receiving an uploaded PDF, it collaborates with FileService to store the file, reads its pages, and analyzes each page using LLM-based extraction methods. It identifies key facts, groups them into higher-level concepts, and determines inter-fact relationships, then organizes this information into structured triplets. These triplets are published to the KnowledgeGraphService for storage in Neo4j, enabling downstream processes such as semantic retrieval and question generation. Through this workflow, PdfRetriever transforms unstructured document content into structured, queryable knowledge.

### Launch Order

```bash
python src\services\file_service.py
python src\services\llm_service.py
python src\services\kg_service.py
python src\retrieval\pdf_retriever.py
```

### Test (in another terminal)

```bash
python unit_test\test_pdf_retriever.py
```
Verify that the response is **OK**.

# Start and Test Generation Agents

## SCQ Generator

### Overview

SingleChoiceGenerator is an agent that creates and evaluates single-choice exam questions by combining knowledge graph concepts, ranked facts, and LLM-based generation under psychometric constraints.

### Details

The **SingleChoiceGenerator** agent is designed to produce high-quality single-choice questions (SCQs) with controlled difficulty for educational assessments. It queries concepts from the KnowledgeGraphService, ranks them with domain-specific rankers, and extracts relevant facts as text materials. Using weighted psychometric features aligned with Item Response Theory and Bloom’s Taxonomy, it generates multiple candidate questions via LLM prompts and evaluates them against predefined difficulty criteria. If the first attempt does not meet the standard, it retries with variations up to three times, selecting the best candidate. By integrating structured knowledge, ranking algorithms, and automatic evaluation, this agent ensures that generated questions are pedagogically sound, difficulty-calibrated, and suitable for scalable exam generation.

### Start

```bash
python src\generation\sa_generator.py
```

## SCQ Evaluator

### Overview

ScqEvaluator is an agent that evaluates single-choice questions by scoring their psychometric and linguistic features, ensuring alignment with defined difficulty criteria.

### Details

The **ScqEvaluator** agent plays a key role in validating the quality of generated exam questions. When provided with a question and its criteria, it analyzes the stem and options across seven predefined features, including stem length, technical term density, cognitive demand, option length, similarity, and distractor plausibility. Some evaluations are rule-based (e.g., stem length), while others use LLM-driven assessment for semantic accuracy. The results are returned as structured feature scores, which are then used to determine whether a question meets the target difficulty level. By combining automated heuristics with LLM-powered analysis, ScqEvaluator ensures that generated single-choice questions are pedagogically sound and psychometrically valid.

### Start

```bash
python src\evaluation\scq_evaluator.py
```

## Test Single-Choice Question Generation

### Overview

To be added.

### Launch Order

```bash
python src\services\llm_service.py
python src\services\kg_service.py
python src\generation\scq_generator.py
python src\evaluation\scq_evaluator.py
```

### Test (in another terminal)

```bash
python unit_test\test_scq_generator.py
```
Verify that the response is **OK**.

---

## 🔗 Related Projects

- 🤖 [AgentFlow](https://github.com/mfshiu/AgentFlow): Multi-agent architecture for distributed coordination and task delegation in KAQG.

---

## 🧠 Authors

- **Ching Han Chen** – Professor, National Central University  
- **Ming Fang Shiu** – Ph.D. Candidate, NCU

---

## 📬 Contact

For questions, contact the maintainer: [108582003@cc.ncu.edu.tw](mailto:108582003@cc.ncu.edu.tw)
