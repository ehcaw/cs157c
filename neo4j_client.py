import sys

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
