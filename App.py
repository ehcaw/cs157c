#!/usr/bin/env python3
"""
Social Networking Application with Neo4j Backend

This application provides a command-line interface for a social network
with user management, profile viewing/editing, and other social features
powered by a Neo4j graph database.
"""

import cmd
import os
import sys
import getpass
import re
import hashlib
import configparser

try:
    from neo4j import GraphDatabase, exceptions as neo4j_exceptions
except ImportError:
    print("Neo4j driver not found. Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "neo4j"])
    from neo4j import GraphDatabase, exceptions as neo4j_exceptions

class Neo4jConnection:
    """Handles connection and queries to Neo4j database."""

    def __init__(self, uri, user, password):
        self.driver = None
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test the connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("Connected to Neo4j database")
        except neo4j_exceptions.ServiceUnavailable:
            print("Failed to connect to Neo4j database. Please check if Neo4j is running and credentials are correct.")
            self.driver = None
        except Exception as e:
            print(f"Error connecting to Neo4j: {e}")
            self.driver = None

    def close(self):
        """Close the driver connection."""
        if self.driver:
            self.driver.close()

    def verify_connection(self):
        """Verify if the connection to Neo4j is active."""
        return self.driver is not None

    def execute_query(self, query, parameters=None):
        """Execute a Cypher query and return results."""
        if not self.driver:
            print("No connection to Neo4j database")
            return None

        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record for record in result]
        except Exception as e:
            print(f"Query error: {e}")
            return None

