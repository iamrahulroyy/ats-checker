from sqlmodel import Session, SQLModel, create_engine
import os
from dotenv import load_dotenv
import time
from functools import wraps
import logging
from sqlalchemy.exc import OperationalError, TimeoutError
from contextlib import contextmanager
from sqlalchemy import text

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")


def retry_with_backoff(retries=3, backoff_in_seconds=1):
    """
    Decorator that retries the decorated function with exponential backoff.

    Args:
        retries: Maximum number of retries
        backoff_in_seconds: Initial backoff time, doubles with each retry
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except (OperationalError, TimeoutError, ConnectionError) as e:
                    attempts += 1
                    if attempts > retries:
                        logger.error(
                            f"Maximum retries ({retries}) reached. Last error: {e}"
                        )
                        raise

                    sleep_time = backoff_in_seconds * (2 ** (attempts - 1))
                    logger.warning(
                        f"Database connection attempt {attempts} failed: {str(e)}. "
                        f"Retrying in {sleep_time} seconds..."
                    )
                    time.sleep(sleep_time)

        return wrapper

    return decorator


# Circuit breaker implementation
class CircuitBreaker:
    def __init__(self, max_failures=5, reset_interval=300):
        self.max_failures = max_failures
        self.reset_interval = reset_interval
        self.failure_count = 0
        self.reset_time = None

    def is_open(self):
        """Check if circuit is open (too many failures)"""
        if self.reset_time is not None:
            if time.time() < self.reset_time:
                return True
            # Reset after interval
            self.reset_time = None
            self.failure_count = 0
        return False

    def record_success(self):
        """Record a successful operation"""
        self.failure_count = 0
        self.reset_time = None

    def record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            self.reset_time = time.time() + self.reset_interval
            logger.error(f"Circuit breaker opened for {self.reset_interval} seconds")
            return True
        return False


# Create circuit breaker instance
circuit_breaker = CircuitBreaker()


@retry_with_backoff(retries=5, backoff_in_seconds=1)
def create_db_engine():
    """Create SQLAlchemy engine with retry capability"""
    # Check if circuit breaker is open
    if circuit_breaker.is_open():
        raise Exception("Circuit breaker is open. Database connection not attempted.")

    try:
        engine = create_engine(
            DATABASE_URL,
            echo=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )

        # Test connection using proper SQLAlchemy syntax
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()

        circuit_breaker.record_success()
        logger.info("Database engine created successfully")
        return engine

    except Exception as e:
        circuit_breaker.record_failure()
        raise


try:
    engine = create_db_engine()
except Exception as e:
    logger.critical(f"Failed to create database engine: {e}")
    raise


@retry_with_backoff(retries=3)
def init_db():
    """Initialize database schema"""
    if circuit_breaker.is_open():
        raise Exception(
            "Circuit breaker is open. Database initialization not attempted."
        )

    try:
        logger.info("Initializing database...")
        SQLModel.metadata.create_all(engine)
        circuit_breaker.record_success()
        logger.info("Database initialized successfully!")
    except Exception as e:
        circuit_breaker.record_failure()
        raise


@contextmanager
def get_session():
    """Provide a transactional scope around a series of operations"""
    if circuit_breaker.is_open():
        raise Exception("Circuit breaker is open. Database session not created.")

    session = None
    try:

        @retry_with_backoff(retries=3)
        def _get_session_with_retry():
            return Session(engine)

        session = _get_session_with_retry()
        yield session
        session.commit()
        circuit_breaker.record_success()

    except Exception as e:
        if session:
            session.rollback()
        circuit_breaker.record_failure()
        logger.error(f"Database session error: {e}")
        raise

    finally:
        if session:
            session.close()


if __name__ == "__main__":
    init_db()

    try:
        with get_session() as session:
            result = session.execute(text("SELECT 1")).fetchone()
            logger.info(f"Database query result: {result}")
    except Exception as e:
        logger.error(f"Error using database: {e}")
