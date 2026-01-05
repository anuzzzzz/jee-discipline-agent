"""
Science-QnA Dataset Loader

Loads from HuggingFace: 169Pi/Science-QnA
5.63M questions covering Physics, Chemistry, Biology, Mathematics
JEE/NEET aligned content
"""

from typing import Generator, Dict, Any, Optional
from datasets import load_dataset

from ingestion.loaders.base import BaseLoader, RawQuestion


class ScienceQnALoader(BaseLoader):
    """
    Loader for 169Pi/Science-QnA dataset from HuggingFace.

    Massive dataset with 5.63M science questions.
    We filter for MCQ-style questions only.
    """

    name = "science_qna"

    def __init__(self, subject_filter: str = None, limit: int = 2000):
        """
        Initialize loader.

        Args:
            subject_filter: Filter by subject ("physics", "chemistry", "mathematics")
            limit: Max questions to load (default 2000 - dataset is huge!)
        """
        self.subject_filter = subject_filter
        self.limit = limit
        self.dataset = None

    def _load_dataset(self):
        """Load the dataset from HuggingFace."""
        if self.dataset is None:
            print("📥 Loading Science-QnA dataset from HuggingFace...")
            print("   (This is a large dataset - loading may take a moment)")

            # Stream to avoid loading entire 5.63M rows into memory
            self.dataset = load_dataset(
                "169Pi/Science-QnA",
                split="train",
                streaming=True  # Stream instead of loading all
            )
            print("   ✅ Dataset stream ready")

    def _detect_subject(self, text: str, category: str = "") -> str:
        """Detect subject from question text or category."""
        combined = (text + " " + category).lower()

        physics_keywords = ["force", "velocity", "acceleration", "mass", "energy",
                          "momentum", "electric", "magnetic", "wave", "optics",
                          "thermodynamic", "newton", "gravity", "circuit", "resistance"]

        chemistry_keywords = ["reaction", "compound", "element", "acid", "base",
                            "organic", "bond", "electron", "oxidation", "mole",
                            "solution", "atom", "molecule", "ion", "equilibrium"]

        math_keywords = ["integral", "derivative", "matrix", "equation", "function",
                        "limit", "probability", "vector", "triangle", "circle",
                        "polynomial", "calculus", "algebra", "geometry", "trigonometry"]

        physics_count = sum(1 for kw in physics_keywords if kw in combined)
        chemistry_count = sum(1 for kw in chemistry_keywords if kw in combined)
        math_count = sum(1 for kw in math_keywords if kw in combined)

        # Check category field first
        if "physics" in category.lower():
            return "physics"
        elif "chemistry" in category.lower():
            return "chemistry"
        elif "math" in category.lower():
            return "mathematics"
        elif "biology" in category.lower():
            return None  # Skip biology for JEE

        # Fall back to keyword detection
        if physics_count >= chemistry_count and physics_count >= math_count:
            return "physics"
        elif chemistry_count >= math_count:
            return "chemistry"
        elif math_count > 0:
            return "mathematics"

        return "physics"  # Default

    def _is_mcq(self, row: Dict) -> bool:
        """Check if the question is MCQ format."""
        text = str(row.get("question", "") or row.get("text", "")).lower()
        answer = str(row.get("answer", "") or row.get("response", ""))

        # Look for option markers
        has_options = any(marker in text for marker in ["(a)", "(b)", "(c)", "(d)",
                                                         "a)", "b)", "c)", "d)",
                                                         "option a", "option b"])

        # Or answer is a single letter
        is_letter_answer = answer.strip().upper() in ["A", "B", "C", "D"]

        return has_options or is_letter_answer

    def _extract_options(self, text: str) -> Dict[str, str]:
        """Try to extract options from question text."""
        import re

        options = {"A": "", "B": "", "C": "", "D": ""}

        # Common patterns
        patterns = [
            r'\(a\)\s*(.+?)(?=\(b\)|\(c\)|\(d\)|$)',
            r'\(A\)\s*(.+?)(?=\(B\)|\(C\)|\(D\)|$)',
            r'a\)\s*(.+?)(?=b\)|c\)|d\)|$)',
            r'A\)\s*(.+?)(?=B\)|C\)|D\)|$)',
            r'Option A[:\s]+(.+?)(?=Option B|$)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                for i, match in enumerate(matches[:4]):
                    key = ["A", "B", "C", "D"][i]
                    options[key] = match.strip()[:200]  # Limit length
                break

        return options

    def _parse_row(self, row: Dict[str, Any]) -> Optional[RawQuestion]:
        """Parse a row into RawQuestion format."""

        # Get question text
        question_text = str(row.get("question", "") or row.get("text", "") or row.get("input", ""))

        if len(question_text) < 20:
            return None

        # Get category/subject
        category = str(row.get("category", "") or row.get("subject", "") or row.get("topic", ""))
        subject = self._detect_subject(question_text, category)

        if subject is None:  # Skip biology
            return None

        # Filter by subject if specified
        if self.subject_filter and subject != self.subject_filter:
            return None

        # Get answer
        answer_text = str(row.get("answer", "") or row.get("response", "") or row.get("output", ""))

        # Try to extract correct option
        correct_option = "A"
        if answer_text.strip().upper() in ["A", "B", "C", "D"]:
            correct_option = answer_text.strip().upper()

        # Try to extract options from question text
        options = self._extract_options(question_text)

        # If no options found, this isn't an MCQ - skip
        if not any(options.values()):
            return None

        # Clean question text (remove options from it)
        clean_question = question_text
        for marker in ["(a)", "(b)", "(c)", "(d)", "(A)", "(B)", "(C)", "(D)"]:
            if marker in clean_question:
                clean_question = clean_question.split(marker)[0]

        return RawQuestion(
            question_text=clean_question.strip()[:1000],
            option_a=options["A"] or "Option A",
            option_b=options["B"] or "Option B",
            option_c=options["C"] or "Option C",
            option_d=options["D"] or "Option D",
            correct_option=correct_option,
            subject=subject,
            chapter=subject,
            topic=category[:50] if category else "general",
            difficulty=2,
            source="Science-QnA",
            solution=answer_text[:500] if len(answer_text) > 10 else "",
            is_pyq=False,
        )

    def load(self) -> Generator[RawQuestion, None, None]:
        """Load questions from the dataset."""
        self._load_dataset()

        loaded = 0
        skipped = 0

        print(f"📚 Processing Science-QnA (limit: {self.limit})...")

        for row in self.dataset:
            if loaded >= self.limit:
                break

            try:
                question = self._parse_row(row)

                if question and self.validate_question(question):
                    loaded += 1
                    yield question

                    if loaded % 100 == 0:
                        print(f"   Loaded {loaded}...")
                else:
                    skipped += 1

            except Exception as e:
                skipped += 1
                continue

        print(f"✅ Science-QnA: Loaded {loaded}, Skipped {skipped}")
