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

# TODO migrate the user_data table to either the slack_user table or the
#  team_members table. This is because, ooo and disabled are relevant to 
#  each team or to the user as a whole and does not need to be in its own
#  table.

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
            senderUserName = request.form["user_name"]
            channelID = request.form["channel_id"]
            senderId = request.form["user_id"]

            print("=================")
            print("A new priority has come in")
            print(rawText,senderUserName,channelID,senderId)

            # # Create a Priority Message
            # message = cm.PriorityMessage(channelID, senderUserName, rawText)

            # Record the message in the Database
            cur = conn.cursor()

            # Find the user who entered the priority
            cur.execute(f"SELECT id, f_name, l_name FROM slack_user WHERE slack_id = '{senderId}';")
            userId, fName, lName = cur.fetchone()

            senderName = fName + " " + lName

            # Find the channel that this message was sent to
            cur.execute(f"SELECT id FROM slack_team WHERE slack_channel = '{channelID}'")
            cid = cur.fetchone()[0]

            if cid is None:
                return "This team is not registered to send priority messages. Please register using /reg"

            # Make record of the priority
            cur.execute(f"INSERT INTO priority (entered_time, entered_by, message, closed, slack_team_id) \
                VALUES (NOW(), {userId}, '{rawText}', FALSE, {cid}) RETURNING id;")

            # Get the id of the priority that was just created
            pid = cur.fetchone()[0]

            # Create a new thread to handle the heavy lifting
            #print(message.getBlocks())
            t = PriorityThread(replyURL, rawText, slackClient, pid, conn, channelID, senderName)
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
        cur.execute("INSERT INTO slack_user (slack_id, f_name, l_name, out_of_office) VALUES (%s,%s,%s,%s) RETURNING id;", (senderId, fName, lName, False))

        uid = cur.fetchone()


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
        cur.execute("INSERT INTO team_members (team_id, slack_user_id, points, escalated, disabled) VALUES (%s, %s, %s, %s, %s)", (cid[0], uid[0], 0, False))
        res = "You have sucessfully been registered for this team!"

    return res

@app.route("/escalateUser", methods=["POST"])
def escalateUser():
    """/escalate @conzty01"""

    # Escalate the provided user
    senderId = request.form["user_id"]
    channelID = request.form["channel_id"]
    paylaod = request.form["text"]

    print(payload)

    if len(payload.split()) != 1:
        return f"Invalid Usage: Expected 1 argument but received {len(payload.split())}"


    return "SUCCESS", 200

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
        user = data["user"]
        channel = data["container"]["channel_id"]
        response_url = data["response_url"]
        action = data["actions"][0]["value"]
        msg = data["message"]["blocks"][2]["text"]["text"]
        ts = data["container"]["message_ts"]
        # The timestamp will be the key to relating this reply to a sent message

        print("--------------------")
        print(f"A response has come in for ts: {ts}")

        cur = conn.cursor()

        # Get the user's id who responded
        cur.execute(f"SELECT id, f_name, l_name FROM slack_user WHERE slack_id = '{user['id']}';")
        uid, fName, lName = cur.fetchone()

        responderName = fName + " " + lName

        # Get the priority id for the priority in question, the team it was entered for,
        #  and the user who first entered it
        cur.execute(f"""SELECT priority.id, slack_team.id, slack_user.f_name, slack_user.l_name 
                        FROM priority JOIN slack_user ON (slack_user.id = priority.entered_by)
                        JOIN slack_team ON (slack_team.id = priority.slack_team_id)
                        WHERE priority.slack_ts = {ts};""")
        pid, tid, fName, lName = cur.fetchone()

        senderName = fName + " " + lName

        # If the user is accepting the case
        print("111111111111111111111111111111111111111111111111111111111")
        print("  action == 'Accept'")
        print(action == "Accept")
        print(action)
        print(data["actions"][0]["value"])
        if action == "Accept":

            # Mark the case as assigned
            cur.execute(f"UPDATE priority SET closed = TRUE WHERE id = {pid};")

            # Record the user accepting the case.
            cur.execute(f"UPDATE action SET action = 'A', reason = 'Accepted Case', last_updated = NOW() \
                          WHERE priority_id = {pid} AND user_id = {uid};")

            # Add the points to the user's data
            cur.execute(f"UPDATE team_members SET points = points + 1, escalated = FALSE \
                          WHERE slack_user_id = {uid} AND team_id = {tid};")

            print(user,channel,token,response_url,action,ts)

        else:

            # If the user is not accepting the case, then record the reason

            cur.execute(f"UPDATE action SET action = 'R', reason = '{'Reason Unknown'}', last_updated = NOW() \
                          WHERE priority_id = {pid} AND user_id = {uid};")



        # Check to see if the channel is registered as a team channel
        cur.execute(f"SELECT id FROM slack_team WHERE slack_channel = '{channel}'")

        if cur.fetchone() is not None:
            # If this is coming from a registered channel, send back a ChannelReply message
            pr = cm.PriorityChannelReply(channel, senderName, msg, action, responderName)

        else:
            pr = cm.PriorityDirectReply(channel, senderName, msg, action)

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