class SocialNetworkCLI(cmd.Cmd):
    """Command-line interface for the Socli Network application."""

    intro = """
    ╔═══════════════════════════════════════════════╗
    ║                    Socli                      ║
    ║           Type 'help' for commands            ║
    ╚═══════════════════════════════════════════════╝
    """
    prompt = "socli> "
    current_user = None

    def __init__(self):
        super().__init__()
        self.connection = self._init_db_connection()
        self._setup_database()

    def _init_db_connection(self):
        """Initialize connection to Neo4j database."""
        config = configparser.ConfigParser()

        # Check if config file exists, otherwise prompt for credentials
        if os.path.exists('config.ini'):
            config.read('config.ini')
            uri = config.get('neo4j', 'uri', fallback='bolt://localhost:7687')
            user = config.get('neo4j', 'user', fallback='neo4j')
            password = config.get('neo4j', 'password', fallback='')
        else:
            print("Neo4j database configuration not found.")
            uri = input("Enter Neo4j URI [bolt://localhost:7687]: ") or "bolt://localhost:7687"
            user = input("Enter Neo4j username [neo4j]: ") or "neo4j"
            password = getpass.getpass("Enter Neo4j password: ")

            # Save configuration
            config['neo4j'] = {
                'uri': uri,
                'user': user,
                'password': password
            }

            with open('config.ini', 'w') as configfile:
                config.write(configfile)

            print("Configuration saved to config.ini")

        return Neo4jConnection(uri, user, password)

    def _setup_database(self):
        """Set up initial database constraints and indexes."""
        if not self.connection.verify_connection():
            return

        # Create constraints to ensure unique usernames and emails
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE"
        ]

        for constraint in constraints:
            self.connection.execute_query(constraint)


    def do_register(self, arg):
        """Register a new user: register"""
        if not self.connection.verify_connection():
            print("Database connection is not available. Cannot register.")
            return

        print("\n=== User Registration ===\n")

        # Collect user information
        username = input("Username: ").strip()
        if not username:
            print("Username cannot be empty.")
            return

        # Check if username already exists
        result = self.connection.execute_query(
            "MATCH (u:User {username: $username}) RETURN u",
            {"username": username}
        )

        if result and len(result) > 0:
            print(f"Username '{username}' is already taken.")
            return

        # Get remaining details
        name = input("Full Name: ").strip()
        email = input("Email: ").strip()

        # Validate email
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            print("Invalid email format.")
            return

        # Check if email already exists
        result = self.connection.execute_query(
            "MATCH (u:User {email: $email}) RETURN u",
            {"email": email}
        )

        if result and len(result) > 0:
            print(f"Email '{email}' is already registered.")
            return

        # Get and hash password
        password = getpass.getpass("Password: ")
        if not password:
            print("Password cannot be empty.")
            return

        confirm_password = getpass.getpass("Confirm Password: ")
        if password != confirm_password:
            print("Passwords do not match.")
            return

        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Create user in Neo4j
        query = """
        CREATE (u:User {
            username: $username,
            name: $name,
            email: $email,
            password: $password,
            joinDate: datetime(),
            bio: $bio
        })
        RETURN u.username as username
        """

        result = self.connection.execute_query(
            query,
            {
                "username": username,
                "name": name,
                "email": email,
                "password": hashed_password,
                "bio": ""
            }
        )

        if result:
            print(f"\nUser '{username}' registered successfully! You can now login.")
        else:
            print("Failed to register user. Please try again.")

    def do_login(self, arg):
        """Login to your account: login <username>"""
        if not self.connection.verify_connection():
            print("Database connection is not available. Cannot login.")
            return

        if self.current_user:
            print(f"You're already logged in as {self.current_user}.")
            return

        username = arg.strip() if arg else input("Username: ").strip()
        if not username:
            print("Username cannot be empty.")
            return

        password = getpass.getpass("Password: ")
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Check credentials
        query = """
        MATCH (u:User {username: $username, password: $password})
        RETURN u.username as username
        """

        result = self.connection.execute_query(
            query,
            {"username": username, "password": hashed_password}
        )

        if result and len(result) > 0:
            self.current_user = username
            self.prompt = f"{username}> "
            print(f"Welcome back, {username}!")
        else:
            print("Invalid username or password.")

    def do_logout(self, arg):
        """Logout from your account."""
        if not self.current_user:
            print("You're not logged in.")
            return

        username = self.current_user
        self.current_user = None
        self.prompt = "socli> "
        print(f"Goodbye, {username}!")

    def do_profile(self, arg):
        """View your profile or another user's profile: profile [username]"""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return

        # Determine which profile to view
        if arg:
            username = arg.strip()
        elif self.current_user:
            username = self.current_user
        else:
            print("Please login first or specify a username.")
            return

        # Query user profile
        query = """
        MATCH (u:User {username: $username})
        RETURN u.username as username, u.name as name, u.email as email,
               u.bio as bio, u.joinDate as joinDate
        """

        result = self.connection.execute_query(
            query,
            {"username": username}
        )

        if not result or len(result) == 0:
            print(f"User '{username}' not found.")
            return

        user = result[0]

        # Display profile
        print("\n=== User Profile ===")
        print(f"Username: {user['username']}")
        print(f"Name: {user['name']}")

        # Only show email for the current user
        if self.current_user and self.current_user == username:
            print(f"Email: {user['email']}")

        print(f"Bio: {user['bio'] or 'No bio available'}")

        if user['joinDate']:
            print(f"Joined: {user['joinDate']}")

        # Get follower count
        followers_query = """
        MATCH (follower:User)-[:FOLLOWS]->(u:User {username: $username})
        RETURN count(follower) as followerCount
        """

        followers_result = self.connection.execute_query(
            followers_query,
            {"username": username}
        )

        if followers_result:
            print(f"Followers: {followers_result[0]['followerCount']}")

        # Get following count
        following_query = """
        MATCH (u:User {username: $username})-[:FOLLOWS]->(following:User)
        RETURN count(following) as followingCount
        """

        following_result = self.connection.execute_query(
            following_query,
            {"username": username}
        )

        if following_result:
            print(f"Following: {following_result[0]['followingCount']}")

        print()

    def do_edit_profile(self, arg):
        """Edit your profile information."""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return

        if not self.current_user:
            print("Please login first to edit your profile.")
            return

        print("\n=== Edit Profile ===\n")

        # Get current profile info
        query = """
        MATCH (u:User {username: $username})
        RETURN u.name as name, u.email as email, u.bio as bio
        """

        result = self.connection.execute_query(
            query,
            {"username": self.current_user}
        )

        if not result:
            print("Failed to retrieve your profile.")
            return

        current = result[0]

        # Get updated information
        print(f"Current name: {current['name']}")
        name = input("New name (leave blank to keep current): ").strip()
        if not name:
            name = current['name']

        print(f"Current email: {current['email']}")
        email = input("New email (leave blank to keep current): ").strip()
        if email:
            # Validate email
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                print("Invalid email format. Email not updated.")
                email = current['email']
            else:
                # Check if email is already used
                email_check = self.connection.execute_query(
                    "MATCH (u:User {email: $email}) WHERE u.username <> $username RETURN u",
                    {"email": email, "username": self.current_user}
                )

                if email_check and len(email_check) > 0:
                    print(f"Email '{email}' is already in use. Email not updated.")
                    email = current['email']
        else:
            email = current['email']

        print(f"Current bio: {current['bio'] or 'No bio available'}")
        bio = input("New bio (leave blank to keep current): ").strip()
        if not bio:
            bio = current['bio'] or ""

        # Update profile
        update_query = """
        MATCH (u:User {username: $username})
        SET u.name = $name, u.email = $email, u.bio = $bio
        RETURN u.username as username
        """

        update_result = self.connection.execute_query(
            update_query,
            {
                "username": self.current_user,
                "name": name,
                "email": email,
                "bio": bio
            }
        )

        if update_result:
            print("\nProfile updated successfully!")
        else:
            print("Failed to update profile.")

    def do_change_password(self, arg):
        """Change your password."""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return

        if not self.current_user:
            print("Please login first to change your password.")
            return

        current_password = getpass.getpass("Current password: ")
        hashed_current = hashlib.sha256(current_password.encode()).hexdigest()

        # Verify current password
        verify_query = """
        MATCH (u:User {username: $username, password: $password})
        RETURN u.username as username
        """

        verify_result = self.connection.execute_query(
            verify_query,
            {"username": self.current_user, "password": hashed_current}
        )

        if not verify_result or len(verify_result) == 0:
            print("Current password is incorrect.")
            return

        # Get new password
        new_password = getpass.getpass("New password: ")
        if not new_password:
            print("Password cannot be empty.")
            return

        confirm_password = getpass.getpass("Confirm new password: ")
        if new_password != confirm_password:
            print("Passwords do not match.")
            return

        # Update password
        hashed_new = hashlib.sha256(new_password.encode()).hexdigest()

        update_query = """
        MATCH (u:User {username: $username})
        SET u.password = $password
        RETURN u.username as username
        """

        update_result = self.connection.execute_query(
            update_query,
            {"username": self.current_user, "password": hashed_new}
        )

        if update_result:
            print("Password changed successfully!")
        else:
            print("Failed to change password.")

    def do_delete(self, arg):
        """Delete your own user: delete"""
        if not self.current_user:
            print("Please login first")
            return


        password = getpass.getpass("Password: ")
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        query = """
        MATCH (u:User {username: $username, password: $password})
        RETURN u.username as username
        """
        password_confirmation = getpass.getpass("Confirm Password: ")
        hashed_password_confirmation = hashlib.sha256(password_confirmation.encode()).hexdigest()

        if hashed_password != hashed_password_confirmation:
            print("Passwords didn't match")
            return

        result = self.connection.execute_query(
            query,
            {"username": self.current_user, "password": hashed_password}
        )

        if result:
            confirm_deletion = input("Confirm you want to delete by typing yes: ")
            if not confirm_deletion or confirm_deletion != "yes":
                print("Cancelling user deletion")
                return

            query = """
            MATCH (n: User {username: $username})
            DETACH DELETE n
            """

            delete_result =  self.connection.execute_query(query, {"username": self.current_user})
            if delete_result is not None:
                print(f"User {self.current_user} successfully deleted!")
                self.current_user = None
                self.prompt = "social> "
            else:
                print("Failed to delete user.")


    def do_follow(self, arg):
        """Follow another user: follow <username>"""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return
        if not self.current_user:
            print("Please login first.")
            return

        username = arg.strip()
        if not username:
            print("Please specify a username to follow.")
            return
        if username == self.current_user:
            print("You cannot follow yourself.")
            return

        # Check existence
        user_exists = self.connection.execute_query(
            "MATCH (u:User {username: $username}) RETURN u", {"username": username}
        )
        if not user_exists:
            print(f"User '{username}' not found.")
            return

        # Check if already following
        already = self.connection.execute_query(
            """
            MATCH (:User {username: $me})-[r:FOLLOWS]->(:User {username: $them})
            RETURN r.since AS since
            """,
            {"me": self.current_user, "them": username}
        )

        if already:
            since = already[0].get("since")
            print(f"You're already following {username} since {since or 'earlier'}.")
            return

        # Follow
        query = """
        MATCH (a:User {username: $me}), (b:User {username: $them})
        CREATE (a)-[:FOLLOWS {since: datetime()}]->(b)
        """
        self.connection.execute_query(query, {"me": self.current_user, "them": username})
        print(f"You're now following {username}.")
        # By Siddhi Patil – UC-5


    def do_unfollow(self, arg):
        """Unfollow a user: unfollow <username>"""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return
        if not self.current_user:
            print("Please login first.")
            return

        username = arg.strip()
        if not username:
            print("Please specify a username to unfollow.")
            return

        check = self.connection.execute_query(
            """
            MATCH (:User {username: $me})-[r:FOLLOWS]->(:User {username: $them})
            RETURN r
            """,
            {"me": self.current_user, "them": username}
        )

        if not check:
            print(f"You are not following {username}.")
            return

        confirm = input(f"Unfollow {username}? Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            print("Cancelled.")
            return

        self.connection.execute_query(
            """
            MATCH (:User {username: $me})-[r:FOLLOWS]->(:User {username: $them})
            DELETE r
            """,
            {"me": self.current_user, "them": username}
        )
        print(f"You've unfollowed {username}.")
    # By Siddhi Patil – UC-6

    def do_followers(self, arg):
        """List users following you or another user: followers [username]"""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return

        username = arg.strip() or self.current_user
        if not username:
            print("Please login or specify a username.")
            return

        result = self.connection.execute_query(
            """
            MATCH (f:User)-[:FOLLOWS]->(u:User {username: $username})
            RETURN f.username AS follower, f.name AS name
            ORDER BY follower
            """,
            {"username": username}
        )

        if not result:
            print(f"No one follows {username}.")
            return

        print(f"\nFollowers of {username}:")
        for i, row in enumerate(result, 1):
            print(f"{i}. {row['follower']} ({row['name']})")
    # By Siddhi Patil – UC-7A


    def do_following(self, arg):
        """List users you or another user is following: following [username]"""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return

        username = arg.strip() or self.current_user
        if not username:
            print("Please login or specify a username.")
            return

        result = self.connection.execute_query(
            """
            MATCH (u:User {username: $username})-[:FOLLOWS]->(f:User)
            RETURN f.username AS following, f.name AS name
            ORDER BY following
            """,
            {"username": username}
        )

        if not result:
            print(f"{username} is not following anyone.")
            return

        print(f"\n{username} is following:")
        for i, row in enumerate(result, 1):
            print(f"{i}. {row['following']} ({row['name']})")
    # By Siddhi Patil – UC-7B

    def do_recommendations(self, arg):
        """Show people you may know: recommendations"""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return
        if not self.current_user:
            print("Please login first.")
            return

        result = self.connection.execute_query(
            """
            MATCH (me:User {username: $me})-[:FOLLOWS]->(:User)-[:FOLLOWS]->(rec:User)
            WHERE rec.username <> $me AND NOT (me)-[:FOLLOWS]->(rec)
            RETURN rec.username AS username, rec.name AS name, COUNT(*) AS mutuals
            ORDER BY mutuals DESC, username
            LIMIT 5
            """,
            {"me": self.current_user}
        )

        if not result:
            print("No recommendations available.")
            return

        print("\nPeople You May Know:")
        for i, row in enumerate(result, 1):
            print(f"{i}. {row['username']} ({row['name']}) – {row['mutuals']} mutual connection(s)")
    # By Siddhi Patil – UC-9
    def do_clear(self, arg):
        """Clear the screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
        if not self.current_user:
            print(self.intro)

    def do_help(self, arg):
        """List available commands with "help" or detailed help with "help cmd"."""
        if arg:
            # Show help for a specific command
            super().do_help(arg)
        else:
            # Show categorized help menu
            print("\n=== Socli Network Commands ===\n")

            print("Account Management:")
            print("  register        - Create a new user account")
            print("  login <user>    - Log in to your account")
            print("  logout          - Log out from your account")
            print("  profile [user]  - View your profile or another user's profile")
            print("  edit_profile    - Edit your profile information")
            print("  change_password - Change your account password")
            print("  delete          - Delete your own account")

            print("\nGeneral Commands:")
            print("  clear           - Clear the screen")
            print("  help            - Show this help message")
            print("  exit            - Exit the application")

            print("\nSearch & Exploration:")
            print("  search [term]         - Search users by name or username")
            print("  popular               - Explore the most followed users")
            print()

    def do_ls(self, arg):
        """List available commands with "help" or detailed help with "help cmd"."""
        if arg:
            # Show help for a specific command
            super().do_help(arg)
        else:
            # Show categorized help menu
            print("\n=== Socli Network Commands ===\n")

            print("Account Management:")
            print("  register        - Create a new user account")
            print("  login <user>    - Log in to your account")
            print("  logout          - Log out from your account")
            print("  profile [user]  - View your profile or another user's profile")
            print("  edit_profile    - Edit your profile information")
            print("  change_password - Change your account password")

            print("\nSocli Interactions:")
            print("  follow <user>   - Follow another user")
            print("  unfollow <user> - Unfollow a user")
            print("  followers [user]- List users following you or another user")
            print("  following [user]- List users you or another user is following")
            print("  recommendations - Get friend recommendations")

            print("\nGeneral Commands:")
            print("  clear           - Clear the screen")
            print("  help            - Show this help message")
            print("  exit            - Exit the application")
            print()

    def do_exit(self, arg):
        """Exit the application."""
        print("Thank you for using Socli. Goodbye!")

        if self.connection:
            self.connection.close()

        return True

    def do_quit(self, arg):
        """Exit the application."""
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """Exit on Ctrl+D."""
        print()  # Add newline
        return self.do_exit(arg)
    
    def do_search(self, arg):
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return

        term = arg.strip()
        if not term:
            term = input("Enter name or username to search: ").strip()
        if not term:
            print("Search term cannot be empty.")
            return

        query = """
        MATCH (u:User)
        WHERE toLower(u.name) CONTAINS toLower($term) OR toLower(u.username) CONTAINS toLower($term)
        RETURN u.username AS username, u.name AS name
        ORDER BY u.username
        LIMIT 10
        """

        result = self.connection.execute_query(query, {"term": term})

        if not result:
            print("No matching users found.")
            return

        print("\n=== Search Results ===")
        for i, user in enumerate(result, 1):
            print(f"{i}. {user['username']} ({user['name']})")
        print()

    def do_popular(self, arg):
        """Explore popular users (most followed): popular"""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return

        query = """
        MATCH (u:User)<-[:FOLLOWS]-(f:User)
        RETURN u.username AS username, u.name AS name, count(f) AS followers
        ORDER BY followers DESC
        LIMIT 10
        """

        result = self.connection.execute_query(query)

        if not result:
            print("Failed to retrieve popular users.")
            return

        print("\n=== Most Followed Users ===")
        for i, user in enumerate(result, 1):
            print(f"{i}. {user['username']} ({user['name']}) - {user['followers']} followers")
        print()
    


    def do_mutuals(self, arg):
        """Find mutual connections between you and another user: mutuals <username>"""
        if not self.connection.verify_connection():
            print("Database connection is not available.")
            return

        if not self.current_user:
            print("Please login first.")
            return

        other_username = arg.strip()
        if not other_username:
            print("Usage: mutuals <username>")
            return

        if other_username == self.current_user:
            print("Cannot check mutuals with yourself.")
            return

        query = """
        MATCH (me:User {username: $user1})-[:FOLLOWS]->(x)<-[:FOLLOWS]-(other:User {username: $user2})
        RETURN DISTINCT x.username AS mutual_friend
        """

        result = self.connection.execute_query(query, {
            "user1": self.current_user,
            "user2": other_username
        })

        if result is None:
            print("Failed to retrieve mutuals.")
            return

        if not result:
            print(f"No mutuals found with {other_username}.")
        else:
            print(f"\n=== Mutuals with {other_username} ===")
            for i, r in enumerate(result, 1):
                print(f"{i}. {r['mutual_friend']}")
            print()


    def do_debug_mutual_pairs(self, arg):
        """Temporary: Show sample users with mutual follows."""
        query = """
        MATCH (a:User)-[:FOLLOWS]->(b:User),
            (b)-[:FOLLOWS]->(a)
        RETURN DISTINCT a.username AS user1, b.username AS user2
        LIMIT 10
        """
        result = self.connection.execute_query(query)
        if not result:
            print("No mutual follow pairs found.")
            return
        print("\n=== Sample Mutual Follower Pairs ===")
        for i, row in enumerate(result, 1):
            print(f"{i}. {row['user1']} ↔ {row['user2']}")




if __name__ == "__main__":
    try:
        SocialNetworkCLI().cmdloop()
    except KeyboardInterrupt:
        print("\nExiting Socli Network. Goodbye!")
        sys.exit(0)
