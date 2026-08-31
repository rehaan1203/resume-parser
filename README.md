# Friction Matcher

Friction Matcher is an advanced AI-augmented web application designed to analyze the "friction" between a candidate's resume and a specific Job Description (JD). It provides a highly detailed match score, identifies skill and seniority gaps, highlights strengths, and generates actionable, AI-driven advice (such as a career roadmap, ATS optimizations, and interview preparation).

## 🚀 Features

- **Deterministic Parsing:** Extracts exact years of experience, domain detection, and skill matching using structured logic before falling back to AI.
- **Comprehensive Match Scoring:** Evaluates candidates based on technical skills, soft skills, and seniority alignment.
- **AI-Powered Insights:** Uses Google Gemini (or Mistral) to generate executive summaries, ATS optimization tips, and personalized learning roadmaps.
- **Verified Resources:** An internal `LinkProcessor` validates AI-generated links to ensure candidates only receive functional YouTube and external resources.
- **Domain Guardrails:** Detects if a candidate is applying outside their industry and generates specialized "Career Change" roadmaps instantly.
- **High Performance:** Utilizes asynchronous Python, parallel AI generation, and Redis caching for lightning-fast responses.

## 🏗️ Architecture

The project is strictly separated into a client and server model to ensure scalability and clean separation of concerns.

### Frontend
- **Framework:** Next.js 14 (App Router)
- **UI Library:** React 18
- **Styling:** Tailwind CSS & Framer Motion
- **Language:** TypeScript

### Backend
- **Framework:** FastAPI
- **Data Validation:** Pydantic
- **AI Models:** Google Gemini (`gemini-2.5-flash`), Mistral (Supported Alternative)
- **Caching & Rate Limiting:** Redis
- **Language:** Python 3

## 🛠️ Getting Started

### Prerequisites
- Node.js (v18+)
- Python (3.9+)
- Redis Server (Optional but recommended for caching)
- API Keys: Google Gemini API Key (or Mistral API Key)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Or venv/bin/activate on Mac/Linux
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables:
   Copy `.env.example` to `.env` and fill in your `GOOGLE_API_KEY`.
5. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```
   *The API will be available at `http://localhost:8000`. Documentation is at `http://localhost:8000/docs`.*

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   *The application will be available at `http://localhost:3000`.*

## 🔒 Security & Limits

The application includes built-in rate limiting to prevent API abuse and excessive LLM costs. By default, it allows 10 requests per minute and 100 requests per day per IP address.

## 🤝 Contributing

When contributing to this repository, please ensure that any new LLM prompts follow the strict JSON schema enforced by Pydantic models in the backend to prevent frontend rendering errors.
