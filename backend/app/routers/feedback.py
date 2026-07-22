import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_username_optional
from app.db import get_db

router = APIRouter()


class FeedbackIn(BaseModel):
    feedback_type: str
    related_page: str
    feedback_text: str
    contact_info: str = ""


class SurveyIn(BaseModel):
    q1_intuitive: int
    q2_useful: int
    q3_satisfied: int
    lacking_features: str = ""
    open_text: str = ""


@router.post("/feedback")
def submit_feedback(payload: FeedbackIn, username: str = Depends(get_current_username_optional)):
    if not payload.feedback_text.strip():
        raise HTTPException(status_code=400, detail="Please provide text feedback before submitting.")

    doc = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "user_name": username,
        "feedback_type": payload.feedback_type,
        "related_page": payload.related_page,
        "feedback_text": payload.feedback_text,
        "contact_info": payload.contact_info,
    }
    try:
        get_db()["feedback"].insert_one(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"saved": True}


@router.post("/survey")
def submit_survey(payload: SurveyIn, username: str = Depends(get_current_username_optional)):
    doc = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "user_name": username,
        "q1_intuitive": payload.q1_intuitive,
        "q2_useful": payload.q2_useful,
        "q3_satisfied": payload.q3_satisfied,
        "lacking_features": payload.lacking_features,
        "open_text": payload.open_text,
    }
    try:
        get_db()["surveys"].insert_one(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"saved": True}
