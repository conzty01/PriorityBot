from slackapp import logAction
import psycopg2
import datetime
import pytz

def main():
    now = datetime.datetime.now()

    timezone = pytz.timezone("America/Chicago")
    local_now = timezone.localize(now)

    # If it is within the 0 hour Central Time
    if local_now.hour == 0:
        # Then reset the ooo statuses

        # Establish connection with DB
        conn = psycopg2.connect(os.getenv('DATABASE_URL').replace("'",""))
        conn.autocommit = True

        cur = conn.cursor()

        try:
            # Reset all users to be in-office
            cur.execute("UPDATE slack_user SET out_of_office = FALSE;")
            success = True

        except Exception e:
            success = False

        finally:
            if success:
                logAction("OOO Reset: Successfully reset ooo for all users")
            else:
                logAction(f"OOO Reset: Failed to reset ooo for all users. The following exception occured: {e}")

if __name__ == "__main__":
    main()