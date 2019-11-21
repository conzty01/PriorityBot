import psycopg2
import os

def createConfigTable(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS app_config CASCADE")

    cur.execute("""

    CREATE TABLE app_config (
    id          SERIAL,
    name        VARCHAR(50),
    value       VARCHAR(50),

    PRIMARY KEY (id),
    UNIQUE (name)

    );

    """)

# Possibly not necessary if the functionality is that the channel that users
#  run the slash command in is where it should spit out the team notification

# The above message is no longer the reason for the teams table. Instead, the 
#  team table should be used to determine who to ping the message to.
#  The message can still be put in the thread where it originated, (which will 
#  be beneficial for people who are in multiple teams)

def createTeamTable(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS slack_team")
    cur.execute("""
    CREATE TABLE slack_team (
    id              SERIAL,
    slack_channel   VARCHAR(10),
    team_name       VARCHAR(40),
    PRIMARY KEY (id),
    UNIQUE (slack_channel)
    );
    """)

def createTeamMemberstable(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS team_members")
    cur.execute("""
    CREATE TABLE team_members (
    id              SERIAL,
    team_id         INT,
    slack_user_id   INT,
    points          INT,
    escalated       BOOLEAN,
    PRIMARY KEY (id)
    );
    """)

def createUserTable(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS slack_user CASCADE")

    cur.execute("""

    CREATE TABLE slack_user (
    id          SERIAL,
    slack_id    VARCHAR(9),
    f_name      VARCHAR(20),
    l_name      VARCHAR(20),

    PRIMARY KEY (id),
    UNIQUE (slack_id)

    );

    """)

def createUserDataTable(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS user_data CASCADE")

    cur.execute("""
    
    CREATE TABLE user_data (
    id              SERIAL,
    slack_user_id   INT,
    out_of_office   BOOLEAN,
    disabled        BOOLEAN,

    PRIMARY KEY (id),
    UNIQUE (slack_user_id),
    FOREIGN KEY (slack_user_id) REFERENCES slack_user(id)

    );
    
    """)

def createActionsTable(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS action CASCADE")

    cur.execute("""

    CREATE TABLE action (
    id              SERIAL,
    user_id         INT,
    priority_id     INT,
    action          VARCHAR(1),
    reason          VARCHAR(100),
    last_updated    TIMESTAMP,

    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES slack_user(id),
    FOREIGN KEY (priority_id) REFERENCES priority(id)

    );

    """)

def createPriorityTable(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS priority CASCADE")

    cur.execute("""
    CREATE TABLE priority (
    id              SERIAL,
    entered_time    TIMESTAMP,
    entered_by      INT,
    slack_ts        NUMERIC,
    message         TEXT,
    closed          BOOLEAN,
    slack_team_id   INT,

    PRIMARY KEY (id),
    FOREIGN KEY (entered_by) REFERENCES slack_user(id)
    FOREIGN KEY (slack_team_id) REFERENCES slack_team(id)

    );
    
    """)


def main(conn):
    print("Creating Database Tables:")
    print("  app_config: ", end=" ")
    createConfigTable(conn)
    print(" SUCCESS")

    print("  slack_user: ", end=" ")
    createUserTable(conn)
    print(" SUCCESS")

    print("  user_data: ", end=" ")
    createUserDataTable(conn)
    print(" SUCCESS")

    print("  priority: ", end=" ")
    createPriorityTable(conn)
    print(" SUCCESS")

    print("  action: ", end=" ")
    createActionsTable(conn)
    print(" SUCCESS")

    print("  slack_team: ", end=" ")
    createTeamTable(conn)
    print(" SUCCESS")

    print("  team_members: ", end=" ")
    createTeamMemberstable(conn)
    print(" SUCCESS")

    print("\nCommiting Database Changes: ", end=" ")
    conn.commit()
    print(" SUCCESS")

    conn.close()
    print("Connection Closed")

    print("\nDatabase Creation Complete")

if __name__ == '__main__':
    print("Starting")
    conn = psycopg2.connect(os.getenv('DATABASE_URL').replace("'",""))
    print("Connection established")

    main(conn)