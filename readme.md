# 🏥 Intelligent Cloud-Based Healthcare Data Management System

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-412991?style=for-the-badge&logo=openai&logoColor=white)
![JWT](https://img.shields.io/badge/Auth-JWT-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white)
![License](https://img.shields.io/badge/License-Academic-green?style=for-the-badge)

> A scalable, secure, and AI-powered backend system for intelligent healthcare data management — built as part of an M.Tech research project.

---

## 📌 Overview

This backend system provides RESTful APIs for managing patients, doctors, medical records, and appointments — enriched with **AI-based disease prediction** and **NLP-powered medical report analysis**.

Designed as part of an **M.Tech research project**, the system explores the intersection of:
- Cloud-based healthcare data management
- Conversational AI over medical records
- AI-assisted medical document analysis

---

## 🚀 Features

### 👤 User Management
- Secure authentication and authorization using **JWT**
- Role-based access control (RBAC)
- Supported roles: **Admin**, **Doctor**, **Patient**

### 🧑‍⚕️ Patient Profile Management
- Create and manage patient profiles
- Store demographic and medical information

### 📅 Appointment Management
- Patients can book appointments with doctors
- Appointment status tracking and history

### 📋 Medical Record Management
- Secure storage and retrieval of patient medical records
- Authorized access updates only

### 📄 Medical Report Upload
- Upload medical reports (PDF / documents)
- Reports stored and linked with patient records

### 🤖 AI-Based Disease Prediction
- Uses a pretrained ML model
- Predicts diseases based on patient symptoms
- Supports healthcare analytics dashboards

### 🧠 NLP-Based Medical Report Analysis
Uploaded reports are analyzed using NLP techniques:
- **Text Summarization**
- **Keyword Extraction**
- **Named Entity Recognition (NER)**

### 💬 LLM-Based Question Answering
Users can ask natural language questions about uploaded reports:

```
Question: What is the patient's blood pressure?
Answer:   The blood pressure recorded in the report is 120/80 mmHg.
```

### 🗂️ Audit Logging
- Tracks all important system activities
- Logs access and modifications for security and compliance

### 🔒 Access Control
- Fine-grained permission management
- Ensures secure and compliant data access

---

## 🏗️ System Architecture

```
┌──────────────────────────┐
│     Client Applications  │
│  (Web / Mobile / API)    │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│     FastAPI Backend      │
│   (REST API Layer)       │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   Business Logic Layer   │
│   (Services / Utils)     │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│    AI / NLP Modules      │
│        OpenAI│
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       Database           │
│  PostgreSQL + SQLAlchemy │
└──────────────────────────┘
```

**Tech Stack:**

| Layer | Technology |
|---|---|
| Web Framework | FastAPI |
| Language | Python 3.10+ |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Schema Validation | Pydantic |
| AI / NLP | OpenAI |
| Authentication | JWT (JSON Web Tokens) |

---

## 📂 Project Structure

```
backend/
│
├── app/
│   ├── api/            # API routers and endpoints
│   ├── core/           # Configuration and security
│   ├── models/         # SQLAlchemy database models
│   ├── schemas/        # Pydantic request/response schemas
│   ├── services/       # Business logic layer
│   ├── utils/          # Utility and helper functions
│   └── main.py         # FastAPI application entry point
│
├── requirements.txt    # Python dependencies
├── README.md
└── .env                # Environment variables (not committed)
```

---

## 🗄️ Database Schema

| Table | Description |
|---|---|
| `user` | User authentication and role information |
| `patient_profile` | Patient demographic and medical data |
| `appointment` | Appointment scheduling and tracking |
| `medical_record` | Patient medical records |
| `report_upload` | Uploaded medical report files |
| `nlp_analysis` | NLP analysis results for reports |
| `ai_prediction` | Disease prediction results |
| `disease_trend` | Disease prediction analytics data |
| `audit_log` | System activity and access logs |
| `access_control` | Fine-grained permission management |

---

## ⚙️ Installation

### Prerequisites
- Python 3.10+
- PostgreSQL
- pip

### 1. Clone the Repository

```bash
git clone https://github.com/kunalraut666/healthcare_backend.git
cd healthcare-backend
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate:

```bash
# Linux / Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/healthcare_db
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-model
```

---

## ▶️ Running the Application

Start the FastAPI development server:

```bash
uvicorn app.main:app --reload
```

| Endpoint | URL |
|---|---|
| API Base URL | `http://127.0.0.1:8000` |
| Swagger UI Docs | `http://127.0.0.1:8000/docs` |
| ReDoc Documentation | `http://127.0.0.1:8000/redoc` |

---

## 🔐 Authentication

The system uses **JWT-based authentication**.

**Workflow:**
1. User logs in with credentials
2. Server returns a signed JWT token
3. Token is included in the `Authorization` header for all protected requests

**Example Header:**

```
Authorization: Bearer <JWT_TOKEN>
```

---

## 📊 AI & NLP Components

### 🔬 Disease Prediction

```
POST /predict/disease
```

- **Input:** List of symptoms
- **Output:** Predicted disease with confidence score

### 📝 NLP Report Analysis

```
POST /report/analyze
```

- Report summarization
- Keyword extraction
- Named entity recognition (medications, diagnoses, lab values)

### 💬 Question Answering

```
POST /report/ask-question
```

Ask natural language questions about any uploaded medical report.

---

## 🛡️ Security

- ✅ JWT Authentication
- ✅ Role-based access control (RBAC)
- ✅ Audit logging for compliance
- ✅ Secure API endpoints
- ✅ Data access restrictions per role

---

## 📈 Future Enhancements

- [ ] Integration with Hospital Management Systems (HMS)
- [ ] Real-time health monitoring via WebSockets
- [ ] Advanced AI diagnostics engine
- [ ] Cloud deployment (AWS / Azure / GCP)
- [ ] Vector search for semantic medical document retrieval
- [ ] FHIR compliance for healthcare interoperability

---

## 🎓 Academic Context

This project is developed as part of an **M.Tech research project** focusing on:

- Intelligent Healthcare Data Systems
- Cloud-based Medical Data Management
- Conversational AI in Healthcare
- AI-assisted Medical Document Analysis

---

## 👨‍💻 Author

**M.Tech Student**  
Department of Computer Science  

**Project Title:**  
*Intelligent Cloud-Based Healthcare Data Management System*

---

## 📜 License

This project is intended for **academic and research purposes only**.  
All rights reserved © 2024.