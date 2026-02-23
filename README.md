PR Review Scheduler Bot
An automated Slack bot that schedules Pull Request (PR) review meetings directly from Slack and creates Google Calendar events for reviewers.This project helps teams streamline PR review workflows and reduce manual coordination.
Features
Schedule PR review via /pr-review command
Select reviewer from Slack users
Choose date & time (IST supported)
Select meeting duration
Automatically sends Google Calendar invite
Sends event link back in Slack DM
Secure OAuth2 authentication
Tech Stack
Python
Slack Bolt (Socket Mode)
Google Calendar API
OAuth 2.0
pytz (Timezone handling)
