from fastapi import FastAPI
from app.core.database import Base, engine
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import os
# Routers import with clear aliases (avoid conflict with models/schemas)
from app.routers import (
    auth as auth_router,
    access_control as access_control_router,
    ai_prediction as ai_prediction_router,
    appointment as appointment_router,
    audit_log as audit_log_router,
    disease_trend as disease_trend_router,
    medical_record as medical_record_router,
    nlp_analysis as nlp_analysis_router,
    patient_profile as patient_profile_router,
    report_upload as report_upload_router,
    report_qa as report_qa_router,
    nlp_runtime as nlp_runtime_router,
    doctor_patients as doctor_patients_router,
    notifications as notifications_router
)
from fastapi.staticfiles import StaticFiles


# Create FastAPI app
app = FastAPI()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
print("[UPLOAD_DIR]", settings.UPLOAD_DIR)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


origins = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all database tables
Base.metadata.create_all(bind=engine)

# Register routers
app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
app.include_router(doctor_patients_router.router, prefix="/doctor", tags=["doctor"])
app.include_router(access_control_router.router, prefix="/access-control", tags=["Access Control"])
app.include_router(ai_prediction_router.router, prefix="/ai-prediction", tags=["AI Prediction"])
app.include_router(appointment_router.router, prefix="/appointments", tags=["Appointments"])
app.include_router(audit_log_router.router, prefix="/audit-log", tags=["Audit Log"])
app.include_router(disease_trend_router.router, prefix="/disease-trends", tags=["Disease Trends"])
app.include_router(medical_record_router.router, prefix="/medical-records", tags=["Medical Records"])
app.include_router(nlp_analysis_router.router, prefix="/nlp-analysis", tags=["NLP (Patient)"])
app.include_router(nlp_runtime_router.router, prefix="/nlp", tags=["NLP (Runtime)"])
app.include_router(patient_profile_router.router, prefix="/patient-profiles", tags=["Patient Profiles"])
app.include_router(report_upload_router.router, prefix="/report-upload", tags=["Report Upload"])
app.include_router(report_qa_router.router, prefix="/report-qa", tags=["Report Question Answering"])
app.include_router(notifications_router.router, prefix="/notifications", tags=["Notifications"])  
# 
# Root endpoint
@app.get("/")
def root():
    return {"msg": "Welcome to Healthcare API"}
