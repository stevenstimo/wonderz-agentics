"""
Router registrations - imported by main.py
"""
from app.routes.agents import router as agents_router
from app.routes.hr import router as hr_router
from app.routes.training import router as training_router
from app.routes.crew import router as crew_router
from app.routes.monitoring import router as monitoring_router
from app.routes.status import router as status_router
from app.routes.talents import router as talents_router
from app.routes.skills import router as skills_router
from app.routes.settings import router as settings_router
from app.routes.ceo import router as ceo_router
from app.routes.explainer import router as explainer_router
from app.routes.intelligence import router as intelligence_router
from app.routes.alex_dev import router as alex_dev_router
from app.routes.debug_chat import router as debug_chat_router
from app.routes.skills_judson import router as judson_router


def register_routers(app):
    app.include_router(agents_router)
    app.include_router(hr_router)
    app.include_router(training_router)
    app.include_router(crew_router)
    app.include_router(monitoring_router)
    app.include_router(status_router)
    app.include_router(talents_router)
    app.include_router(judson_router)
    app.include_router(skills_router)
    app.include_router(settings_router)
    app.include_router(ceo_router)
    app.include_router(explainer_router)
    app.include_router(intelligence_router)
    app.include_router(alex_dev_router)
    app.include_router(debug_chat_router)
