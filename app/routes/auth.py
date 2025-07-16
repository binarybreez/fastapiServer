from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
import json
import logging
import os
from svix.webhooks import Webhook
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()


@router.post("/clerk/webhook")
async def handle_user_created(request: Request):
    webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    body = await request.body()
    try:
        payload = body.decode("utf-8")
        headers = dict(request.headers)
        webhook = Webhook(webhook_secret)
        webhook.verify(payload, headers)
        data = json.loads(payload)
        if data.get("type") != "user.created":
            return {"status": "ignored"}

        user_data = data.get("data", {})
        print(f"User created: {user_data}")
        user_id = user_data.get("id")
        if not user_id:
            raise HTTPException(
                status_code=400, detail="User ID not found in webhook data"
            )

    except Exception as e:
        logging.error(f"Webhook verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
