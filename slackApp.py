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
    """/priority P1/P2 Ft. Worth cert issue. <@xxxxxxxxx|username> connected but cannot see problem. Case #123123123"""

    # Verify that the message has come from slack
    if request.form["token"] == VERIFICATION_TOKEN:

        rawText = request.form["text"]
        replyURL = request.form["response_url"]
        senderUserName = request.form["user_name"]
        channelID = request.form["channel_id"]
        senderId = request.form["user_id"]

        print("A new priority has come in")

        if len(rawText) < 1:
            return "An empty message was received-- aborting sending priority to team."

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
    """/listp """

    # Verify that the message has come from slack
    if request.form["token"] == VERIFICATION_TOKEN:

        # Get the channelID
        channelID = request.form["channel_id"]
        senderID = request.form["user_id"]

        cur = conn.cursor()

        # Get an ordered list of eligible team members
        cur.execute(f"""
            SELECT slack_user.f_name, slack_user.l_name
            FROM slack_user
            JOIN team_members ON (slack_user.id = team_members.slack_user_id)
            JOIN slack_team ON (slack_team.id = team_members.team_id)
            WHERE NOT slack_user.out_of_office AND
                  NOT team_members.disabled AND
                  slack_team.slack_channel = '{channelID}'
            ORDER BY team_members.escalated DESC, team_members.points ASC, slack_user.l_name ASC;
        """)

        res = cur.fetchall()

        # If no results were returned, no users were found for this channel.
        #  It could also be that the channel has not been registered (yet).
        #  In either situation, this response should suffice. 
        if len(res) == 0:
            return "This slack channel does not have any registered users."

        # Create the List Message
        message = cm.ListMessage(channelID, res)

        # # Send the list to the channel
        # slackClient.chat_postMessage(
        #     channel=channelID,
        #     text='Here is the curent P1/P2 lineup',
        #     blocks=message.getBlocks()
        # )

        logAction(f"Viewed List: User {senderID} has viewed the following priority list for channel {channelID}: {res}")

        cur.close()

        return message.getMessagePayload()

    else:
        return "Denied", 401

@app.route("/register", methods=["POST"])
def reg():
    """/register """

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
        cur.execute("INSERT INTO team_members (team_id, slack_user_id, points, escalated, disabled) VALUES (%s, %s, %s, %s, %s)", (cid[0], uid[0], 0, False, False))
        res = "You have sucessfully been registered for this team!"

    cur.close()

    return res

@app.route("/escalateUser", methods=["POST"])
def escalateUser():
    """/escalate <@xxxxxxxxx|username>"""

    # Escalate the provided user
    senderId = request.form["user_id"]
    channelID = request.form["channel_id"]
    payload = request.form["text"]

    if len(payload.split()) != 1:
        return f"Invalid Usage: Expected 1 argument but received {len(payload.split())}"

    # <@xxxxxxxxx|username>
    sid, name = payload.split("|")
    sid = sid[2:]
    name = name[:-1]

    cur = conn.cursor()

    # Get the get user id for the given user on the given team
    cur.execute(f"""
            SELECT slack_user.id, slack_team.id
            FROM slack_user JOIN team_members ON (slack_user.id = team_members.slack_user_id)
            JOIN slack_team ON (slack_team.id = team_members.team_id)
            WHERE slack_id = '{sid}' AND slack_channel = '{channelID}';
    """)
    res = cur.fetchone()

    # If none exists, the user is not registered for this team.
    if res is None:
        name = payload.split("|")[1]
        return f"User '{name}' is not registered for this team."

    # Unpack the results
    uid, tid = res

    # Update the entry in the database
    cur.execute(f"UPDATE team_members SET escalated = TRUE WHERE team_id = {tid} AND slack_user_id = {uid};")

    # Log the escalation of the user
    logAction(f"Escalated User: User {senderId} has escalated user {sid} for channel {channelID}")

    cur.close()

    return f"Successfully escalated {name} for this team."

@app.route("/setOOO", methods=["POST"])
def oooUser():
    """/ooo <@xxxxxxxxx|username>"""

    # Mark the provided users as out of office
    senderId = request.form["user_id"]
    channelID = request.form["channel_id"]
    payload = request.form["text"]

    rawUsers = payload.split()

    cur = conn.cursor()

    # iterate over the users
    for rUser in rawUsers:
        # <@xxxxxxxxx|username>
        sid = payload.split("|")[0][2:]

        # Set the user as ooo if they are registered to the given slack channel.
        #  If the username is not a part of the provided slack channel, they 
        #  not be updated
        cur.execute(f"""
            UPDATE slack_user
            SET out_of_office = TRUE
            FROM team_members JOIN slack_team ON (team_members.team_id = slack_team.id)
            WHERE slack_id = '{sid}' AND slack_team.slack_channel = '{channelID}'
            RETURNING f_name, l_name;
        """)

        # Log that the sender marked this user as ooo
        logAction(f"Marked OOO: User {senderId} set {sid} as out of office for channel {channelID}")

    cur.close()

    return "Successfully marked user(s) as out of office"

