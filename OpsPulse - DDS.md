This Detailed Design Specification (DDS) is tailored for a **Hackathon environment**. It prioritizes speed of implementation, use of accessible "off-the-shelf" AI tools, and a Python-centric stack, while adhering strictly to the architectural requirements defined in the SRS.

---

# **Detailed Design Specification: OpsPulse AI**

Version: 1.0 (Hackathon MVP)

**Based on:** OpsPulse AI SRS v1.0 1

## **1\. Executive Summary**

OpsPulse AI is a middleware intelligence layer designed to reduce Mean Time To Resolution (MTTR)2222. It ingests raw logs, uses NLP to classify them into distinct "event types," detects statistical anomalies using tumbling windows, and automatically retrieves remediation steps via RAG (Retrieval-Augmented Generation)3333.

## **2\. High-Level Architecture**

The system follows a uni-directional stream-processing pipeline. For the hackathon, we will use a **Microservices** approach to separate the "fast" stream processing from the "heavy" AI processing.

### **2.1 Core Modules**

1. **Log Ingestion Service:** Buffers high-velocity logs4.  
2. **Stream Processor (The Brain):** Handles parsing, NLP classification, and windowing5.  
3. **RAG Service:** Indices runbooks and retrieves solutions upon anomaly triggers6666.  
4. **Presentation Layer:** A real-time Dashboard and Alert dispatcher7777.

---

## **3\. Component Design & Implementation Logic**

### **3.1 Module A: Ingestion & PII Masking**

* **Goal:** Accept logs via TCP/UDP or HTTP, sanitize them, and push to the message broker.  
* **Hackathon Stack:** FastAPI (HTTP endpoint) or Python Socket \-\> Kafka (or Redpanda for lower overhead).  
* **Key Logic:**  
  1. **Schema Enforcement:** Ensure Timestamp, Source\_IP, Log\_Level, and Message exist8.  
  2. **PII Masking (Regex):** Before pushing to Kafka, scan Message for credit card/password patterns and replace with \[MASKED\]9.  
  3. **Serialization:** Convert to JSON and push to Kafka Topic: raw\_logs.

### **3.2 Module B: NLP Classification & Stream Processing**

* **Goal:** Normalize raw text into "Templates" and detect anomalies10101010.  
* **Hackathon Stack:** Python Consumer (using confluent-kafka) \+ Scikit-Learn (for lightweight isolation forest or Z-score) \+ SentenceTransformers (for local embeddings).  
* **Logic Flow:**  
  1. **Template Extraction (NLP):**  
     * Instead of calling an expensive LLM for *every* log, use a lightweight embedding model (e.g., all-MiniLM-L6-v2) to vectorise the log message.  
     * Cluster these vectors to assign a Class\_ID (e.g., Cluster 1 \= "DB Connection Fail")11111111.  
  2. **Tumbling Window Aggregation:**  
     * Group logs by Class\_ID.  
     * Count occurrences in fixed 1-minute windows12.  
  3. **Anomaly Detection:**  
     * **Spike Detection:** Calculate Z-Score. If $Z \> 3$, flag as Spike13.  
     * **Drop Detection:** If a known Class\_ID (like "Heartbeat") count \== 0, flag as Drop14.

### **3.3 Module C: RAG (Retrieval-Augmented Generation)**

* **Goal:** Fetch the correct runbook snippet when an anomaly is flagged15.  
* **Hackathon Stack:** LangChain \+ ChromaDB (Local Vector Store) \+ OpenAI API (or Ollama for local LLM).  
* **Workflows:**  
  1. **Ingestion (Pre-computation):**  
     * Upload PDF/MD runbooks16.  
     * Chunk text and store embeddings in ChromaDB17.  
  2. **Retrieval (Real-time):**  
     * Triggered *only* when Anomaly \== True.  
     * Query ChromaDB using the Log Template (not the specific timestamped log) as the key18.  
     * Retrieve the top 3 chunks (Remediation steps)19.

