from flask import Flask, request, jsonify
from customThreads import PriorityThread
from dotenv import load_dotenv
import customMessages as cm
import ssl as ssl_lib
import urllib.parse
import threading
import psycopg2
import asyncio
import certifi
import slack
import json
import os

"""
    /nextp Workflow:
        1) User uses slash command to send information about the next priority issue to PriorityBot
        2) PriorityBot sends message to group chat
            Message contains:
                A. Info provided from the user
        3) PriorityBot sends message to user up for P1/P2 and asks for confirmation (2 minute Timeout)
            If confirmed,
                A. PriorityBot acknowledges user confirmation
                B. Sends message to group chat informing of the next person up for P1/P2
            If denied,
                A. PriorityBot acknowledges user rejection
                B. Repeat step 3
            If timeout,
                A. PriorityBot sends timeout message to user
                B. Repeat step 3
            If all users pinged,
                A. PriorityBot sends @here message to group chat about the priority issue
"""

app = Flask(__name__)

# Connect to Postgres Database
conn = psycopg2.connect(os.getenv('DATABASE_URL').replace("'",""))
conn.autocommit = True

# Load Slack Connection Information
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN").replace("'","")
SLACK_TOKEN = os.getenv("SLACK_TOKEN").replace("'","")
SSL_CONTEXT = ssl_lib.create_default_context(cafile=certifi.where())

# Create SlackClient in async mode
slackClient = slack.WebClient(
    token=SLACK_TOKEN, ssl=SSL_CONTEXT#, run_async=True, loop=LOOP
)

LOCK = threading.Lock()

@app.route("/nextp", methods=["POST"])
def nextp():
    """/nextp P1/P2 Ft. Worth cert issue. <@U4SCYHQUX|conzty01> connected but cannot see problem. Case #123123123"""

    print(request.values)

    print(request.form["token"])
    print(VERIFICATION_TOKEN)
    print(SLACK_TOKEN)
    print(request.form["token"] == VERIFICATION_TOKEN)

    # Verify that the message has come from slack
    if request.form["token"] == VERIFICATION_TOKEN:

        if request.form["command"] == '/nextp':

            rawText = request.form["text"]
            replyURL = request.form["response_url"]
            senderName = request.form["user_name"]
            channelID = request.form["channel_id"]
            senderId = request.form["user_id"]
            print(rawText,senderName,channelID,senderId)

            # Create a Priority Message
            message = cm.PriorityMessage(channelID, senderName, rawText)

            # Record the message in the Database
            cur = conn.cursor()

            cur.execute(f"SELECT id FROM slack_user WHERE slack_id = '{senderId}';")
            userId = cur.fetchone()[0]

            cur.execute(f"INSERT INTO priority (entered_time, entered_by, message, closed) \
                VALUES (NOW(), {userId}, '{message.getMessage()}', FALSE) RETURNING id;")

            pid = cur.fetchone()[0]

            # Create a new thread to handle the heavy lifting
            print(message.getBlocks())
            t = PriorityThread(replyURL, message, slackClient, pid, conn, channelID)
            t.start()

            # Acknowledge the slash command
            return "Thank you! Your message has been received and will be sent out to the team!"

    return "Denied", 401

@app.route("/listp", methods=["POST"])
def listp():
    """/listp"""
    pass

@app.route("/register", methods=["POST"])
def reg():
    """/reg"""

    # When registering, may need to also ping conversations.list api to get the 
    # user's IM Channel so that we can send a message to it. This could be stored
    # in the user_data table

    senderId = request.form["user_id"]
    channelID = request.form["channel_id"]
    fName, lName = request.form["text"].split()

    res = ""

    # Check if user exists
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM slack_user WHERE slack_id = '{senderId}';")
    uid = cur.fetchone()

    if uid is None:
        # This user is not registered.

        # Insert the user into the slack_user table
        cur.execute("INSERT INTO slack_user (slack_id, f_name, l_name) VALUES (%s,%s,%s);", (senderId, fName, lName))

        cur.execute(f"SELECT id FROM slack_user WHERE slack_id = '{senderId}';")

        uid = cur.fetchone()
        # Insert the user into the user_data table
        cur.execute("""INSERT INTO user_data (slack_user_id, points, escalated, out_of_office, disabled) 
                        VALUES (%s, %s, %s, %s, %s)""", (uid[0], 0, False, False, False))


    # This user is registered.

    # Check if a channel/team is registerd
    cur.execute(f"SELECT id FROM slack_team WHERE slack_channel = '{channelID}';")
    cid = cur.fetchone()

    if cid is None:
        # The team is not registered
        # Register the channel/team
        cur.execute("INSERT INTO slack_team (slack_channel) VALUES (%s) RETURNING id;", (channelID,))
        cid = cur.fetchone()

    # Check if this user is a member of this channel/team.
    cur.execute(f"SELECT EXISTS(SELECT id FROM team_members WHERE team_id = {cid[0]} AND slack_user_id = {uid[0]});")

    if cur.fetchone()[0]:
        # The user is registered for this channel
        res = "You are already registered for this team!"

    else:
        cur.execute("INSERT INTO team_members (team_id, slack_user_id) VALUES (%s, %s)", (cid[0], uid[0]))
        res = "You have sucessfully been registered for this team!"

    return res

@app.route("/", methods=["GET"])
def index():
    return "<h1>Hello, World!</h1>"

@app.route("/messageResponse", methods=["POST"])
def messageResponse():
    rawStr = request.get_data(as_text=True)[8:]
    jsonStr = urllib.parse.unquote_plus(rawStr)

    data = json.loads(jsonStr)

    token = data["token"]

    if token == VERIFICATION_TOKEN:
        print(data)
        user = data["user"]["id"]
        channel = data["container"]["channel_id"]
        response_url = data["response_url"]
        action = data["actions"][0]["value"]
        msg = data["message"]["blocks"][2]["text"]["text"]
        ts = data["container"]["message_ts"]
        # The timestamp will be the key to relating this reply to a sent message

        cur = conn.cursor()

        # Get the user's id
        cur.execute(f"SELECT id FROM slack_user WHERE slack_id = '{user}';")
        uid = cur.fetchone()[0]

        # Mark the case as assigned
        cur.execute(f"UPDATE priority SET closed = True WHERE slack_ts = {ts} RETURNING id;")
        pid = cur.fetchone()[0]

        # If the user is accepting the case
        if action == "Accept":

            # Record the user accepting the case.
            cur.execute(f"UPDATE action SET action = 'A', reason = 'Accepted Case', last_updated = NOW() \
                          WHERE priority_id = {pid} AND user_id = {uid};")

            cur.execute(f"UPDATE user_data SET points = points + 1, escalated = FALSE \
                          WHERE slack_user_id = {uid};")

            print(user,channel,token,response_url,action,ts)

        else:

            # If the user is not accepting the case, then record the reason

            cur.execute(f"UPDATE action SET action = 'R', reason = '{'Reason Unknown'}', last_updated = NOW() \
                          WHERE priority_id = {pid} AND user_id = {uid};")

            # Create a reply message
            pr = cm.PriorityReply(channel, user["name"], msg, action)

        # Send an acknowledgement message to the user
        slackClient.chat_update(
            ts=ts,
            channel=channel,
            blocks=pr.getBlocks()
        )

        cur.close()

    else:
        # Validation token was not correct
        return "Denied", 401

    # Acknowledge the message was received
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True)

    # curl localhost:5000/nextp -X POST
