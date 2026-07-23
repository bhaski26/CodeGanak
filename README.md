# CodeGanak

> **Understand. Visualize. Engineer.**

CodeGanak is an AI-powered software engineering platform that helps developers understand unfamiliar codebases in minutes instead of days.

Rather than acting as a simple chatbot for code, CodeGanak builds a structured understanding of an entire repository by combining source code parsing, semantic analysis, knowledge representation, and AI-assisted reasoning. It enables developers to explore project architecture, inspect relationships between components, and interact with repositories using natural language.

---

## Why CodeGanak?

Modern software systems are large, distributed, and constantly evolving. Understanding an unfamiliar codebase is often one of the biggest challenges for developers during onboarding, maintenance, debugging, or feature development.

CodeGanak aims to reduce that learning curve by transforming repositories into searchable, explainable knowledge.

---

## Key Features

* Secure user authentication
* Workspace management
* Repository import

  * GitHub repositories
  * ZIP uploads
* Repository indexing
* AI-assisted repository understanding
* Interactive architecture visualization
* Dependency graph exploration
* Semantic repository search
* Extensible service-oriented architecture

---

## Technology Stack

### Frontend

* React
* TypeScript
* Tailwind CSS
* React Router
* TanStack Query
* Framer Motion
* React Flow
* Radix UI

### Backend

* FastAPI
* Python
* MongoDB
* JWT Authentication

### AI & Analysis

* Repository analysis services
* Extensible AI service layer
* Graph analysis foundation

### DevOps

* Docker
* Docker Compose
* GitHub Actions (planned)

---

## High-Level Architecture

```text
                +----------------------+
                |      Frontend        |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |     FastAPI API      |
                +----------+-----------+
                           |
      +---------+----------+----------+---------+
      |         |                     |         |
      v         v                     v         v
 Auth Service Repo Service      AI Service Graph Service
      |         |                     |         |
      +---------+----------+----------+---------+
                           |
                           v
                     MongoDB Database
```

---

## Repository Structure

```text
CodeGanak/
├── apps/
│   └── web/
├── backend/
├── components/
├── hooks/
├── services/
├── shared/
├── public/
├── docs/
└── ...
```

---

## Getting Started

### Clone the repository

```bash
git clone https://github.com/bhaski26/CodeGanak.git
cd CodeGanak
```

### Install dependencies

Follow the setup instructions for the frontend and backend as documented in the project.

### Configure environment variables

Create the required environment files and provide the necessary configuration values before starting the application.

### Run the project

Start the backend service, then launch the frontend development server.

---

## Project Status

CodeGanak is currently under active development.

The current focus is on:

* Building a robust engineering foundation
* Improving repository analysis
* Strengthening AI capabilities
* Creating comprehensive documentation
* Enhancing developer experience

---

## Roadmap

### Phase 1

* Project foundation
* Authentication
* Repository management
* Documentation

### Phase 2

* Repository parsing
* AI knowledge pipeline
* Semantic search

### Phase 3

* Architecture visualization
* Dependency analysis
* Repository insights

### Phase 4

* Performance optimization
* Production deployment
* Advanced AI capabilities

---

## Documentation

Detailed documentation is available in the `docs/` directory.

Topics include:

* Architecture
* System Design
* Backend
* Frontend
* AI Pipeline
* Parser
* Database
* Security
* Deployment
* Testing

---

## Vision

The long-term vision of CodeGanak is to become an intelligent software engineering companion that enables developers to understand, navigate, and reason about complex software systems with confidence.

---

## License

This project is currently intended for educational and portfolio purposes.
