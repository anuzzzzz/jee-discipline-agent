"""
JEEBench Dataset Loader

Loads questions from the JEEBench dataset on HuggingFace.
Now includes conversion of numeric questions to MCQ format.
"""

from typing import Generator, Dict, Any, Optional
from datasets import load_dataset

from ingestion.loaders.base import BaseLoader, RawQuestion


# Mapping from JEEBench topics to our taxonomy
TOPIC_MAPPING = {
    # Physics
    "mechanics": ("physics", "mechanics", "general_mechanics"),
    "kinematics": ("physics", "mechanics", "kinematics"),
    "laws of motion": ("physics", "mechanics", "newtons_laws"),
    "work energy power": ("physics", "mechanics", "work_energy_power"),
    "rotational motion": ("physics", "mechanics", "rotational_mechanics"),
    "gravitation": ("physics", "mechanics", "gravitation"),
    "properties of matter": ("physics", "mechanics", "properties_of_matter"),
    "oscillations": ("physics", "waves", "simple_harmonic_motion"),
    "waves": ("physics", "waves", "wave_motion"),
    "heat and thermodynamics": ("physics", "thermodynamics", "heat_transfer"),
    "thermodynamics": ("physics", "thermodynamics", "laws_of_thermodynamics"),
    "electrostatics": ("physics", "electromagnetism", "electrostatics"),
    "current electricity": ("physics", "electromagnetism", "current_electricity"),
    "magnetic effects": ("physics", "electromagnetism", "magnetic_effects"),
    "electromagnetic induction": ("physics", "electromagnetism", "electromagnetic_induction"),
    "optics": ("physics", "optics", "ray_optics"),
    "modern physics": ("physics", "modern_physics", "photoelectric_effect"),
    "semiconductors": ("physics", "modern_physics", "semiconductors"),
    # Chemistry
    "atomic structure": ("chemistry", "physical_chemistry", "atomic_structure"),
    "chemical bonding": ("chemistry", "inorganic_chemistry", "chemical_bonding"),
    "states of matter": ("chemistry", "physical_chemistry", "states_of_matter"),
    "thermochemistry": ("chemistry", "physical_chemistry", "thermochemistry"),
    "equilibrium": ("chemistry", "physical_chemistry", "chemical_equilibrium"),
    "ionic equilibrium": ("chemistry", "physical_chemistry", "ionic_equilibrium"),
    "electrochemistry": ("chemistry", "physical_chemistry", "electrochemistry"),
    "chemical kinetics": ("chemistry", "physical_chemistry", "chemical_kinetics"),
    "solutions": ("chemistry", "physical_chemistry", "solutions"),
    "surface chemistry": ("chemistry", "physical_chemistry", "surface_chemistry"),
    "periodic table": ("chemistry", "inorganic_chemistry", "periodic_table"),
    "coordination compounds": ("chemistry", "inorganic_chemistry", "coordination_compounds"),
    "metallurgy": ("chemistry", "inorganic_chemistry", "metallurgy"),
    "organic chemistry": ("chemistry", "organic_chemistry", "general_organic"),
    "hydrocarbons": ("chemistry", "organic_chemistry", "hydrocarbons"),
    "organic compounds": ("chemistry", "organic_chemistry", "functional_groups"),
    "polymers": ("chemistry", "organic_chemistry", "polymers"),
    "biomolecules": ("chemistry", "organic_chemistry", "biomolecules"),
    # Mathematics
    "algebra": ("mathematics", "algebra", "general_algebra"),
    "quadratic equations": ("mathematics", "algebra", "quadratic_equations"),
    "complex numbers": ("mathematics", "algebra", "complex_numbers"),
    "matrices": ("mathematics", "algebra", "matrices_determinants"),
    "determinants": ("mathematics", "algebra", "matrices_determinants"),
    "permutations": ("mathematics", "algebra", "permutations_combinations"),
    "binomial theorem": ("mathematics", "algebra", "binomial_theorem"),
    "sequences": ("mathematics", "algebra", "sequences_series"),
    "calculus": ("mathematics", "calculus", "general_calculus"),
    "limits": ("mathematics", "calculus", "limits_continuity"),
    "differentiation": ("mathematics", "calculus", "differentiation"),
    "integration": ("mathematics", "calculus", "integration"),
    "differential equations": ("mathematics", "calculus", "differential_equations"),
    "coordinate geometry": ("mathematics", "coordinate_geometry", "straight_lines"),
    "straight lines": ("mathematics", "coordinate_geometry", "straight_lines"),
    "circles": ("mathematics", "coordinate_geometry", "circles"),
    "conic sections": ("mathematics", "coordinate_geometry", "conic_sections"),
    "vectors": ("mathematics", "vectors_3d", "vectors"),
    "3d geometry": ("mathematics", "vectors_3d", "three_dimensional_geometry"),
    "trigonometry": ("mathematics", "trigonometry", "trigonometric_functions"),
    "probability": ("mathematics", "probability_statistics", "probability"),
    "statistics": ("mathematics", "probability_statistics", "statistics"),
}


