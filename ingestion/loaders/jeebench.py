"""
JEEBench Dataset Loader

Loads questions from the JEEBench dataset on HuggingFace.
Dataset: https://huggingface.co/datasets/daman1209arora/jeebench

Actual dataset format:
- subject: "phy", "chem", "math"
- description: "JEE Adv 2016 Paper 1"
- gold: "A", "B", "C", or "D"
- index: question number
- type: "MCQ", etc.
- question: Full text with options embedded as (A), (B), (C), (D)
"""

import re
from typing import Generator, Dict, Any, Optional, Tuple
from datasets import load_dataset

from ingestion.loaders.base import BaseLoader, RawQuestion


class JEEBenchLoader(BaseLoader):
    """
    Loader for JEEBench dataset from HuggingFace.

    The dataset contains JEE Advanced questions with options embedded in text.
    """

    name = "jeebench"

    def __init__(self, subset: str = None):
        """
        Initialize loader.

        Args:
            subset: Optional subject filter ("phy", "chem", "math", "physics", etc.)
        """
        self.subset = subset
        self.dataset = None

    def _load_dataset(self):
        """Load the dataset from HuggingFace."""
        if self.dataset is None:
            print("Loading JEEBench dataset from HuggingFace...")
            self.dataset = load_dataset("daman1209arora/jeebench", split="test")
            print(f"   Loaded {len(self.dataset)} questions")

    def _parse_options_from_text(self, question_text: str) -> Tuple[str, str, str, str, str]:
        """
        Extract question stem and options from the full question text.

        JEEBench format has options embedded like:
        (A) option text
        (B) option text
        ...

        Returns:
            (question_stem, option_a, option_b, option_c, option_d)
        """
        # Pattern to match options: (A), (B), (C), (D)
        # Also handles \n(A), variations with $ for LaTeX
        pattern = r'\(([ABCD])\)\s*'

        # Find all option positions
        matches = list(re.finditer(pattern, question_text))

        if len(matches) < 4:
            # Fallback: return full text as question, empty options
            return question_text, "", "", "", ""

        # Extract question stem (everything before first option)
        question_stem = question_text[:matches[0].start()].strip()

        # Extract each option
        options = {}
        for i, match in enumerate(matches):
            option_letter = match.group(1)
            start = match.end()

            # End is either next option or end of string
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(question_text)

            option_text = question_text[start:end].strip()
            options[option_letter] = option_text

        return (
            question_stem,
            options.get("A", ""),
            options.get("B", ""),
            options.get("C", ""),
            options.get("D", "")
        )

    def _extract_year_from_description(self, description: str) -> Optional[int]:
        """Extract year from description like 'JEE Adv 2016 Paper 1'."""
        match = re.search(r'20\d{2}', description)
        if match:
            return int(match.group())
        return None

    def _map_subject(self, subject_code: str) -> str:
        """Map subject code to full name."""
        mapping = {
            "phy": "physics",
            "chem": "chemistry",
            "math": "mathematics",
        }
        return mapping.get(subject_code.lower(), "physics")

    def _get_chapter_topic(self, subject: str) -> Tuple[str, str]:
        """Get default chapter and topic based on subject."""
        defaults = {
            "physics": ("mechanics", "general"),
            "chemistry": ("physical_chemistry", "general"),
            "mathematics": ("algebra", "general"),
        }
        return defaults.get(subject, ("general", "general"))

    def _parse_question(self, row: Dict[str, Any]) -> RawQuestion:
        """Parse a single row into RawQuestion format."""

        # Get full question text and parse it
        full_text = row.get("question", "")
        question_stem, opt_a, opt_b, opt_c, opt_d = self._parse_options_from_text(full_text)

        # Get subject
        subject_code = row.get("subject", "phy")
        subject = self._map_subject(subject_code)

        # Get chapter and topic (JEEBench doesn't provide these, use defaults)
        chapter, topic = self._get_chapter_topic(subject)

        # Get correct answer
        correct_option = row.get("gold", "A").upper()
        if correct_option not in ["A", "B", "C", "D"]:
            correct_option = "A"

        # Extract year from description
        description = row.get("description", "")
        year = self._extract_year_from_description(description)

        # Get question index as source ID
        source_id = str(row.get("index", ""))

        return RawQuestion(
            question_text=question_stem,
            option_a=opt_a,
            option_b=opt_b,
            option_c=opt_c,
            option_d=opt_d,
            correct_option=correct_option,
            subject=subject,
            chapter=chapter,
            topic=topic,
            difficulty=3,  # JEE Advanced = medium-hard
            source="JEEBench",
            source_id=source_id,
            year=year,
            is_pyq=True,
            solution="",  # JEEBench doesn't include solutions
        )

    def load(self) -> Generator[RawQuestion, None, None]:
        """
        Load and yield questions from JEEBench.

        Yields:
            RawQuestion objects
        """
        self._load_dataset()

        loaded = 0
        skipped = 0

        for row in self.dataset:
            try:
                # Filter by type - only MCQ for now
                q_type = row.get("type", "MCQ")
                if q_type != "MCQ":
                    skipped += 1
                    continue

                # Filter by subset if specified
                if self.subset:
                    row_subject = row.get("subject", "").lower()
                    subset_lower = self.subset.lower()

                    # Handle both short and long forms
                    if subset_lower in ["physics", "phy"]:
                        if row_subject != "phy":
                            continue
                    elif subset_lower in ["chemistry", "chem"]:
                        if row_subject != "chem":
                            continue
                    elif subset_lower in ["mathematics", "math", "maths"]:
                        if row_subject != "math":
                            continue

                question = self._parse_question(row)

                # Validate
                if self.validate_question(question):
                    loaded += 1
                    yield question
                else:
                    skipped += 1

            except Exception as e:
                print(f"Error parsing question: {e}")
                skipped += 1
                continue

        print(f"JEEBench: Loaded {loaded}, Skipped {skipped}")
