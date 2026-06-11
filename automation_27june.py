import csv
import time
import requests
import pandas as pd

from requests.auth import HTTPBasicAuth
from postmarker.core import PostmarkClient
from datetime import datetime, date, timedelta, timezone
from dotenv import load_dotenv

import os

# =========================================
# LOAD ENV
# =========================================

load_dotenv(".env.27june")

# =========================================
# LOG FUNCTION
# =========================================

def write_log(message):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    log_message = (
        f"[{timestamp}] {message}"
    )

    print(log_message)

    with open(
        "logs_27june.txt",
        "a",
        encoding="utf-8"
    ) as log_file:

        log_file.write(
            log_message + "\n"
        )

# =========================================
# TIMELINE GOOGLE SHEET
# =========================================

TIMELINE_FILE = (
    "https://docs.google.com/spreadsheets/d/"
    "1sOdQOqqiHz46VVeo4JVUkoy_5sj89VdTX18V2Et6W6g/"
    "export?format=csv&gid=1655275628"
)

# =========================================
# BATCH CONTROL
# =========================================

BATCH_SIZE = 95
WAIT_TIME = 300

# =========================================
# IMPORTANT EVENT DATES
# =========================================

EVENT_DAY = date(2026, 6, 27)

THANK_YOU_DAY = date(2026, 6, 28)

# =========================================
# ENV VARIABLES
# =========================================

SERVER_API_TOKEN = os.getenv(
    "SERVER_API_TOKEN"
)

SENDER_EMAIL = os.getenv(
    "SENDER_EMAIL"
)

ACCOUNT_ID = os.getenv(
    "ACCOUNT_ID"
)

CLIENT_ID = os.getenv(
    "CLIENT_ID"
)

CLIENT_SECRET = os.getenv(
    "CLIENT_SECRET"
)

ZOOM_MEETING_ID = os.getenv(
    "ZOOM_MEETING_ID"
).strip()

# =========================================
# INTERNAL TEST EMAIL
# =========================================

EXTRA_USERS = [

    {
        "email": "shreyatiwari6995@gmail.com",
        "first_name": "Shreya"}
    # },

    # {
    #     "email": "jaruratcare@gmail.com",
    #     "first_name": "Jarurat"
    # },

    # {
    #     "email": "joshipriyanka97.pj@gmail.com",
    #     "first_name": "Priyanka"
    # },

    # {
    #     "email": "ap24btb0a04@student.nitw.ac.in",
    #     "first_name": "Pranav"
    # }

]

# =========================================
# INIT POSTMARK
# =========================================

postmark = PostmarkClient(
    server_token=SERVER_API_TOKEN
)

# =========================================
# READ TIMELINE
# =========================================

timeline_df = pd.read_csv(
    TIMELINE_FILE
)

timeline_df.columns = (
    timeline_df.columns
    .str.strip()
)

# =========================================
# FIND CURRENT CAMPAIGN (IST + 15 MIN WINDOW)
# =========================================

timeline_df["combined_datetime"] = pd.to_datetime(
    timeline_df["Date"].astype(str)
    + " "
    + timeline_df["Time"].astype(str)
)

ist_timezone = timezone(
    timedelta(hours=5, minutes=30)
)

now = datetime.now(
    ist_timezone
).replace(tzinfo=None)

current_campaign = None

write_log(
    f"Current IST time: "
    f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
)

for _, row in timeline_df.iterrows():

    campaign_time = row["combined_datetime"]

    if (
        campaign_time.year == now.year
        and campaign_time.month == now.month
        and campaign_time.day == now.day
    ):

        time_difference_minutes = (
            now - campaign_time
        ).total_seconds() / 60.0

        if 0 <= time_difference_minutes <= 15:

            current_campaign = row

            write_log(
                f"Matched campaign scheduled at "
                f"{campaign_time.strftime('%H:%M')} "
                f"({round(time_difference_minutes,1)} minutes late)"
            )

            break
# =========================================
# AUTO EXIT FOR GITHUB ACTIONS
# =========================================

if current_campaign is None:

    write_log(
        "No campaign scheduled right now."
    )

    exit()

campaign = current_campaign

# =========================================
# CAMPAIGN DATA
# =========================================

SUBJECT_LINE = str(
    campaign.get(
        "Subject Line",
        ""
    )
).strip()

CSV_FILE = str(
    campaign.get(
        "Database Link",
        ""
    )
).strip()

raw_template_alias = campaign.get(
    "Template Alias",
    ""
)

if pd.isna(raw_template_alias):

    TEMPLATE_ALIAS = ""

else:

    TEMPLATE_ALIAS = str(
        raw_template_alias
    ).strip()

raw_email_body = campaign.get(
    "Email Full Body",
    ""
)

if pd.isna(raw_email_body):

    FULL_EMAIL_BODY = ""

else:

    FULL_EMAIL_BODY = str(
        raw_email_body
    ).strip()

campaign_date = pd.to_datetime(
    campaign["Date"]
).date()

write_log(
    f"Campaign loaded: "
    f"{SUBJECT_LINE}"
)

