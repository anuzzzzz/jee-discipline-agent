"""
Kaggle JEE Questions Loader

Loads questions from CSV files downloaded from Kaggle.
Supports multiple CSV formats commonly found on Kaggle.
"""

import csv
from pathlib import Path
from typing import Generator, Dict, Any, List

from ingestion.loaders.base import BaseLoader, RawQuestion


# Common column name variations
COLUMN_MAPPINGS = {
    "question": ["question", "question_text", "Question", "QUESTION", "problem", "Problem"],
    "option_a": ["option_a", "Option A", "option A", "A", "a", "opt_a", "choice_a"],
    "option_b": ["option_b", "Option B", "option B", "B", "b", "opt_b", "choice_b"],
    "option_c": ["option_c", "Option C", "option C", "C", "c", "opt_c", "choice_c"],
    "option_d": ["option_d", "Option D", "option D", "D", "d", "opt_d", "choice_d"],
    "correct": ["correct_option", "Correct Option", "correct", "answer", "Answer", "correct_answer"],
    "subject": ["subject", "Subject", "SUBJECT", "topic", "category"],
    "solution": ["solution", "Solution", "explanation", "Explanation"],
    "difficulty": ["difficulty", "Difficulty", "level", "Level"],
}


def find_column(row: Dict, field: str) -> Any:
    """Find a column value using multiple possible names."""
    for col_name in COLUMN_MAPPINGS.get(field, [field]):
        if col_name in row and row[col_name]:
            return row[col_name]
    return None


def detect_subject(text: str, filename: str = "") -> str:
    """Detect subject from question text or filename."""
    text_lower = (text + filename).lower()

    physics_keywords = ["force", "velocity", "acceleration", "mass", "energy", "momentum",
                       "electric", "magnetic", "wave", "optics", "thermodynamics", "newton"]
    chemistry_keywords = ["reaction", "compound", "element", "acid", "base", "organic",
                         "bond", "electron", "oxidation", "mole", "solution"]
    math_keywords = ["integral", "derivative", "matrix", "equation", "function", "limit",
                    "probability", "vector", "triangle", "circle", "polynomial"]

    physics_count = sum(1 for kw in physics_keywords if kw in text_lower)
    chemistry_count = sum(1 for kw in chemistry_keywords if kw in text_lower)
    math_count = sum(1 for kw in math_keywords if kw in text_lower)

    if physics_count >= chemistry_count and physics_count >= math_count:
        return "physics"
    elif chemistry_count >= math_count:
        return "chemistry"
    else:
        return "mathematics"


class KaggleCSVLoader(BaseLoader):
    """
    Loader for JEE questions from Kaggle CSV files.

    Handles various CSV formats commonly found on Kaggle.
    """

    name = "kaggle"

    def __init__(self, file_path: str = "data/raw/jee_questions.csv", subject_filter: str = None):
        """
        Initialize loader.

        Args:
            file_path: Path to CSV file
            subject_filter: Optional filter ("physics", "chemistry", "mathematics")
        """
        self.file_path = Path(file_path)
        self.subject_filter = subject_filter

    def _parse_row(self, row: Dict, filename: str) -> RawQuestion:
        """Parse a CSV row into RawQuestion format."""

        question_text = find_column(row, "question") or ""

        option_a = find_column(row, "option_a") or ""
        option_b = find_column(row, "option_b") or ""
        option_c = find_column(row, "option_c") or ""
        option_d = find_column(row, "option_d") or ""

        correct = find_column(row, "correct") or "A"
        correct_option = self.normalize_option(str(correct))

        # Get or detect subject
        subject_raw = find_column(row, "subject")
        if subject_raw:
            subject = self.normalize_subject(subject_raw)
        else:
            subject = detect_subject(question_text, filename)

        solution = find_column(row, "solution") or ""

        # Difficulty
        diff_raw = find_column(row, "difficulty")
        try:
            difficulty = int(diff_raw) if diff_raw else 2
            difficulty = max(1, min(5, difficulty))
        except:
            difficulty = 2

        return RawQuestion(
            question_text=question_text.strip(),
            option_a=str(option_a).strip(),
            option_b=str(option_b).strip(),
            option_c=str(option_c).strip(),
            option_d=str(option_d).strip(),
            correct_option=correct_option,
            subject=subject,
            chapter=subject,  # Will be refined later
            topic="general",
            difficulty=difficulty,
            source=f"Kaggle_{self.file_path.stem}",
            solution=str(solution).strip() if solution else "",
            is_pyq=False,
        )

    def load(self) -> Generator[RawQuestion, None, None]:
        """Load questions from CSV file."""

        if not self.file_path.exists():
            print(f"❌ File not found: {self.file_path}")
            print(f"   Download from Kaggle and place in: {self.file_path}")
            return

        print(f"📂 Loading questions from {self.file_path}...")

        loaded = 0
        skipped = 0

        # Try different encodings
        encodings = ["utf-8", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                with open(self.file_path, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)

                    for row in reader:
                        try:
                            question = self._parse_row(row, self.file_path.name)

                            # Filter by subject if specified
                            if self.subject_filter:
                                if question.subject != self.subject_filter:
                                    continue

                            if self.validate_question(question):
                                loaded += 1
                                yield question
                            else:
                                skipped += 1

                        except Exception as e:
                            skipped += 1
                            continue

                    break  # Success, exit encoding loop

            except UnicodeDecodeError:
                continue

        print(f"✅ Kaggle CSV: Loaded {loaded}, Skipped {skipped}")


class MultiCSVLoader(BaseLoader):
    """Load from multiple CSV files in a directory."""

    name = "multi_csv"

    def __init__(self, directory: str = "data/raw", subject_filter: str = None):
        self.directory = Path(directory)
        self.subject_filter = subject_filter

    def load(self) -> Generator[RawQuestion, None, None]:
        """Load from all CSV files in directory."""

        if not self.directory.exists():
            print(f"❌ Directory not found: {self.directory}")
            return

        csv_files = list(self.directory.glob("*.csv"))
        print(f"📂 Found {len(csv_files)} CSV files in {self.directory}")

        for csv_file in csv_files:
            loader = KaggleCSVLoader(
                file_path=str(csv_file),
                subject_filter=self.subject_filter
            )
            yield from loader.load()
