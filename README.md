# ARGOS OSINT - Local Optimized Version

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation & Run
```powershell
# Start the server
.\START.ps1
```

### Access Points
- **Main UI**: http://localhost:8000/ui/
- **API Docs**: http://localhost:8000/docs
- **Routes**: http://localhost:8000/__routes

## 🎯 Features

### Core OSINT Functions
- **Email OSINT**: Email analysis and verification
- **Username Search**: Social media username discovery
- **Person Search**: Find people by name
- **Advanced Scan**: Full comprehensive analysis

### Supported Platforms
- Instagram
- GitHub
- Twitter/X
- Reddit
- YouTube
- Facebook
- LinkedIn

## 🔧 Configuration

### Environment Variables
Create `.env` file with your API keys:
```
EMAILREP_KEY=your_emailrep_key
HUNTER_KEY=your_hunter_key
HIBP_KEY=your_hibp_key
SELF_BASE_URL=http://localhost:8000
IG_USER_AGENT=your_user_agent
```

## 📁 Project Structure
```
├── app/
│   ├── routers/          # API endpoints
│   ├── services/         # Core services
│   ├── utils/            # Utilities
│   └── main.py           # FastAPI app
├── ui/
│   └── index.html        # Modern UI
├── requirements.txt      # Dependencies
└── START.ps1            # Startup script
```

## 🛠️ Development

### Adding New Features
1. Create router in `app/routers/`
2. Add service in `app/services/`
3. Update UI in `ui/index.html`

### API Endpoints
- `/mosint/full` - Email OSINT
- `/username-bios` - Username search
- `/hunt-x-by-name` - Person search
- `/scan/full` - Advanced scan

## 🔒 Security
- API keys are stored in environment variables
- Session management handled securely
- No sensitive data in code

## 📊 Performance
- Optimized for local development
- FastAPI with async support
- Caching enabled
- No Docker overhead

## 🐛 Troubleshooting

### Common Issues
1. **Port 8000 in use**: Change port in START.ps1
2. **API keys missing**: Check .env file
3. **UI not loading**: Hard refresh (CTRL+F5)

### Logs
- Server logs in terminal
- Error logs in `logs/` directory

## 📝 License
Private project - All rights reserved