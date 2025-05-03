# KAQG: Knowledge‑Graph‑Enhanced RAG for Difficulty‑Controlled Question Generation

![License](https://img.shields.io/github/license/mfshiu/kaqg)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![LLM](https://img.shields.io/badge/LLM-Compatible-green)
![Graph](https://img.shields.io/badge/Neo4j-5.x-orange)

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
├── retriever/          # KG construction & document parsing
├── generator/          # Question generation & assessment
├── agents/             # MAS components using DDS
├── configs/            # YAML configuration files
├── data/               # Sample data & KG exports
├── notebooks/          # Demos and experimental scripts
├── tests/              # Unit tests
└── README.md
```

---

## ⚙️ Installation

```bash
git clone https://github.com/mfshiu/kaqg.git
cd kaqg
pip install -r requirements.txt
```

You’ll also need:
- Neo4j 5.x
- OpenAI-compatible LLMs (e.g., GPT-4 or LLaMA2)
- DDS middleware (e.g., Eclipse Cyclone DDS)

---

## 🚀 Usage

1. **Build Knowledge Graphs**
   ```bash
   python retriever/build_graph.py --input data/textbooks/
   ```

2. **Generate Questions**
   ```bash
   python generator/generate_questions.py --subject "Environmental Science"
   ```

3. **Evaluate with IRT**
   ```bash
   python generator/evaluate_questions.py --model irt
   ```

---

## 📊 Results

Validated against ACT reading passages with over 90 system-generated questions at three difficulty levels. Questions were evaluated by domain experts and showed high alignment with psychometric expectations.

---

## 🔗 Related Projects

- 🤖 [AgentFlow](https://github.com/mfshiu/AgentFlow): Multi-agent architecture for distributed coordination and task delegation in KAQG.

---

## 📄 Citation

If you use KAQG in academic work, please cite:

```
@article{kaqg2025,
  title={KAQG: A Knowledge-Graph-Enhanced RAG for Difficulty-Controlled Question Generation},
  author={Chen, Ching Han and Shiu, Ming Fang},
  journal={IEEE Transactions on Learning Technologies},
  year={2025}
}
```

---

## 🧠 Authors

- **Ching Han Chen** – Professor, National Central University  
- **Ming Fang Shiu** – Ph.D. Candidate, NCU

---

## 📬 Contact

For questions, contact the maintainer: [108582003@cc.ncu.edu.tw](mailto:108582003@cc.ncu.edu.tw)

---

Would you like a version of this saved as `README.md` for direct upload?
