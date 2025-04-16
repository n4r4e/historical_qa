# Knowledge Graph QA System from Historical Newspapers

This project builds a spatio-temporal knowledge graph from historical newspaper articles and integrates Large Language Models (LLMs) to enable natural language question answering. A web application interface is also provided for ease of use (Live demo: https://qa-qf7q.onrender.com/).


## Features

- Text scraped from online newspaper archives (custom browser console script)
- LLM-based entity & relation extraction (OpenAI models)
- Spatial and temporal metadata enhancement : coordinates, ISO dates
- Global entity integration and deduplication across articles
- Export to Neo4j graph database
- LLM-based natural language QA over the graph (LangChain)
- Web interface deployed (FastAPI)


## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/historical_qa.git
cd historical_qa
```

### 2. Configure your environment
Edit `.env.example` and rename it to `.env`:

```
OPENAI_API_KEY=your_openai_key
NEO4J_URI=bolt+s://your_neo4j_uri
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Extract article texts
Extract article texts using a custom script in the browser console from [e-newspaperarchives.ch](https://www.e-newspaperarchives.ch/):

1. Open browser DevTools > Console 
2. Paste script `newspaper_console_scraper.js` 
3. Navigate to each article you want to capture 
4. For each article, run `window.captureCurrentArticle()` 
5. When finished, run `window.generateNewspaperJSON()` to get the JSON and download the file.

### 5. Extract entities and relations from article JSON
Extract entities and relations from article text using LLMs (OpenAI models):

```
python src/extract_info.py
```

This process uses two methods:
- Method 1: Divides articles into chunks, extracts entities/relations from each chunk, then integrates them
- Method 2: Summarizes articles and extracts entities/relations from the summaries

### 6. Enhance Spatial and Temporal Information
Add coordinates and standardized time formats to spatial and temporal entities:

```
python src/geo_temp_enhancer.py
```


### 7. Global Entity Integration
Integrate entities across multiple articles and remove duplicates:
 
```
python src/global_entity_integrator.py
```


### 8. Create Graph Database
Import extracted entities and relations into Neo4j as a graph database:

This process converts relations into assertion nodes that connect: 
- Subject entities(via "SUBJECT_OF")
- Object entities (via "OBJECT_IS")
- Temporal context entities (via "HAS_TEMPORAL_CONTEXT")
- and Spatial context entities (via "HAS_SPATIAL_CONTEXT")

Initialize the Neo4j knowledge graph by running the query in `cypher/setup_graph.cypher`

Note: This script loads CSV files hosted online (e.g., Google Drive, GitHub).

### 9. LLM-Based Natural Language Querying
Run the question-answering system using LangChain to query the Neo4j knowledge graph:

```
python src/qa_system_cli.py
```

The system translates natural language questions into Cypher queries, executes them against the knowledge graph, and transforms the results back into natural language responses.

### 10. Web Interface (optional)
Run the web interface for the QA system:

```
cd web
uvicorn app.main:app
```

A live demo is available at: https://qa-qf7q.onrender.com/

Note: Initial loading may take up to a minute due to cold start.