### **3.4 Module D: Alerting & Dashboard**

* **Goal:** Visualize health and send notifications.  
* **Hackathon Stack:** Streamlit (Python-only UI).  
* **UI Layout:**  
  * **Top:** Metrics Ticker (Total Logs, MTTR, Active Anomalies).  
  * **Middle:** Real-time Line Chart (Log volume per minute).  
  * **Bottom:** "Active Incidents" Table.  
    * Columns: Time, Error Class, Recommended Fix (Expandable), Link to Runbook 20.  
  * **Backend Action:** Send JSON payload to a Slack Webhook21.

---

## **4\. Data Models (Schema Design)**

### **4.1 Log Event (Kafka Message)**

JSON  
{  
  "timestamp": "2023-10-27T10:00:00Z",  
  "source\_ip": "192.168.1.5",  
  "log\_level": "ERROR",  
  "raw\_message": "Connection timeout to DB-01",  
  "masked\_message": "Connection timeout to DB-01",  
  "template\_id": "ERR\_DB\_TIMEOUT"  
}

### **4.2 Runbook Vector Document**

JSON  
{  
  "id": "runbook\_db\_01\_chunk\_4",  
  "embedding": \[0.12, \-0.05, ...\],  
  "metadata": {  
    "filename": "Database\_Recovery.pdf",  
    "page\_number": 3,  
    "content": "If DB timeout occurs, restart service via: sudo systemctl restart postgresql"  
  }  
}

22

---

## **5\. Technology Stack Selection (Hackathon Optimized)**

| Component | Technology Choice | Rationale |
| :---- | :---- | :---- |
| **Language** | Python 3.10+ | Native support for AI/ML and rapid prototyping. |
| **Message Broker** | Redpanda (Docker) | Kafka-compatible but lighter and faster to set up. |
| **Vector DB** | ChromaDB | Open-source, runs locally, easy Python integration23. |
| **LLM / NLP** | OpenAI gpt-3.5-turbo | Cheap, fast, reliable for the RAG summarization24. |
| **Embeddings** | SentenceTransformers | Free local embedding (huggingface) to save API costs. |
| **Dashboard** | Streamlit | Zero HTML/CSS required; builds dashboard in minutes25. |
| **Orchestration** | Docker Compose | Spin up the whole stack with one command. |

---

## **6\. Implementation Roadmap (24-Hour Plan)**

1. **Hours 0-4: The Pipeline**  
   * Set up Docker Compose (Redpanda, ChromaDB).  
   * Write producer.py (reads a dummy log file and pushes to Kafka)26.  
2. **Hours 4-10: The Intelligence**  
   * Write processor.py. Implement the Windowing logic manually (Python list buffers) or using Pandas.  
   * Implement basic "Spike Detection" (if count \> threshold)27.  
3. **Hours 10-16: The RAG**  
   * Build the indexer.py to ingest 3 sample PDF runbooks.  
   * Connect the processor to query ChromaDB when a spike is detected28.  
4. **Hours 16-20: The UI**  
   * Build Streamlit app to read from a "Processed" topic or local SQLite DB.  
   * Display the alerts and the retrieved runbook text29.  
5. **Hours 20-24: Polish**  
   * Refine the "Mock Data" to ensure it triggers the demo scenarios perfectly.  
   * Add PII masking logic30.

---

## **7\. Future/Production Considerations (Post-Hackathon)**

* **Scalability:** Replace Python consumer with Apache Flink for true distributed windowing31.  
* **Storage:** Implement a Data Lake (S3) for long-term log retention (Archival)32.  
* **Auto-Remediation:** Allow the system to trigger Ansible/Terraform scripts directly33.

### **Suggested Next Step**

The SRS specifically asks: **"Would you like me to create a Python simulation code for the 'Tumbling Window' statistical analysis part of this SRS?"**34343434.

Given that this is the core logic for the anomaly detection engine, would you like me to generate that simulation code now so you can use it for the "Processing Layer"?

