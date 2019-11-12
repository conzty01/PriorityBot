import threading
import requests
import time

class PriorityThread(threading.Thread):

    def __init__(self, replyURL, payload, slackClient, lock, conn, teamId):
        super(PriorityThread, self).__init__()
        
        self.payload = payload
        self.replyURL = replyURL
        self.client = slackClient
        self.done = False

        self.LOCK = lock
        self.dbConn = conn
        self.teamId = teamId

    def run(self):
        print("Starting PriorityThread")

        # Workflow of a PriorityThread:
        # 1) Get the ID of the next user
        # 2) Ping user with necessary information

        cur = self.dbConn.cursor()

        assigned = False
        while not assigned:

            cur.execute(f"""
            SELECT slack_id
            FROM slack_user
            JOIN user_data ON (slack_user.id = user_data.slack_user_id)
            JOIN team_members ON (slack_user.id = team_members.slack_user_id)
            JOIN slack_team ON (slack_team.id = team_members.team_id)
            WHERE NOT out_of_office AND
                  NOT disabled AND
                  slack_team.slack_channel = '{self.teamId}'
            ORDER BY escalated DESC, points ASC;
            """)

            slackId = cur.fetchone()

            ts = self.pingUser('D4RMZCVJ6')#slackId)

            # Get the lock for the CASE_DICT
            self.LOCK.acquire()

            # Add this id to CASE_DICT
            self.CASE_DICT[ts] = False

            # Release the lock on CASE_DICT
            self.LOCK.release()

            # Sleep for 20 seconds
            time.sleep(20)

            # Get the lock for CASE_DICT
            self.LOCK.acquire()

            # Get value for this id
            beenAssigned = self.CASE_DICT[ts]

            # Release lock on CASE_DICT
            self.LOCK.release()

            # Check if case was accepted
            if beenAssigned:
                print("Case Assigned")
                assigned = True
                self.CASE_DICT.pop(ts, None)
                print(self.CASE_DICT)

            else:
                print("Case Not Assigned")
                

    def pingUser(self, channelID):
        # Send the message to the given user

        response = self.client.chat_postMessage(
            channel=channelID,
            text='A high priority case has come in',
            blocks=self.payload,
            #as_user=True
        )

        # Return the "ID" of the message
        return response["message"]["ts"]


    def pingChannel(self,chnlID):
        pass

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


