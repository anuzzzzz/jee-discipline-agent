"""
Base loader class for question ingestion.

All loaders inherit from this and implement load() method.
"""

from abc import ABC, abstractmethod
from typing import Generator
from dataclasses import dataclass
from typing import Optional


@dataclass
class RawQuestion:
    """
    Raw question data before database insertion.

    This is the common format all loaders output.
    """
    # Required fields
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str  # "A", "B", "C", or "D"

    # Classification
    subject: str  # "physics", "chemistry", "mathematics"
    chapter: str  # e.g., "mechanics", "algebra"
    topic: str    # e.g., "rotational_motion", "quadratic_equations"

    # Metadata
    difficulty: int = 2  # 1-5 scale
    source: str = ""     # e.g., "JEEBench", "JEE2020"
    source_id: Optional[str] = None  # Original ID from source
    year: Optional[int] = None
    is_pyq: bool = False  # Previous Year Question

    # Solution
    solution: str = ""

    # Optional hints
    hint_1: Optional[str] = None
    hint_2: Optional[str] = None
    hint_3: Optional[str] = None

    # Image URLs (if any)
    question_image_url: Optional[str] = None
    solution_image_url: Optional[str] = None


class BaseLoader(ABC):
    """
    Abstract base class for question loaders.

    Each data source (JEEBench, Kaggle, manual) gets its own loader.
    """

    name: str = "base"

    @abstractmethod
    def load(self) -> Generator[RawQuestion, None, None]:
        """
        Load questions from the source.

        Yields:
            RawQuestion objects one at a time (memory efficient)
        """
        pass

    def validate_question(self, q: RawQuestion) -> bool:
        """
        Validate a question has required fields.

        Returns:
            True if valid, False otherwise
        """
        # Check required text fields
        if not q.question_text or len(q.question_text) < 10:
            return False

        # Check options exist
        if not all([q.option_a, q.option_b, q.option_c, q.option_d]):
            return False

        # Check correct option is valid
        if q.correct_option not in ["A", "B", "C", "D"]:
            return False

        # Check subject is valid
        if q.subject not in ["physics", "chemistry", "mathematics"]:
            return False

        return True

    def normalize_subject(self, subject: str) -> str:
        """Normalize subject name to our standard format."""
        subject = subject.lower().strip()

        mappings = {
            "phy": "physics",
            "phys": "physics",
            "physics": "physics",
            "chem": "chemistry",
            "chemistry": "chemistry",
            "math": "mathematics",
            "maths": "mathematics",
            "mathematics": "mathematics",
        }

        return mappings.get(subject, subject)

    def normalize_option(self, option: str) -> str:
        """Normalize correct option to single letter."""
        option = option.strip().upper()

        # Handle various formats
        if option in ["A", "B", "C", "D"]:
            return option

        if option.startswith("OPTION"):
            option = option.replace("OPTION", "").strip()

        if option in ["1", "2", "3", "4"]:
            return {"1": "A", "2": "B", "3": "C", "4": "D"}[option]

        # Try to extract first letter
        if option and option[0] in ["A", "B", "C", "D"]:
            return option[0]

        return "A"  # Default fallback
