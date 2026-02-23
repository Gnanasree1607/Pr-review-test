import os
import logging
from datetime import datetime, timedelta
import pytz
import pickle

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ---------------------------------------------------
# LOGGING
# ---------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------
# ENV VARIABLES
# ---------------------------------------------------
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    raise ValueError("❌ SLACK TOKENS NOT SET")

# ---------------------------------------------------
# SLACK APP
# ---------------------------------------------------
app = App(token=SLACK_BOT_TOKEN)

# ---------------------------------------------------
# GOOGLE CALENDAR
# ---------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"

def get_calendar_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return build("calendar", "v3", credentials=creds)

calendar_service = get_calendar_service()

IST = pytz.timezone("Asia/Kolkata")

# ---------------------------------------------------
# SLASH COMMAND
# ---------------------------------------------------
@app.command("/pr-review")
def open_modal(ack, body, client):
    ack()

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "schedule_pr",
            "title": {"type": "plain_text", "text": "PR Review Scheduler"},
            "submit": {"type": "plain_text", "text": "Schedule"},
            "blocks": [

                {
                    "type": "input",
                    "block_id": "pr_block",
                    "label": {"type": "plain_text", "text": "PR Title"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "pr_title",
                    },
                },

                {
                    "type": "input",
                    "block_id": "team_block",
                    "label": {"type": "plain_text", "text": "Select Team"},
                    "element": {
                        "type": "static_select",
                        "action_id": "team",
                        "options": [
                            {"text": {"type": "plain_text", "text": "Backend"}, "value": "backend"},
                            {"text": {"type": "plain_text", "text": "Frontend"}, "value": "frontend"},
                            {"text":{"type":  "plain_text", "text": "Security"}, "value": "security"},
                        ],
                    },
                },

                # DAY SELECT
                {
                    "type": "input",
                    "block_id": "day_block",
                    "label": {"type": "plain_text", "text": "Select Day"},
                    "element": {
                        "type": "static_select",
                        "action_id": "day",
                        "options": [
                            {"text": {"type": "plain_text", "text": "Today"}, "value": "today"},
                            {"text": {"type": "plain_text", "text": "Tomorrow"}, "value": "tomorrow"},
                        ],
                    },
                },

                # TIME SELECT
                {
                    "type": "input",
                    "block_id": "time_block",
                    "label": {"type": "plain_text", "text": "Select Time"},
                    "element": {
                        "type": "static_select",
                        "action_id": "time",
                        "options": [
                            {"text": {"type": "plain_text", "text": "10:00 AM"}, "value": "10:00"},
                            {"text": {"type": "plain_text", "text": "12:00 PM"}, "value": "12:00"},
                            {"text": {"type": "plain_text", "text": "02:00 PM"}, "value": "14:00"},
                            {"text": {"type": "plain_text", "text": "04:00 PM"}, "value": "16:00"},
                        ],
                    },
                },

                {
                    "type": "input",
                    "block_id": "reviewer_block",
                    "label": {"type": "plain_text", "text": "Select Reviewer"},
                    "element": {
                        "type": "users_select",
                        "action_id": "reviewer"
                    },
                },

                {
                    "type": "input",
                    "block_id": "duration_block",
                    "label": {"type": "plain_text", "text": "Duration"},
                    "element": {
                        "type": "static_select",
                        "action_id": "duration",
                        "options": [
                            {"text": {"type": "plain_text", "text": "30 mins"}, "value": "30"},
                            {"text": {"type": "plain_text", "text": "60 mins"}, "value": "60"},
                        ],
                    },
                },
            ],
        },
    )

# ---------------------------------------------------
# HANDLE SUBMISSION
# ---------------------------------------------------
@app.view("schedule_pr")
def handle_schedule(ack, body, client):
    ack()

    try:
        values = body["view"]["state"]["values"]

        pr_title = values["pr_block"]["pr_title"]["value"]
        team = values["team_block"]["team"]["selected_option"]["value"]
        duration = int(values["duration_block"]["duration"]["selected_option"]["value"])

        selected_day = values["day_block"]["day"]["selected_option"]["value"]
        selected_time = values["time_block"]["time"]["selected_option"]["value"]

        reviewer_slack_id = values["reviewer_block"]["reviewer"]["selected_user"]

        user_info = client.users_info(user=reviewer_slack_id)

        reviewer_name = user_info["user"]["real_name"]
        reviewer_email = user_info["user"]["profile"].get("email")

        if not reviewer_email:
            raise Exception("Add users:read.email scope in Slack.")

        # CREATE DATE TIME
        now_ist = datetime.now(IST)

        if selected_day == "tomorrow":
            now_ist = now_ist + timedelta(days=1)

        hour, minute = map(int, selected_time.split(":"))

        start_ist = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
        start_utc = start_ist.astimezone(pytz.utc)
        end_utc = start_utc + timedelta(minutes=duration)

        event = {
            "summary": f"PR Review: {pr_title}",
            "description": f"Automated PR Review for {team}",
            "start": {"dateTime": start_utc.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_utc.isoformat(), "timeZone": "UTC"},
            "attendees": [
                {"email": reviewer_email},
                {"email": "gnanasree.gundluri@gmail.com"}
            ],
        }

        created_event = calendar_service.events().insert(
            calendarId="primary",
            body=event,
            sendUpdates="all"
        ).execute()

        event_link = created_event.get("htmlLink")

        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f"🎉 PR Scheduled with {reviewer_name}\n📅 {event_link}"
        )

    except Exception as e:
        logger.error(str(e))
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f"❌ Scheduling Failed: {str(e)}"
        )

# ---------------------------------------------------
# START BOT
# ---------------------------------------------------
if __name__ == "__main__":
    logger.info("🚀 Starting PR Review Scheduler")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