write_log(
    f"Using database: "
    f"{CSV_FILE}"
)

write_log(
    f"Using template alias: "
    f"{TEMPLATE_ALIAS}"
)

write_log(f"ACCOUNT_ID present: {bool(ACCOUNT_ID)}")
write_log(f"CLIENT_ID present: {bool(CLIENT_ID)}")
write_log(f"CLIENT_SECRET present: {bool(CLIENT_SECRET)}")
write_log(f"ZOOM_MEETING_ID present: {bool(ZOOM_MEETING_ID)}")

# =========================================
# GENERATE ZOOM TOKEN
# =========================================

def generate_zoom_token():

    token_url = (
        f"https://zoom.us/oauth/token"
        f"?grant_type=account_credentials"
        f"&account_id={ACCOUNT_ID}"
    )

    response = requests.post(

        token_url,

        auth=HTTPBasicAuth(
            CLIENT_ID,
            CLIENT_SECRET
        )
    )

    response.raise_for_status()

    token_data = response.json()

    access_token = token_data[
        "access_token"
    ]

    return access_token

ZOOM_ACCESS_TOKEN = (
    generate_zoom_token()
)

write_log(
    "Zoom token generated successfully"
)

# =========================================
# FETCH ZOOM REGISTRANTS
# =========================================

def get_zoom_registered_emails():

    registered_emails = set()

    next_page_token = ""

    while True:

        url = (
            f"https://api.zoom.us/v2/"
            f"meetings/"
            f"{ZOOM_MEETING_ID}/registrants"
        )

        params = {
            "page_size": 300
        }

        if next_page_token:

            params[
                "next_page_token"
            ] = next_page_token

        headers = {

            "Authorization":
            f"Bearer "
            f"{ZOOM_ACCESS_TOKEN}"

        }

        response = requests.get(

            url,

            headers=headers,

            params=params

        )

        response.raise_for_status()

        data = response.json()

        registrants = data.get(
            "registrants",
            []
        )

        for user in registrants:

            email = (

                user.get(
                    "email",
                    ""
                )

                .strip()
                .lower()

            )

            if email:

                registered_emails.add(
                    email
                )

        write_log(
            f"Fetched "
            f"{len(registrants)} "
            f"registrants"
        )

        next_page_token = data.get(
            "next_page_token",
            ""
        )

        if not next_page_token:

            break

    return registered_emails

# =========================================
# FETCH ZOOM ATTENDEES
# =========================================

def get_zoom_attendee_emails():

    attendee_emails = set()

    next_page_token = ""

    while True:

        url = (
            f"https://api.zoom.us/v2/"
            f"past_meetings/"
            f"{ZOOM_MEETING_ID}/participants"
        )

        params = {
            "page_size": 300
        }

        if next_page_token:

            params[
                "next_page_token"
            ] = next_page_token

        headers = {

            "Authorization":
            f"Bearer "
            f"{ZOOM_ACCESS_TOKEN}"

        }

        response = requests.get(

            url,

            headers=headers,

            params=params

        )

        response.raise_for_status()

        data = response.json()

        participants = data.get(
            "participants",
            []
        )

        for user in participants:

            email = (

                user.get(
                    "user_email",
                    ""
                )

                .strip()
                .lower()

            )

            if email:

                attendee_emails.add(
                    email
                )

        write_log(
            f"Fetched "
            f"{len(participants)} "
            f"participants"
        )

        next_page_token = data.get(
            "next_page_token",
            ""
        )

        if not next_page_token:

            break

    return attendee_emails

# =========================================
# GET REGISTRANTS
# =========================================

zoom_emails = (
    get_zoom_registered_emails()
)

write_log(
    f"Zoom registered users found: "
    f"{len(zoom_emails)}"
)

# =========================================
# GET ATTENDEES
# =========================================

attendee_emails = set()

if campaign_date == THANK_YOU_DAY:

    try:

        attendee_emails = (
            get_zoom_attendee_emails()
        )

        write_log(
            f"Zoom attendees found: "
            f"{len(attendee_emails)}"
        )

    except Exception as e:

        attendee_emails = set()

        write_log(
            f"Could not fetch attendees: "
            f"{e}"
        )

# =========================================
# READ USERS DATABASE
# =========================================

users_df = pd.read_csv(
    CSV_FILE
)

users_df.columns = (
    users_df.columns
    .str.strip()
)

reader = users_df.to_dict(
    orient="records"
)

users = []

failed_emails = []

seen_emails = set()

row_index = 0
duplicate_count = 0
registered_skip_count = 0
processed_count = 0

# =========================================
# EVENT DAY
# =========================================

if campaign_date == EVENT_DAY:

    for registered_email in zoom_emails:

        registered_email = (
            registered_email
            .strip()
            .lower()
        )

        if not registered_email:
            continue

        if registered_email in seen_emails:
            continue

        seen_emails.add(
            registered_email
        )

        users.append({

            "email":
            registered_email,

            "first_name":
            ""

        })

        write_log(
            f"Added registered user: "
            f"{registered_email}"
        )

# =========================================
# PROCESS DATABASE USERS
# =========================================

