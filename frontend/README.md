# Autonomous Competitive Intelligence Agent Network — Frontend

The frontend user interface for the Autonomous Competitive Intelligence Agent Network platform, built with **React 19**, **Vite**, **Tailwind CSS**, **Recharts**, and **Lucide React**.

---

## 🎨 Overview & UI Architecture

The frontend provides a dark-mode dashboard for monitoring competitor web snapshots, pricing shifts, sentiment analysis, multi-agent pipeline executions, interactive RAG AI chat, and intelligence reports.

```text
+----------------------------------------------------------------------------------+
|                            APP LAYOUT (Sidebar + Main)                           |
+----------------------------------------------------------------------------------+
|                                                                                  |
|  [Sidebar Navigation]                                                            |
|  - Dashboard Overview                                                            |
|  - Competitors List                                                              |
|  - Price Timelines                                                               |
|  - Sentiment Trends                                                              |
|  - Comparative Matrix                                                            |
|  - Intelligence Reports                                                          |
|  - User Profile & Settings                                                       |
|                                                                                  |
|  [Dashboard Controls & Actions]                                                  |
|  - Add / Edit Competitor Modal                                                   |
|  - Trigger Live Scrape & Agent Pipeline Run                                      |
|  - Real-Time Agent Execution Status Tracker                                      |
|  - RAG AI Assistant Chat Widget (Context-Bounded RAG + Attachments)             |
|                                                                                  |
+----------------------------------------------------------------------------------+
```

---

## ✨ Key Features & Components

- 📊 **Price History Timeline (`PriceTimelineChart.jsx`)**: Interactive Recharts line graph tracking historical price changes across competitor product tiers.
- 🎭 **Sentiment & Topic Analysis (`SentimentChart.jsx`)**: Visual breakdown of VADER sentiment scores (compound, positive, negative, neutral) and extracted key topic tags.
- 🧩 **Comparative Matrix (`ComparativeMatrix.jsx`)**: Side-by-side positioning grid comparing pricing tiers, features, sentiment rankings, and update frequencies across competitors.
- 📋 **Competitors Management (`CompetitorList.jsx`)**: Manage tracked companies, domains, scraping frequencies, and triggering on-demand scrapes/pipeline runs.
- 📑 **Intelligence Reports Hub (`ReportsPanel.jsx`)**: View generated reports, download HTML/PDF documents, and trigger Slack Webhook or Email deliveries.
- ⚡ **Agent Execution Modal (`AgentRunStatusModal.jsx`)**: Live status modal monitoring 4-node LangGraph pipeline progress (Researcher -> Change-Detector -> Sentiment-Analyst -> Report-Writer).
- 💬 **RAG AI Chat Widget (`ChatWidget.jsx`)**: Slide-over AI assistant supporting vector context retrieval, conversation memory, image attachments, and document/PDF uploads.
- 🔐 **Authentication & Security (`AuthContext.jsx` & `ProtectedRoute.jsx`)**: JWT bearer token authentication, auto-login persistence, and protected routing.

---

## 🛠️ Tech Stack & Libraries

| Dependency | Purpose |
| :--- | :--- |
| **React 19** | UI Component Library |
| **Vite** | Next-generation Frontend Tooling & Fast HMR |
| **Tailwind CSS** | Utility-first CSS Styling |
| **Recharts** | Responsive Charting Library |
| **Lucide React** | Modern Icon Suite |
| **Axios** | HTTP Client with Interceptors for JWT auth |
| **React Router DOM** | Client-side Routing |

---

## 📁 Directory Structure

```text
frontend/src/
├── api/
│   └── client.js             # Axios instance & API method bindings
├── components/
│   ├── AgentRunStatusModal.jsx# Live pipeline execution tracker
│   ├── ChatWidget.jsx        # RAG AI assistant chat drawer
│   ├── ComparativeMatrix.jsx # Competitor feature & price comparison table
│   ├── CompetitorList.jsx    # Tracked competitors CRUD list
│   ├── PriceTimelineChart.jsx# Recharts pricing history line graph
│   ├── ProtectedRoute.jsx    # Auth route guard
│   ├── ReportsPanel.jsx      # HTML/PDF report viewer & delivery actions
│   ├── SentimentChart.jsx    # Recharts sentiment visualization
│   └── Sidebar.jsx           # Dashboard navigation sidebar
├── contexts/
│   └── AuthContext.jsx       # User auth state provider
├── pages/
│   ├── DashboardPage.jsx     # Main multi-tab analytics dashboard
│   ├── LoginPage.jsx         # User login & registration page
│   └── ProfilePage.jsx       # User profile management
├── App.jsx                   # Main routes container
├── main.jsx                  # React application entry point
└── index.css                 # Global CSS & Tailwind imports
```

---

## 🚀 Setup & Local Development

### 1. Prerequisites
- Node.js 18+
- npm or pnpm

### 2. Installation
```bash
# Navigate to the frontend folder
cd frontend

# Install node dependencies
npm install
```

### 3. Environment Setup
Create a `.env` file in the `frontend` folder (or copy `.env.example` if available):
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 4. Run Development Server
```bash
npm run dev
```
The application will start at `http://localhost:5173`.

### 5. Production Build & Preview
```bash
# Build production assets to dist/
npm run build

# Preview production build locally
npm run preview
```

---

## 📄 License

Part of the **Autonomous Competitive Intelligence Agent Network**.
