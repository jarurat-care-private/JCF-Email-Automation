import csv
import time
import requests

from requests.auth import HTTPBasicAuth
from postmarker.core import PostmarkClient
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

import os

# =========================================
# LOAD ENV
# =========================================

load_dotenv(".env")

# =========================================
# CAMPAIGN SCHEDULE
# =========================================

CAMPAIGNS = [
    {
        "time": "18:30",
        "template": "registered-doctors-1"
    },
    {
        "time": "19:00",
        "template": "registered-doctors-2"
    },
    {
        "time": "19:30",
        "template": "registered-doctors-3"
    },
    {
        "time": "20:00",
        "template": "registered-doctors-4"
    }
]

# =========================================
# CONFIG
# =========================================

BATCH_SIZE = 40
WAIT_TIME = 9

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
)



# =========================================
# INTERNAL TEST EMAILS
# =========================================

EXTRA_USERS = [

    {
        "email": "shreyatiwari6995@gmail.com",
        "first_name": "Shreya"
    },

    {
        "email": "jaruratcare@gmail.com",
        "first_name": "Jarurat"
    },

    {
        "email": "joshipriyanka97.pj@gmail.com",
        "first_name": "Priyanka"
    },

    {
        "email": "ap24btb0a04@student.nitw.ac.in",
        "first_name": "Pranav"
    }

]

# =========================================
# LOGGING
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
        "campaign_logs.txt",
        "a",
        encoding="utf-8"
    ) as log_file:

        log_file.write(
            log_message + "\n"
        )

# =========================================
# INIT POSTMARK
# =========================================

postmark = PostmarkClient(
    server_token=SERVER_API_TOKEN
)

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

    return response.json()[
        "access_token"
    ]

# =========================================
# GET ZOOM REGISTRANTS
# =========================================

def get_zoom_registrants():

    users = []

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
            f"Bearer {ZOOM_ACCESS_TOKEN}"
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

        write_log(
            f"Fetched {len(registrants)} registrants"
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

            if not email:
                continue

            users.append({

                "email":
                email,

                "first_name":
                user.get(
                    "first_name",
                    ""
                ).strip(),

                "last_name":
                user.get(
                    "last_name",
                    ""
                ).strip()

            })

        next_page_token = data.get(
            "next_page_token",
            ""
        )

        if not next_page_token:
            break

    return users

# =========================================
# START
# =========================================

write_log(
    "Generating Zoom token..."
)

ZOOM_ACCESS_TOKEN = (
    generate_zoom_token()
)

write_log(
    "Zoom token generated successfully"
)

# =========================================
# SELECT CAMPAIGN BASED ON TIME
# =========================================

current_campaign = None

ist = timezone(timedelta(hours=5, minutes=30))
now = datetime.now(ist).replace(tzinfo=None)

for campaign in CAMPAIGNS:

    scheduled = datetime.combine(
        now.date(),
        datetime.strptime(
            campaign["time"],
            "%H:%M"
        ).time()
    )

    diff_minutes = (
        now - scheduled
    ).total_seconds() / 60

    if 0 <= diff_minutes <= 2:

        current_campaign = campaign

        break

if current_campaign is None:

    write_log(
        "No campaign scheduled right now."
    )

    exit()

TEMPLATE_ALIAS = current_campaign[
    "template"
]

write_log(
    f"Selected template: "
    f"{TEMPLATE_ALIAS}"
)
# =========================================
# FETCH REGISTRANTS
# =========================================

users = get_zoom_registrants()

write_log(
    f"Total registrants fetched: "
    f"{len(users)}"
)

# =========================================
# REMOVE DUPLICATES
# =========================================

unique_users = []
seen_emails = set()

for user in users:

    email = user[
        "email"
    ]

    if email in seen_emails:

        write_log(
            f"Duplicate skipped: "
            f"{email}"
        )

        continue

    seen_emails.add(
        email
    )

    unique_users.append(
        user
    )

users = unique_users

write_log(
    f"Unique registrants: "
    f"{len(users)}"
)

# =========================================
# EXPORT USERS
# =========================================

with open(
    "users_to_email.csv",
    "w",
    newline="",
    encoding="utf-8"
) as output_file:

    writer = csv.DictWriter(
        output_file,
        fieldnames=[
            "email",
            "first_name",
            "last_name"
        ]
    )

    writer.writeheader()

    writer.writerows(
        users
    )

write_log(
    "users_to_email.csv exported"
)

# =========================================
# SEND EMAILS
# =========================================

failed_emails = []

for i in range(
    0,
    len(users),
    BATCH_SIZE
):

    batch = users[
        i:i + BATCH_SIZE
    ]

    batch_with_extra = (
        batch +
        EXTRA_USERS
    )

    batch_no = (
        i // BATCH_SIZE
    ) + 1

    write_log(
        f"STARTING BATCH {batch_no}"
    )

    write_log(
        f"Batch size: {len(batch)}"
    )

    for user in batch_with_extra:

        try:

            write_log(
                f"START -> {user['email']}"
            )

            # postmark.emails.send_with_template(

            #     From=SENDER_EMAIL,

            #     To=user[
            #         "email"
            #     ],

            #     TemplateAlias=
            #     TEMPLATE_ALIAS,

            #     TemplateModel={

            #         "Name":
            #         user.get(
            #             "first_name",
            #             ""
            #         ),

            #         "FullName":
            #         (
            #             f"{user.get('first_name','')} "
            #             f"{user.get('last_name','')}"
            #         ).strip()

            #     }

            # )

            write_log(
                f"DONE -> {user['email']}"
            )

        except Exception as e:

            write_log(
                f"FAILED -> "
                f"{user['email']} | "
                f"{e}"
            )

            failed_emails.append({

                "email":
                user["email"],

                "first_name":
                user.get(
                    "first_name",
                    ""
                ),

                "last_name":
                user.get(
                    "last_name",
                    ""
                ),

                "error":
                str(e)

            })

    write_log(
        f"BATCH {batch_no} COMPLETED"
    )

    if i + BATCH_SIZE < len(users):

        write_log(
            f"Sleeping for "
            f"{WAIT_TIME} seconds"
        )

        time.sleep(
            WAIT_TIME
        )

        write_log(
            "Sleep completed"
        )

# =========================================
# EXPORT FAILURES
# =========================================

if failed_emails:

    with open(
        "failed_emails.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as failed_file:

        writer = csv.DictWriter(
            failed_file,
            fieldnames=[
                "email",
                "first_name",
                "last_name",
                "error"
            ]
        )

        writer.writeheader()

        writer.writerows(
            failed_emails
        )

    write_log(
        "failed_emails.csv exported"
    )

# =========================================
# SUMMARY
# =========================================

write_log(
    "========== SUMMARY =========="
)

write_log(
    f"Total recipients: "
    f"{len(users)}"
)

write_log(
    f"Failed emails: "
    f"{len(failed_emails)}"
)

write_log(
    f"Successful emails: "
    f"{len(users) - len(failed_emails)}"
)

write_log(
    "============================"
)

write_log(
    "Campaign completed successfully"
)