@app.route("/available", methods=["POST"])
def markAvailable():
    """/available """

    # Mark the sender as available
    #  In this slackbot, a user is considered available if they are
    #  NOT out of office and NOT disabled.
    senderId = request.form["user_id"]
    channelID = request.form["channel_id"]
    payload = request.form["text"]

    cur = conn.cursor()

    # Set the user as in-office and return the slack_user id
    cur.execute(f"""UPDATE slack_user
                   SET out_of_office = FALSE
                   WHERE slack_id = '{senderId}'
                   RETURNING id;""")

    res = cur.fetchone()

    if res is None:
        return "You are not registered."

    else:
        suid = res[0]

    # Get the row id for the team_member entry that is being enabled
    cur.execute(f"""SELECT team_members.id
                    FROM team_members JOIN slack_team ON (team_members.team_id = slack_team.id)
                    WHERE team_members.slack_user_id = {suid}
                    AND slack_team.slack_channel = '{channelID}';""")

    res = cur.fetchone()
    if res is None:
        return "You are not registered for this team."

    else:
        tmid = res[0]

    # Set the user as 'enabled' for this team
    cur.execute(f"""UPDATE team_members
                    SET disabled = FALSE
                    WHERE id = {tmid};""")

    # Log that the user marked themselves as available
    logAction(f'Marked Available: User {senderId} (id: {suid}) has set themselves available for team {channelID} (id: {tmid})')

    cur.close()

    return "You have been marked In-Office and Available for this team."

@app.route("/disable", methods=["POST"])
def disableUser():
    """/disable <@xxxxxxxxx|username>"""

    # Mark the user as disabled for the provided team

    # Verify that the message has come from slack
    if request.form["token"] == VERIFICATION_TOKEN:
        senderId = request.form["user_id"]
        channelId = request.form["channel_id"]
        payload = request.form["text"]

        cur = conn.cursor()

        sid, username = payload.split("|")
        sid = sid[2:]
        username = username[:-1]

        # Get the userId for the provided slack username
        cur.execute(f"""SELECT id
                        FROM slack_user
                        WHERE slack_id = '{sid}'""")

        res = cur.fetchone()

        if res is None:
            return "The provided user is not registered."

        uid = res[0]

        # Get the teamId for the provided slack channel
        cur.execute(f"""SELECT id
                        FROM slack_team
                        WHERE slack_channel = '{channelId}'""")

        res = cur.fetchone()

        if res is None:
            return "This channel is not registered."

        tid = res[0]

        # Mark the provided user as disabled for the provided team.
        cur.execute(f"""UPDATE team_members
                        SET disabled = TRUE
                        WHERE slack_user_id = {uid}
                        AND team_id = {tid}
                        RETURNING id""")

        res = cur.fetchone()

        if res is None:
            return "The provided user is not registered for this team"

        logAction(f"Disabled User: User {senderId} disabled user {sid} for channel {channelId}")

        cur.close()

        return f"Successfully marked {username} as disabled for this team"

    return 401, "Denied"

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

        user = data["user"]
        channel = data["container"]["channel_id"]
        response_url = data["response_url"]
        action = data["actions"][0]["value"]
        msg = data["message"]["blocks"][2]["text"]["text"]
        ts = data["container"]["message_ts"]
        # The timestamp will be the key to relating this reply to a sent message

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
        if action == "Accept":

            # Mark the case as assigned
            cur.execute(f"UPDATE priority SET closed = TRUE WHERE id = {pid};")

            # Record the user accepting the case.
            cur.execute(f"UPDATE action SET action = 'A', reason = 'Accepted Case', last_updated = NOW() \
                          WHERE priority_id = {pid} AND user_id = {uid};")

            # Add the points to the user's data
            cur.execute(f"UPDATE team_members SET points = points + 1, escalated = FALSE \
                          WHERE slack_user_id = {uid} AND team_id = {tid};")

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

def logAction(msg):
    # Log the provided action in the database

    cur = conn.cursor()
    cur.execute(f"""INSERT INTO app_userlog (time, log) VALUES (NOW(), '{msg.replace("'",'"')}');""")


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True)

    # curl localhost:5000/nextp -X POST