for row in reader:

    row_index += 1

    if row_index % 100 == 0:
        write_log(f"Processed rows: {row_index}")

    raw_email = row.get(
        "email"
    )

    if pd.isna(raw_email):
        continue

    email = str(
        raw_email
    ).strip().lower()

    if not email:
        continue

    if "@" not in email:
        continue

    if email in seen_emails:

        duplicate_count += 1

        write_log(
            f"Duplicate skipped: "
            f"{email}"
        )

        continue

    if campaign_date < EVENT_DAY:

        if email in zoom_emails:

            registered_skip_count += 1

            write_log(
                f"Skipped registered user: "
                f"{email}"
            )

            continue

    elif campaign_date == THANK_YOU_DAY:

        if not attendee_emails:

            write_log(
                "No attendee data found"
            )

            continue

        if email not in attendee_emails:

            write_log(
                f"Skipped non-attendee user: "
                f"{email}"
            )

            continue

    seen_emails.add(email)

    raw_name = row.get(
        "first_name"
    )

    first_name = (

        str(raw_name).strip()

        if raw_name
        and not pd.isna(raw_name)

        else ""

    )

    users.append({

        "email":
        email,

        "first_name":
        first_name

    })

write_log(
    f"Users to email: "
    f"{len(users)}"
)

write_log("Row processing completed")
write_log(f"Total rows: {row_index}")
write_log(f"Duplicates: {duplicate_count}")
write_log(f"Registered skips: {registered_skip_count}")

# =========================================
# EXPORT FILTERED USERS
# =========================================

with open(

    "users_to_email_27june.csv",

    mode="w",

    newline="",

    encoding="utf-8"

) as output_file:

    writer = csv.DictWriter(

        output_file,

        fieldnames=[
            "email",
            "first_name"
        ]

    )

    writer.writeheader()

    writer.writerows(
        users
    )

write_log(
    "Filtered users exported"
)

# =========================================
# SEND EMAILS
# =========================================

total_attempted = 0

for i in range(

    0,

    len(users),

    BATCH_SIZE

):

    batch = users[
        i:i + BATCH_SIZE
    ]

    # TEST MODE

    #batch_with_extra = EXTRA_USERS
    

    # LIVE MODE
    batch_with_extra = batch + EXTRA_USERS

    write_log(
        f"\nSending batch "
        f"{i // BATCH_SIZE + 1}"
    )

    for user in batch_with_extra:

        total_attempted += 1

        try:

            write_log(

                f"Sending mail to "
                f"{user['email']} | "
                f"Name='{user['first_name']}'"

            )

            # =========================================
            # TEMPLATE MODE
            # =========================================

            # if TEMPLATE_ALIAS:

            #     postmark.emails.send_with_template(

            #         From=SENDER_EMAIL,

            #         To=user["email"],

            #         TemplateAlias=
            #         TEMPLATE_ALIAS,

            #         TemplateModel={

            #             "Name":
            #             user["first_name"]

            #         }

            #     )

                

            write_log(
                f"Template email sent -> "
                f"{user['email']}"
            )

            # =========================================
            # CUSTOM EMAIL BODY MODE
            # =========================================

            # else:

            #     personalized_body = (

            #         FULL_EMAIL_BODY

            #         .replace(
            #             "[Name]",
            #             user["first_name"]
            #         )

            #         .replace(
            #             "{{Name}}",
            #             user["first_name"]
            #         )

            #     )

                # postmark.emails.send(

                #     From=SENDER_EMAIL,

                #     To=user["email"],

                #     Subject=SUBJECT_LINE,

                #     HtmlBody=
                #     personalized_body

                # )

                

                # write_log(
                #     f"Custom body email sent -> "
                #     f"{user['email']}"
                # )

        except Exception as e:

            write_log(
                f"Failed -> "
                f"{user['email']} | "
                f"{e}"
            )

            failed_emails.append({

                "email":
                user["email"],

                "first_name":
                user["first_name"],

                "error":
                str(e)

            })

    if i + BATCH_SIZE < len(users):

        write_log(
            "Waiting between batches..."
        )

        time.sleep(
            WAIT_TIME
        )

# =========================================
# EXPORT FAILED EMAILS
# =========================================

if failed_emails:

    with open(

        "failed_emails_27june.csv",

        mode="w",

        newline="",

        encoding="utf-8"

    ) as failed_file:

        writer = csv.DictWriter(

            failed_file,

            fieldnames=[
                "email",
                "first_name",
                "error"
            ]

        )

        writer.writeheader()

        writer.writerows(
            failed_emails
        )

    write_log(
        "Failed emails exported"
    )

# =========================================
# SUMMARY
# =========================================

write_log(
    "========== SUMMARY =========="
)

write_log(
    f"Total filtered users: "
    f"{len(users)}"
)

write_log(
    f"Actual attempts: "
    f"{total_attempted}"
)

write_log(
    f"Failed emails: "
    f"{len(failed_emails)}"
)

write_log(
    f"Successful emails: "
    f"{total_attempted - len(failed_emails)}"
)

write_log(
    "============================"
)

write_log(
    "Automation completed successfully"
)
