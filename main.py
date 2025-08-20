import datetime
import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- Configuration ---
# !! IMPORTANT !! Paste your credentials here
YOUR_CLIENT_ID = "PASTE_YOUR_CLIENT_ID_HERE"
YOUR_CLIENT_SECRET = "PASTE_YOUR_CLIENT_SECRET_HERE"
    
# This is the last working URL for your frontend.
REDIRECT_URI = "https://korima-frontend-9cqci0rvr-arturos-projects-6e387ff6.vercel.app"

# The scope tells Google what permissions we want.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# This will hold the user's credentials after they log in.
user_credentials = None

# --- Initialize Database & App ---
db = firestore.Client(project="korima-backend")
app = FastAPI(title="Kórima v3.0 - Calendar Enabled")
    
# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[REDIRECT_URI], # Only allow our frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Brain Functions (API Endpoints) ---

@app.get("/")
def read_root():
    return {"message": "Hola, soy el cerebro de Kórima v3.0. Estoy listo para conectar con tu calendario."}

@app.get("/api/auth/google")
def auth_google():
    """Starts the Google authentication flow."""
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": YOUR_CLIENT_ID,
                "client_secret": YOUR_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return {"authorization_url": authorization_url}

@app.get("/api/auth/google/callback")
async def auth_google_callback(request: Request):
    """Handles the response from Google after the user authenticates."""
    global user_credentials
    state = request.query_params.get('state')
    code = request.query_params.get('code')

    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": YOUR_CLIENT_ID,
                "client_secret": YOUR_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=code)
    
    # Store the credentials
    creds = flow.credentials
    user_credentials = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    
    # Redirect the user back to the main app page
    return RedirectResponse(url=REDIRECT_URI)


@app.get("/api/daily-briefing")
def get_daily_briefing():
    """Fetches REAL events from the user's Google Calendar."""
    global user_credentials
    if not user_credentials:
        return {"error": "User not authenticated. Please log in."}

    try:
        creds = Credentials(**user_credentials)
        service = build('calendar', 'v3', credentials=creds)

        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=now,
            maxResults=5, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return {"focus": {"description": "No tienes próximos eventos en tu calendario."}}

        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            event_list.append(f"Event: {event['summary']} at {start}")

        return {"focus": {"description": "Tus próximos eventos son:", "events": event_list}}

    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": "Could not retrieve calendar events."}
