# KAQG: Knowledge Graph Enhanced Question Generation

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)  
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)  
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)  

KAQG is a multi-agent system that integrates **Knowledge Graphs**, **Retrieval-Augmented Generation (RAG)**, and **Educational Measurement Theory** (Item Response Theory + Bloom’s Taxonomy) to automatically generate and evaluate exam questions with controllable difficulty.

---

## 📐 System Architecture

![Architecture](docs/architecture.png)

**Workflow**:
1. **PdfRetriever** extracts text, concepts, and facts from PDFs.
2. **KnowledgeGraphService** manages Neo4j-based knowledge graphs in Docker.
3. **LlmService** handles LLM-based reasoning and text generation.
4. **SingleChoiceGenerator** creates single-choice questions from KG concepts and facts.
5. **ScqEvaluator** evaluates question quality using feature-based difficulty models.

---

## 📂 Repository Structure

```
src/
 ├─ services/
 │   ├─ llm_service.py          # LLM interface agent
 │   ├─ kg_service.py           # Knowledge graph service
 │   ├─ pdf_retriever.py        # PDF ingestion and KG construction
 │   └─ file_service.py         # File upload service
 │
 ├─ generation/
 │   └─ scq_generator.py        # Single-choice question generator
 │
 ├─ evaluation/
 │   ├─ scq_evaluator.py        # Single-choice question evaluator
 │   └─ features.py             # Difficulty feature definitions
 │
 ├─ knowsys/
 │   ├─ docker_management.py    # Neo4j container orchestration
 │   └─ knowledge_graph.py      # Neo4j graph operations
 │
 ├─ agent.py                    # Core agent framework
 └─ weighted_ranker.py          # Concept ranking with PageRank/TF-IDF
```

> **Note:** directory `evluation/` has been corrected to `evaluation/`.

---

## ⚙️ Environment Setup

### Requirements
- Python **3.12+**
- Docker (for Neo4j containers)
- Mosquitto (MQTT broker)
- Recommended: **16GB RAM**, optional **GPU** if using local LLMs

### Installation

```bash
git clone https://github.com/mfshiu/kaqg.git
cd kaqg

conda create -n kaqg python=3.12
conda activate kaqg
pip install -r requirements.txt
```

### Configuration

```bash
cp kaqg-sample.toml kaqg.toml
# Edit kaqg.toml based on your environment
```

### Start MQTT Broker (Example on Windows)

```bash
cd "C:\Program Files\mosquitto"
mosquitto -c mosquitto.conf
```

---

## 🧩 Core Services

### **FileService**
- **One-line**: Manages file upload and metadata storage.  
- **Details**: Handles binary files, extracts metadata (filename, type, encoding), and provides access to subsequent processing agents.

---

### **LlmService**
- **One-line**: Provides LLM-powered text generation.  
- **Details**: Supports ChatGPT, Claude, and LLaMA via a unified API. Subscribes to `Prompt/LlmService/Services` and responds with generated content.

---

### **KnowledgeGraphService**
- **One-line**: Creates and manages knowledge graphs in Docker-hosted Neo4j.  
- **Details**: Supports container lifecycle (create, open, stop) and enables queries such as **concepts**, **facts**, and **sections**. Subscribes to `KGService/Services` topics.

---

### **PdfRetriever**
- **One-line**: Extracts facts and concepts from PDFs into the knowledge graph.  
- **Details**: Uploads PDFs, extracts triplets (fact–relation–concept), and stores them in Neo4j. Supports section hierarchy mapping from document TOC.

---

### **SingleChoiceGenerator**
- **One-line**: Generates single-choice exam questions from KG concepts and facts.  
- **Details**: Uses **rankers** (PageRank, TF-IDF, domain-specific) to select concepts/facts, then prompts LLMs to generate structured questions. Ensures difficulty calibration with feature-based scoring.

---

### **ScqEvaluator**
- **One-line**: Evaluates difficulty and validity of generated questions.  
- **Details**: Uses 7 linguistic and structural features (stem length, option similarity, distractor plausibility, etc.) weighted by IRT + Bloom’s Taxonomy to validate question quality.

---

## 🚀 Quick Start Example

### 1. Upload PDF
```python
# Publish a PDF file to be processed
agent.publish("FileUpload/Pdf/Retrieval", {
    "kg_name": "WasteManagement",
    "file": "waste_regulations.pdf"
})
```

### 2. Generate Question
```python
criteria = {
    "question_id": "Q101",
    "subject": "WasteManagement",
    "document": "Regulation Book",
    "section": ["Chapter 1", "Subsection 1.1"],
    "difficulty": 50
}
agent.publish("Create/SCQ/Generation", criteria)
```

### 3. Evaluate Question
```python
agent.publish("Evaluate/SCQ", {"question_id": "Q101"})
```

---

## 📊 Example Workflow

```
PDF → PdfRetriever → KnowledgeGraphService (Neo4j) → 
Concepts/Facts → SingleChoiceGenerator → Draft Questions →
ScqEvaluator → Validated Exam Items
```

---

## 📚 References

- Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP* (2020)  
- Yu et al., *GraphRAG: RAG Meets Knowledge Graphs* (2024)  
- Shiu et al., *KAQG: A Knowledge Graph Enhanced RAG for Difficulty Controlled Question Generation* (2025, under review)

---

## 🤝 Contributing
Pull requests and issues are welcome. Please ensure tests are included for new features.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
