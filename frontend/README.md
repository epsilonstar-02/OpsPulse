# OpsPulse Frontend

A modern React dashboard for the OpsPulse AI monitoring system. This frontend connects to the OpsPulse backend API to display real-time logs, alerts, metrics, and system health.

## Features

- **Real-time Dashboard**: Live updates via WebSocket connection
- **Alerts Management**: View, acknowledge, and resolve system alerts
- **Service Monitoring**: Track service health and performance metrics
- **System Metrics**: CPU, memory, disk, and network monitoring
- **Responsive Design**: Works on desktop and mobile devices

## Prerequisites

- Node.js 18+ 
- OpsPulse Backend running on port 8001

## Getting Started

### 1. Install Dependencies

```bash
cd OpsPulse-frontend
npm install
```

### 2. Configure Environment (Optional)

Copy the example environment file:

```bash
cp .env.example .env
```

Environment variables:
- `VITE_API_URL`: Backend API URL (leave empty to use Vite proxy in development)
- `VITE_WS_URL`: WebSocket URL (leave empty to auto-detect)

### 3. Start the Backend

Make sure the OpsPulse backend is running:

```bash
cd ../OpsPulse/backend
pip install -r requirements.txt
python -m backend.main
# Backend runs on http://localhost:8001
```

### 4. Start the Frontend

```bash
npm run dev
# Frontend runs on http://localhost:3000
```

The Vite development server will proxy API and WebSocket requests to the backend automatically.

## Project Structure

```
src/
├── components/          # React components
│   ├── pages/          # Page components
│   ├── Dashboard.jsx   # Main dashboard layout
│   ├── Header.jsx      # Header with connection status
│   ├── Sidebar.jsx     # Navigation sidebar
│   └── ...
├── context/            # React context providers
│   └── DashboardContext.jsx  # Dashboard data provider
├── hooks/              # Custom React hooks
│   ├── useWebSocket.js       # WebSocket connection hook
│   └── useDashboardData.js   # Dashboard data management hook
├── services/           # API services
│   └── api.js          # Backend API client
└── App.jsx             # Root application component
```

## API Integration

The frontend connects to these backend endpoints:

### REST API
- `GET /api/analytics/overview` - Dashboard overview metrics
- `GET /api/analytics/services` - Service statistics
- `GET /api/logs/recent` - Recent log entries
- `GET /api/alerts/recent` - Recent alerts
- `GET /api/system/health` - System health status

### WebSocket
- `ws://localhost:8001/ws/live` - Real-time updates

Available WebSocket channels:
- `logs` - Real-time log entries
- `alerts` - Alert notifications
- `stats` - Statistics updates (every 5s)
- `health` - Health status changes
- `all` - All channels

## Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

## Technology Stack

- **React 19** - UI framework
- **Vite** - Build tool and dev server
- **Tailwind CSS 4** - Utility-first CSS
- **Recharts** - Charts and data visualization
- **Lucide React** - Icons
- **Framer Motion** - Animations
