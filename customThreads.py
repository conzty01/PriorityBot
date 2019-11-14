import threading
import requests
import time

class PriorityThread(threading.Thread):

    def __init__(self, replyURL, payload, slackClient, pid, conn, teamId):
        super(PriorityThread, self).__init__()

        self.payload = payload
        self.replyURL = replyURL
        self.client = slackClient
        self.done = False

        self.pid = pid
        self.dbConn = conn
        self.teamId = teamId

    def run(self):
        print("Starting PriorityThread")

        # Workflow of a PriorityThread:
        # 1) Get the ID of the next user
        # 2) Ping user with necessary information

        cur = self.dbConn.cursor()

        # Get the list of team members
        cur.execute(f"""
            SELECT slack_user.id, slack_user.slack_id
            FROM slack_user
            JOIN user_data ON (slack_user.id = user_data.slack_user_id)
            JOIN team_members ON (slack_user.id = team_members.slack_user_id)
            JOIN slack_team ON (slack_team.id = team_members.team_id)
            WHERE NOT out_of_office AND
                    NOT disabled AND
                    slack_team.slack_channel = '{self.teamId}'
            ORDER BY escalated DESC, points ASC, slack_user.l_name ASC;
        """)

        empList = cur.fetchall()

        assigned = False
        while not assigned and len(empList) != 0:

            # Get the next employee candidate
            candidate = empList.pop(0)

            # Ping the user
            ts = self.pingUser(candidate[0], candidate[1])

            # Update priority with slack timestamp
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
            self.pingChannel(self.teamId)

        # Terminate this thread


    def pingUser(self, uid, channelID):
        # Send the message to the given user

        response = self.client.chat_postMessage(
            channel=channelID,
            text='A high priority case has come in',
            blocks=self.payload.getBlocks(),
            #as_user=True
        )

        # Add record of the action to the database
        cur = self.dbConn.cursor()

        cur.execute(f"INSERT INTO action (user_id, priority_id, last_updated) \
                     VALUES ({uid}, {self.pid}, NOW());")

        # Return the "ID" of the message
        return response["message"]["ts"]


    def pingChannel(self,chnlID):
        # Send the message to the given channel

        response = self.client.chat_postMessage(
            channel=chnlID,
            text='@here Unable to assign a high priority case',
            blocks=self.payload.getBlocks(),
            #as_user=True
        )

        # Add record of the action to the database
        cur = self.dbConn.cursor()

        cur.execute(f"INSERT INTO action (priority_id, action, reason, last_updated) \
                     VALUES ({self.pid}, 'U', 'Notified Channel', NOW());")

        # Return the "ID" of the message
        return response["message"]["ts"]

    def notifyNext(self,userID):
        pass


class ScheduleThread(threading.Thread):
    from pyvirtualdisplay import Display
    import schedule
    import selenium

    def __init__(self):
        # Two month interval
        #  60sec/min * 60min/hr * 24hr/day * 30day/month * 2
        self.interval = 60 * 60 * 24 * 30 * 2

    def run(self):
        print("Starting Schedule Thread")

        # Set up the scheduler
        schedule.every(self.interval).seconds.do(self.update)

        # Begin infinite loop
        while True:
            # Run the job
            schedule.run_pending()

            # Sleep for the interval + 10 seconds just to be sure
            #  that the next cycle will run
            sleep(self.interval + 10)

    def update(self):
        # https://help.pythonanywhere.com/pages/selenium/
        with Display():

            browser = selenium.webdriver.Firefox()

            try:
                browser.get('http//www.google.com')
                print(browser.title)

            finally:
                browser.quit()


