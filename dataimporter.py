"""
Facebook Data Importer for Neo4j

This script imports Stanford's Facebook dataset into a Neo4j database
for use with the Social Network Application.

Usage:
    python import_facebook_data.py <dataset_directory>
"""

import os
import sys
import random
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple


def generate_random_name() -> str:
    """Generate a random name for a user."""
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
                  "Linda", "William", "Elizabeth", "David", "Susan", "Richard", "Jessica",
                  "Joseph", "Sarah", "Thomas", "Karen", "Charles", "Nancy", "Ryan", "Bob", "Gerald"]

    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
                 "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
                 "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]

    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_email(user_id: int) -> str:
    """Generate a fake email for a user based on their ID."""
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "example.com"]
    return f"user{user_id}@{random.choice(domains)}"

def parse_edges_file(file_path: str) -> List[Tuple[int, int]]:
    """Parse an .edges file and return a list of (source, target) tuples."""
    edges = []
    with open(file_path, 'r') as f:
        for line in f:
            source, target = map(int, line.strip().split())
            edges.append((source, target))
    return edges

def parse_circles_file(file_path: str) -> Dict[str, List[int]]:
    """Parse a .circles file and return a dictionary of circle_name -> [user_ids]."""
    circles = {}
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 1:
                circle_name = parts[0]
                user_ids = []
                if len(parts) > 1:
                    user_ids = [int(uid) for uid in parts[1:]]
                circles[circle_name] = user_ids
    return circles

def import_facebook_data(dataset_dir: str):
    """
    Import Facebook data from the Stanford dataset into Neo4j.

    Args:
        dataset_dir: Path to the directory containing the Facebook dataset
    """
    # Connect to Neo4j
    connection = None
    try:
        # This will reuse the credentials from config.ini created by the main app
        from App import SocialNetworkCLI
        connection = SocialNetworkCLI()._init_db_connection()
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        sys.exit(1)

    if not connection.verify_connection():
        print("Failed to connect to Neo4j database.")
        sys.exit(1)

    dataset_path = Path(dataset_dir)
    edges_files = list(dataset_path.glob("*.edges"))

    if not edges_files:
        print(f"No .edges files found in {dataset_dir}")
        sys.exit(1)

    print(f"Found {len(edges_files)} network files.")

    # Create constraints if they don't exist (similar to the App.py setup)
    print("Ensuring database constraints...")
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE"
    ]

    for constraint in constraints:
        connection.execute_query(constraint)

    # Process each .edges file
    total_users = set()
    total_edges = []

    for edges_file in edges_files:
        ego_user_id = int(edges_file.stem.split('.')[0])
        total_users.add(ego_user_id)

        # Parse the edges file
        edges = parse_edges_file(str(edges_file))
        for source, target in edges:
            total_users.add(source)
            total_users.add(target)
            total_edges.append((source, target))

        print(f"Processed {edges_file.name}: {len(edges)} connections")

    print(f"Total unique users: {len(total_users)}")
    print(f"Total connections: {len(total_edges)}")

    # Import users in batches
    print("Importing users...")
    batch_size = 500
    user_list = list(total_users)

    # Generate a default password for all imported users
    default_password = "password123"
    hashed_password = hashlib.sha256(default_password.encode()).hexdigest()

    for i in range(0, len(user_list), batch_size):
        batch = user_list[i:i+batch_size]

        # Prepare user data
        users_data = []
        for user_id in batch:
            username = f"fb{user_id}"
            users_data.append({
                "username": username,
                "name": generate_random_name(),
                "email": generate_email(user_id),
                "password": hashed_password,
                "bio": f"Imported Facebook user (ID: {user_id})",
                "user_id": user_id  # Store the original Facebook ID for relationship mapping
            })

        # Create users
        query = """
        UNWIND $users AS user
        MERGE (u:User {username: user.username})
        ON CREATE SET
            u.name = user.name,
            u.email = user.email,
            u.password = user.password,
            u.bio = user.bio,
            u.joinDate = datetime(),
            u.facebook_id = user.user_id
        RETURN count(u) as created_count
        """

        result = connection.execute_query(query, {"users": users_data})
        if result:
            created = result[0]["created_count"]
            print(f"Imported users batch {i//batch_size + 1}/{(len(user_list) + batch_size - 1)//batch_size}: {created} processed")

    # Import relationships in batches
    print("Importing relationships...")
    for i in range(0, len(total_edges), batch_size):
        batch = total_edges[i:i+batch_size]

        # Prepare relationship data
        rels_data = []
        for source, target in batch:
            rels_data.append({
                "source": f"fb{source}",
                "target": f"fb{target}"
            })

        # Create relationships
        query = """
        UNWIND $rels AS rel
        MATCH (source:User {username: rel.source})
        MATCH (target:User {username: rel.target})
        MERGE (source)-[f:FOLLOWS {since: datetime()}]->(target)
        RETURN count(f) as created_count
        """

        result = connection.execute_query(query, {"rels": rels_data})
        if result:
            created = result[0]["created_count"]
            print(f"Imported relationships batch {i//batch_size + 1}/{(len(total_edges) + batch_size - 1)//batch_size}: {created} processed")

    # Optionally import circles if available
    circles_files = list(dataset_path.glob("*.circles"))
    if circles_files:
        print("Importing circle information...")

        for circles_file in circles_files:
            ego_user_id = int(circles_file.stem.split('.')[0])
            ego_username = f"fb{ego_user_id}"

            # Parse circles file
            circles = parse_circles_file(str(circles_file))

            for circle_name, member_ids in circles.items():
                # Create the circle
                create_circle_query = """
                MATCH (ego:User {username: $ego_username})
                MERGE (c:Circle {name: $circle_name, owner: $ego_username})
                RETURN c
                """

                connection.execute_query(
                    create_circle_query,
                    {"ego_username": ego_username, "circle_name": circle_name}
                )

                # Add members to the circle
                member_usernames = [f"fb{mid}" for mid in member_ids]

                add_members_query = """
                MATCH (c:Circle {name: $circle_name, owner: $ego_username})
                UNWIND $member_usernames AS member_username
                MATCH (m:User {username: member_username})
                MERGE (c)-[:HAS_MEMBER]->(m)
                RETURN count(m) as added_count
                """

                result = connection.execute_query(
                    add_members_query,
                    {
                        "ego_username": ego_username,
                        "circle_name": circle_name,
                        "member_usernames": member_usernames
                    }
                )

                if result:
                    added = result[0]["added_count"]
                    print(f"Added {added} members to circle '{circle_name}' for user {ego_username}")

    print("\nImport completed successfully!")
    print(f"Imported {len(total_users)} users and {len(total_edges)} follows relationships")
    print("\nDefault password for all imported users: 'password123'")
    print("You can now log in to any imported user with username format 'fb<id>' (e.g., 'fb123')")

    # Close the connection
    connection.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <dataset_directory>")
        sys.exit(1)

    dataset_dir = sys.argv[1]
    if not os.path.isdir(dataset_dir):
        print(f"Error: {dataset_dir} is not a valid directory")
        sys.exit(1)

    import_facebook_data(dataset_dir)
