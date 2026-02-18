/**
 * Application Configuration
 * 
 * wichtige URLs en instellingen voor het AI Bureau systeem
 * Deze file wordt gebruikt door zowel frontend als backend
 */

export const CONFIG = {
  // ===== API Endpoints =====
  api: {
    // Backend API URL
    baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8090',
    
    // API endpoints
    endpoints: {
      // Crew endpoints
      crew: '/api/crew',
      crewList: '/api/crew',
      crewCreate: '/api/crew',
      crewUpdate: (id) => `/api/crew/${id}`,
      crewDelete: (id) => `/api/crew/${id}`,
      
      // Project endpoints
      projects: '/api/projects',
      projectCreate: '/api/projects',
      projectList: '/api/projects',
      projectDetail: (id) => `/api/projects/${id}`,
      projectUpdate: (id) => `/api/projects/${id}`,
      projectDelete: (id) => `/api/projects/${id}`,
      
      // Job endpoints
      jobs: '/jobs',
      jobCreate: '/jobs',
      jobDetail: (id) => `/jobs/${id}`,
      jobAnswer: (id) => `/jobs/${id}/answer`,
      jobApprovePlan: (id) => `/jobs/${id}/approve-plan`,
      jobRequestChanges: (id) => `/jobs/${id}/request-changes`,
      jobFeedback: (id) => `/jobs/${id}/feedback`,
      jobApprove: (id) => `/jobs/${id}/approve`,
      
      // Task endpoints
      task: '/api/task',
      taskCreate: '/api/task',
      
      // Unified products
      unifiedProducts: '/api/unified-products',
    }
  },

  // ===== Application URLs =====
  app: {
    // Frontend URLs
    frontend: import.meta.env.VITE_FRONTEND_URL || 'http://localhost:5173',
    
    // Pages
    pages: {
      home: '/',
      dashboard: '/dashboard',
      crew: '/crew',
      projects: '/projects',
      createProject: '/projects/new',
      projectDetail: (id) => `/projects/${id}`,
      jobs: '/jobs',
      jobDetail: (id) => `/jobs/${id}`,
      settings: '/settings',
    },
    
    // External services
    docs: 'https://github.com/timo-dev/ai-bureau',
    github: 'https://github.com/timo-dev/ai-bureau',
  },

  // ===== External Services =====
  external: {
    // Supabase Database
    supabase: {
      url: 'https://db.cqasccazioqjodctawzx.supabase.co',
      host: 'db.cqasccazioqjodctawzx.supabase.co',
      port: 5432,
      database: 'postgres',
    },
    
    // Vercel Deployment
    vercel: {
      frontend: 'https://wonderz-agentics.vercel.app',
      apiProd: 'http://localhost:8090',
    },
    
    // Fly.io Deployment
    flyio: {
      api: 'http://localhost:8090',
    },
  },

  // ===== Development Settings =====
  dev: {
    // Enable debug logging
    debugMode: import.meta.env.VITE_DEBUG === 'true',
    
    // Mock API responses (for development)
    useMock: import.meta.env.VITE_USE_MOCK === 'true',
    
    // Log all API calls
    logApiCalls: import.meta.env.VITE_LOG_API === 'true',
  },

  // ===== Features =====
  features: {
    // Enable WebSocket support
    enableWebSocket: true,
    
    // Enable real-time updates
    enableRealtime: true,
    
    // Enable offline mode
    enableOffline: false,
  },

  // ===== Timeouts & Limits =====
  limits: {
    // API timeout in milliseconds
    apiTimeout: 30000,
    
    // Max file upload size in MB
    maxFileSize: 50,
    
    // Max project description length
    maxDescriptionLength: 5000,
    
    // Max crew size
    maxCrewSize: 10,
  },

  // ===== Helper function to get full API URL =====
  getApiUrl(endpoint) {
    return `${this.api.baseUrl}${endpoint}`;
  },

  // ===== Helper function to get full app URL =====
  getAppUrl(path) {
    return `${this.app.frontend}${path}`;
  },
};

export default CONFIG;