async def convert_numeric_to_mcq(question_text: str, answer: str, topic: str) -> Optional[Dict]:
    """
    Convert a numeric/integer answer question to MCQ format using LLM.

    Args:
        question_text: The question
        answer: The numeric answer
        topic: Topic for context

    Returns:
        Dict with option_a, option_b, option_c, option_d, correct_option
    """
    from app.services.llm import generate_json_response

    prompt = f"""Convert this numeric-answer JEE question to MCQ format.

Question: {question_text}
Correct Answer: {answer}
Topic: {topic}

Create 4 options where:
- One option is the correct answer ({answer})
- Three options are plausible wrong answers (common mistakes students make)
- Randomly place the correct answer among A, B, C, D

Return JSON only:
{{
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_option": "A/B/C/D",
    "solution": "Brief explanation of how to solve this"
}}"""

    try:
        result = await generate_json_response(prompt, model="gpt-4o-mini")
        if result and all(k in result for k in ["option_a", "option_b", "option_c", "option_d", "correct_option"]):
            return result
    except Exception as e:
        print(f"⚠️ Failed to convert numeric question: {e}")

    return None


class JEEBenchLoader(BaseLoader):
    """
    Loader for JEEBench dataset from HuggingFace.

    Now handles:
    - Standard MCQ questions
    - Integer/numeric type questions (converts to MCQ)
    """

    name = "jeebench"

    def __init__(self, subset: str = None, convert_numeric: bool = False):
        """
        Initialize loader.

        Args:
            subset: Optional subject filter ("phy", "chem", "math")
            convert_numeric: If True, convert numeric questions to MCQ (slower, uses LLM)
        """
        self.subset = subset
        self.convert_numeric = convert_numeric
        self.dataset = None

    def _load_dataset(self):
        """Load the dataset from HuggingFace."""
        if self.dataset is None:
            print("📥 Loading JEEBench dataset from HuggingFace...")
            self.dataset = load_dataset("daman1209arora/jeebench", split="test")
            print(f"   Loaded {len(self.dataset)} questions")

    def _map_topic(self, topic_str: str, subject: str) -> tuple:
        """Map JEEBench topic to our taxonomy."""
        topic_lower = topic_str.lower().strip()

        if topic_lower in TOPIC_MAPPING:
            return TOPIC_MAPPING[topic_lower]

        for key, value in TOPIC_MAPPING.items():
            if key in topic_lower or topic_lower in key:
                return value

        subject_lower = self.normalize_subject(subject)

        defaults = {
            "physics": ("physics", "mechanics", "general_mechanics"),
            "chemistry": ("chemistry", "physical_chemistry", "general"),
            "mathematics": ("mathematics", "algebra", "general_algebra"),
        }

        return defaults.get(subject_lower, ("physics", "mechanics", "general"))

    def _is_numeric_question(self, row: Dict) -> bool:
        """Check if question is numeric/integer type."""
        options = row.get("options", [])
        answer = row.get("answer", "")

        # No options = likely numeric
        if not options or len(options) < 4:
            return True

        # Answer is a number
        try:
            float(str(answer).strip())
            if len(options) < 4:
                return True
        except:
            pass

        return False

    def _parse_question(self, row: Dict[str, Any]) -> Optional[RawQuestion]:
        """Parse a single row into RawQuestion format."""

        subject_raw = row.get("subject", "physics")
        topic_raw = row.get("topic", "")

        subject, chapter, topic = self._map_topic(topic_raw, subject_raw)

        # Parse options
        options = row.get("options", [])

        if isinstance(options, list) and len(options) >= 4:
            option_a = str(options[0])
            option_b = str(options[1])
            option_c = str(options[2])
            option_d = str(options[3])
        else:
            option_a = str(row.get("option_a", row.get("A", "")))
            option_b = str(row.get("option_b", row.get("B", "")))
            option_c = str(row.get("option_c", row.get("C", "")))
            option_d = str(row.get("option_d", row.get("D", "")))

        # Parse correct answer
        correct = row.get("answer", row.get("correct_option", "A"))
        correct_option = self.normalize_option(str(correct))

        solution = row.get("solution", row.get("explanation", ""))
        difficulty = row.get("difficulty", 3)

        return RawQuestion(
            question_text=str(row.get("question", row.get("problem", ""))),
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_option=correct_option,
            subject=subject,
            chapter=chapter,
            topic=topic,
            difficulty=difficulty,
            source="JEEBench",
            source_id=str(row.get("id", "")),
            year=row.get("year"),
            is_pyq=True,
            solution=str(solution) if solution else "",
        )

    async def _parse_numeric_question(self, row: Dict[str, Any]) -> Optional[RawQuestion]:
        """Parse a numeric question by converting to MCQ."""
        subject_raw = row.get("subject", "physics")
        topic_raw = row.get("topic", "")

        subject, chapter, topic = self._map_topic(topic_raw, subject_raw)

        question_text = str(row.get("question", row.get("problem", "")))
        answer = str(row.get("answer", ""))

        # Convert to MCQ using LLM
        mcq_data = await convert_numeric_to_mcq(question_text, answer, topic)

        if not mcq_data:
            return None

        return RawQuestion(
            question_text=question_text,
            option_a=mcq_data["option_a"],
            option_b=mcq_data["option_b"],
            option_c=mcq_data["option_c"],
            option_d=mcq_data["option_d"],
            correct_option=mcq_data["correct_option"],
            subject=subject,
            chapter=chapter,
            topic=topic,
            difficulty=row.get("difficulty", 3),
            source="JEEBench_Converted",
            source_id=str(row.get("id", "")),
            year=row.get("year"),
            is_pyq=True,
            solution=mcq_data.get("solution", ""),
        )

    def load(self) -> Generator[RawQuestion, None, None]:
        """Load and yield MCQ questions from JEEBench."""
        self._load_dataset()

        loaded = 0
        skipped = 0

        for row in self.dataset:
            try:
                if self.subset:
                    row_subject = row.get("subject", "").lower()
                    if self.subset.lower() not in row_subject:
                        continue

                # Skip numeric questions in sync mode
                if self._is_numeric_question(row):
                    skipped += 1
                    continue

                question = self._parse_question(row)

                if question and self.validate_question(question):
                    loaded += 1
                    yield question
                else:
                    skipped += 1

            except Exception as e:
                print(f"⚠️ Error parsing question: {e}")
                skipped += 1
                continue

        print(f"✅ JEEBench: Loaded {loaded}, Skipped {skipped}")

    async def load_with_conversion(self) -> Generator[RawQuestion, None, None]:
        """Load ALL questions, converting numeric ones to MCQ."""
        self._load_dataset()

        loaded = 0
        converted = 0
        skipped = 0

        for row in self.dataset:
            try:
                if self.subset:
                    row_subject = row.get("subject", "").lower()
                    if self.subset.lower() not in row_subject:
                        continue

                if self._is_numeric_question(row):
                    # Convert numeric to MCQ
                    question = await self._parse_numeric_question(row)
                    if question and self.validate_question(question):
                        converted += 1
                        yield question
                    else:
                        skipped += 1
                else:
                    # Standard MCQ
                    question = self._parse_question(row)
                    if question and self.validate_question(question):
                        loaded += 1
                        yield question
                    else:
                        skipped += 1

            except Exception as e:
                print(f"⚠️ Error: {e}")
                skipped += 1
                continue

        print(f"✅ JEEBench: Loaded {loaded}, Converted {converted}, Skipped {skipped}")
