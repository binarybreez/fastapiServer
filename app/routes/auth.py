from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
import json
import logging
import os
from svix.webhooks import Webhook
from dotenv import load_dotenv
from app.db import db

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
        email = next((email["email_address"] for email in user_data.get("email_addresses", []) 
                    if email["id"] == user_data.get("primary_email_address_id")), None)
        print(f"User email: {email}")

        if not user_id or not email:
            raise HTTPException(
                status_code=400, 
                detail="Missing required user data"
            )

        # Create minimal user document
        user_doc = {
            "clerk_id": user_id,
            "email": email,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # Insert with conflict check
        existing_user = await db.users.find_one({"clerk_id": user_id})
        if existing_user:
            logging.info(f"User {user_id} already exists")
            return {"status": "exists"}

        await db.users.insert_one(user_doc)
        logging.info(f"Created skeleton user for {user_id}")
        return {"status": "success"}

    except Exception as e:
        logging.error(f"Webhook verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
