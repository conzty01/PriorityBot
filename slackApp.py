from customMessages import PriorityMessage, ListMessage
from customThreads import PriorityThread
from flask import Flask, request, jsonify
import ssl as ssl_lib
import urllib.parse
#import psycopg2
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
VERIFICATION_TOKEN = os.environ["VERIFICATION_TOKEN"]
SLACK_TOKEN = os.environ["SLACK_TOKEN"]
SSL_CONTEXT = ssl_lib.create_default_context(cafile=certifi.where())

"""
# Create event loop for slack client
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
"""

#conn = psycopg2.connect(os.environ["DATABASE_URL"])

# Create SlackClient in async mode
slackClient = slack.WebClient(
    token=SLACK_TOKEN, ssl=SSL_CONTEXT#, run_async=True, loop=LOOP
)

@app.route("/nextp", methods=["POST"])
def nextp():
    """/nextp P1/P2 Ft. Worth cert issue. <@U4SCYHQUX|conzty01> connected but cannot see problem. Case #123123123"""

    if request.form["token"] == VERIFICATION_TOKEN:

        if request.form["command"] == '/nextp':
            
            rawText = request.form["text"]
            replyURL = request.form["response_url"]
            senderName = request.form["user_name"]
            channelID = request.form["channel_id"]

            # Create a response message
            message = PriorityMessage(channelID, senderName, rawText)

            # Create a new thread to handle the heavy lifting
            print(message.getBlocks())
            t = PriorityThread(replyURL, message.getBlocks(), slackClient)
            t.start()

            # Acknowledge the slash command
            return "Thank you! Your message has been received and will be sent out to the team!"

        if request.form["command"] == '/listp':
            return "1)  Jonathan _____\n2)  Austin _____\n3)  Monica _____\n4)  Shawn _____\netc..."

    return "Denied", 401

@app.route("/listp", methods=["POST"])
def listp():
    """/listp"""
    pass

@app.route("/", methods=["GET"])
def index():
    return "<h1>Hello, World!</h1>"

@app.route("/messageResponse", methods=["POST"])
def messageResponse():
    rawStr = request.get_data(as_text=True)[8:]
    jsonStr = urllib.parse.unquote(rawStr)

    data = json.loads(jsonStr)

    token = data["token"]

    if token == VERIFICATION_TOKEN:
        print(data)
        user = data["user"]
        channel = data["container"]["channel_id"]
        response_url = data["response_url"]
        action = data["actions"][0]["value"]
        ts = data["container"]["message_ts"]
        # The timestamp will be the key to relating this reply to a sent message

        print(user,channel,token,response_url,action,ts)
        slackClient.chat_update(
            ts=ts,
            channel=channel,
            blocks=[{'type': 'section', 'text': {'type': 'mrkdwn', 'text': 'A high priority case has come from conzty01 with the following message:'}}, {'type': 'divider'}, {'type': 'section', 'text': {'type': 'mrkdwn', 'text': 'test'}}, {'type': 'section', 'text': {'type': 'plain_text', 'text': 'You have elected to Accept/Deny the case'}}]
        )

    else:
        return "Denied", 401

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True)

    # curl localhost:5000/nextp -X POST
