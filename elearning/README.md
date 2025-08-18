# E-Learning Platform

High-performance e-learning platform with dual-layer Redis caching, real-time analytics, and JWT authentication.

## Features
- **90-95% performance improvements** with Redis caching strategy
- Real-time progress tracking and analytics
- JWT-based authentication system
- MongoDB with replica set configuration
- WebSocket support for live updates

## Documentation
Detailed documentation available in the [README](./README/) folder:
- [JWT Authentication](./README/JWT_AUTH_README.md)
- [MongoDB Schema](./README/MONGODB_SCHEMA_DOCUMENTATION.md)
- [Performance Analysis](./README/PERFORMANCE_ANALYSIS_README.md)
- [WebSockets](./README/WEBSOCKETS_README.md)
- [Redis](./README/REDIS_CACHING_STRATEGY_DOCUMENTATION.md)

## Quick Start

### Create Resources
```bash
cd elearning
./run_dev.sh
```

### Drop Resources
```bash
cd elearning
./drop_dev.sh
```

## Environment Variables

Create .env file in the root directory.
```env
MONGO_URI="mongodb://elearning-mongo:27017/elearning?replicaSet=rs0"
REDIS_URL=redis://redis:6379/0
JWT_SECRET=242f4bcc8055cac0028e9a838822c3d0257d44b9b7a5d36bb40bc07588285ea8
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## API Docs
```url
http://localhost:8000/docs
```

## Architecture
- **Backend**: FastAPI with async/await
- **Database**: MongoDB with replica set
- **Cache**: Redis with dual-layer strategy
- **Deployment**: Docker Compose
