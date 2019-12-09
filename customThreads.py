import customMessages as cm
import threading
import requests
import time

class PriorityThread(threading.Thread):

    def __init__(self, replyURL, payload, slackClient, pid, conn, teamId, senderName):
        super(PriorityThread, self).__init__()

        self.payload = payload
        self.replyURL = replyURL
        self.client = slackClient
        self.done = False

        self.pid = pid
        self.dbConn = conn
        self.teamId = teamId
        self.sender = senderName

    def run(self):
        print("Starting PriorityThread")

        # Workflow of a PriorityThread:
        # 1) Get the ID of the next user
        # 2) Ping user with necessary information

        cur = self.dbConn.cursor()

        # Get an ordered list of eligible team members
        cur.execute(f"""
            SELECT slack_user.id, slack_user.slack_id
            FROM slack_user
            JOIN team_members ON (slack_user.id = team_members.slack_user_id)
            JOIN slack_team ON (slack_team.id = team_members.team_id)
            WHERE NOT out_of_office AND
                  NOT disabled AND
                  slack_team.slack_channel = '{self.teamId}'
            ORDER BY escalated DESC, team_members.points ASC, slack_user.l_name ASC;
        """)

        empList = cur.fetchall()

        assigned = False
        while not assigned and len(empList) != 0:

            # Get the next employee candidate
            candidate = empList.pop(0)

            # Ping the user
            ts, timeoutChannel = self.pingUser(candidate[0], candidate[1])

            # Update the priority's slack_ts so that it points to this action as being
            #  the last transaction regarding this priority. We are doing this because,
            #  as far as our workflow is concerned, this is the last interaction that
            #  a user could reply to. This way, when a response comes in, we can query
            #  against the priority table for the timestamp that is provided by slack.
            cur.execute(f"UPDATE priority SET slack_ts={ts} WHERE id={self.pid};")

            # Sleep for 20 seconds
            time.sleep(20)

            # Get the current status of the priority
            cur.execute(f"SELECT closed FROM priority WHERE id={self.pid};")
            beenAssigned = cur.fetchone()[0]

            # Check if case was accepted
            if beenAssigned:
                print(f"Case {ts} Assigned")
                assigned = True

            else:
                # Mark that the user did not respond
                cur.execute(f"UPDATE action SET action = 'R', reason = 'Timeout', last_updated = NOW() \
                              WHERE priority_id = {self.pid} AND user_id = {candidate[0]};")

                self.updateMessage_Timeout(timeoutChannel, ts)

                print(f"Case {ts} Not Assigned")

            # Go around the loop another time.


        # -- Broke out of loop --

        # If the case was not assigned
        if not assigned:
            # Reasons a case was not assigned:
            #  1. User rejected the case (handled in /messageResponse)
            #  2. User did not respond (timeout -- handled in loop)
            #  3. No more employees in the list

            # Notify the channel
            ts = self.pingChannel(self.teamId)

            # Update the priority's slack_ts so that it points to this action as being
            #  the last transaction regarding this priority. We are doing this because,
            #  as far as our workflow is concerned, this is the last interaction that
            #  a user could reply to. This way, when a response comes in, we can query
            #  against the priority table for the timestamp that is provided by slack.
            cur.execute(f"UPDATE priority SET slack_ts={ts} WHERE id={self.pid};")

        else:
            # If the case was assigned, notify the channel.

            # Get the name of the user who responded
            cur.execute(f"""SELECT f_name, l_name
                            FROM slack_user JOIN action ON (action.user_id = slack_user.id)
                            WHERE priority_id = {self.pid} AND reason = 'Accepted Case';""")

            fName, lName = cur.fetchone()

            responderName = fName + " " + lName

            self.notifyChannel(self.teamId, responderName)

        # Terminate this thread


    def pingUser(self, uid, channelID):
        # Send the message to the given user

        fmtMsg = cm.PriorityDirectMessage(channelID, self.sender, self.payload)

        response = self.client.chat_postMessage(
            channel=channelID,
            text='A high priority case has come in',
            blocks=fmtMsg.getBlocks(),
            #as_user=True
        )

        # Add record of the action to the database
        cur = self.dbConn.cursor()

        cur.execute(f"INSERT INTO action (user_id, priority_id, last_updated) \
                     VALUES ({uid}, {self.pid}, NOW());")

        ts = response["message"]["ts"]
        responseChannelId = response["channel"]

        print(f"Sent message to user {channelID} in channel {responseChannelId} with ts: {ts}")

        # Return the "ID" of the message
        return ts, responseChannelId


    def pingChannel(self,chnlID):
        # Send the message to the given channel

        fmtMsg = cm.PriorityChannelMessage(chnlID, self.sender, self.payload)

        response = self.client.chat_postMessage(
            channel=chnlID,
            text='@here Unable to assign a high priority case',
            blocks=fmtMsg.getBlocks(),
            #as_user=True
        )

        # Add record of the action to the database
        cur = self.dbConn.cursor()

        cur.execute(f"INSERT INTO action (priority_id, action, reason, last_updated) \
                     VALUES ({self.pid}, 'U', 'Notified Channel', NOW());")

        t = response["message"]["ts"]

        print(f"Sent message to channel {chnlID} with ts: {t}")

        # Return the "ID" of the message
        return response["message"]["ts"]

    def notifyNext(self,userID):
        pass

    def notifyChannel(self, channelID, acceptedUser):
        # Notify the channel that a particular user has accepted the priority.

        fmtMsg = cm.PriorityChannelNotification(channelID, self.sender, self.payload, acceptedUser)

        response = self.client.chat_postMessage(
            channel=channelID,
            text='Incoming Priority Assigned',
            blocks=fmtMsg.getBlocks(),
            #as_user=True
        )

    def updateMessage_Timeout(self, channelID, ts):
        # Update a message with saying they did not respond in the allotted time.

        print(f"Sending timeout message to user {channelID} with ts: {ts}")

        fmtMsg = cm.PriorityDirectTimeout(channelID, self.sender, self.payload)

        response = self.client.chat_update(
            ts=ts,
            text="Response Time Exceeded",
            channel=channelID,
            blocks=fmtMsg.getBlocks()
        )
