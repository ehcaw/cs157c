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
        self.uri = uri
        self.user = user
        # Mask password for security in debug messages
        masked_pwd = '*' * len(password) if password else '(empty)'

        print(f"DEBUG: Attempting to connect to Neo4j database")
        print(f"DEBUG: URI: {uri}")
        print(f"DEBUG: Username: {user}")
        print(f"DEBUG: Password: {masked_pwd}")

        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test the connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("Connected to Neo4j database successfully!")

        # ServiceUnavailable errors
        except neo4j_exceptions.ServiceUnavailable as e:
            print("\n==== CONNECTION ERROR: SERVICE UNAVAILABLE ====")
            print(f"Failed to connect to Neo4j database: {str(e)}")
            print("\nPossible causes:")
            print("- Neo4j server is not running or unreachable")
            print("- Incorrect URI format (for Neo4j Aura, use 'neo4j+s://' not 'bolt://')")
            print("- Firewall or network issue preventing connection")
            print("- Check if you need to use a VPN")
            print("============================================\n")
            self.driver = None

        # Authentication errors
        except neo4j_exceptions.AuthError as e:
            print("\n==== AUTHENTICATION ERROR ====")
            print(f"Failed to authenticate with Neo4j: {str(e)}")
            print("\nPossible causes:")
            print("- Incorrect username or password")
            print("- User does not have access to this database")
            print("- Access token may have expired (TokenExpired)")
            print("================================\n")
            self.driver = None

        # Configuration errors
        except neo4j_exceptions.ConfigurationError as e:
            print("\n==== CONFIGURATION ERROR ====")
            print(f"Configuration error with Neo4j connection: {str(e)}")
            print("\nPossible causes:")
            print("- Invalid configuration parameters")
            print("- Authentication configuration issues")
            print("- Certificate configuration problems")
            print("- Check your URI format and authentication details")
            print("===============================\n")
            self.driver = None

        # Client-side errors
        except neo4j_exceptions.ClientError as e:
            print("\n==== CLIENT ERROR ====")
            print(f"Client error with Neo4j: {str(e)}")
            print("\nPossible causes:")
            print("- Cypher syntax error")
            print("- Constraint violation")
            print("- Improper data types")
            print("=======================\n")
            self.driver = None

        # Database errors
        except neo4j_exceptions.DatabaseError as e:
            print("\n==== DATABASE ERROR ====")
            print(f"Database error with Neo4j: {str(e)}")
            print("\nPossible causes:")
            print("- Database may be in a failed state")
            print("- Internal server error")
            print("=========================\n")
            self.driver = None

        # Transient errors
        except neo4j_exceptions.TransientError as e:
            print("\n==== TRANSIENT ERROR ====")
            print(f"Transient error with Neo4j: {str(e)}")
            print("\nPossible causes:")
            print("- Database temporarily unavailable")
            print("- Leader election in progress (cluster)")
            print("- Operation attempted on read-only database")
            print("- This error is usually temporary - retry later")
            print("==========================\n")
            self.driver = None

        # Session errors
        except neo4j_exceptions.SessionExpired as e:
            print("\n==== SESSION EXPIRED ====")
            print(f"Session expired: {str(e)}")
            print("\nInfo: Your session with the Neo4j database has expired.")
            print("Recommendation: Create a new session and retry.")
            print("=========================\n")
            self.driver = None

        # Generic driver errors
        except neo4j_exceptions.DriverError as e:
            print("\n==== DRIVER ERROR ====")
            print(f"Neo4j driver error: {type(e).__name__}: {str(e)}")
            print("\nThis is a general driver error that could have various causes.")
            print("Check connection parameters and driver compatibility.")
            print("=======================\n")
            self.driver = None

        # Fallback for any other exceptions
        except Exception as e:
            print("\n==== UNEXPECTED ERROR ====")
            print(f"Error connecting to Neo4j: {type(e).__name__}: {str(e)}")
            print("\nConnection parameters:")
            print(f"- URI: {uri}")
            print(f"- Username: {user}")
            print("===========================\n")
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
        except neo4j_exceptions.ClientError as e:
            print(f"\n==== QUERY ERROR: CLIENT ERROR ====")
            print(f"Error: {str(e)}")
            print("Possible causes:")
            print("- Syntax error in Cypher query")
            print("- Constraint violation")
            print("===================================\n")
            return None
        except neo4j_exceptions.DatabaseError as e:
            print(f"\n==== QUERY ERROR: DATABASE ERROR ====")
            print(f"Error: {str(e)}")
            print("Possible causes:")
            print("- Database encountered an error processing the query")
            print("=====================================\n")
            return None
        except neo4j_exceptions.TransientError as e:
            print(f"\n==== QUERY ERROR: TRANSIENT ERROR ====")
            print(f"Error: {str(e)}")
            print("Possible causes:")
            print("- Database temporarily unavailable")
            print("- Try running the query again in a moment")
            print("=======================================\n")
            return None
        except Exception as e:
            print(f"\n==== QUERY ERROR ====")
            print(f"Error executing query: {type(e).__name__}: {str(e)}")
            print("======================\n")
            return None
