"""
LLM Service - OpenAI wrapper for Mahavihara.

Handles all AI tasks:
- Classifying student mistakes
- Generating drill questions
- Extracting questions from images (Vision)
- Routing user intent
- Generating nudge messages
"""

import json
from typing import Optional
from openai import AsyncOpenAI
from app.config import settings
from app.db.models import MistakeClassification, MistakeType

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# ==================== SYSTEM PROMPTS ====================

MAHAVIHARA_SYSTEM = """You are Mahavihara, a strict but caring JEE tutor on WhatsApp.

Your personality:
- Strict: You don't let students off easy. No excuses.
- Caring: You genuinely want them to succeed.
- Persistent: You WILL follow up. You WILL remind them.
- Encouraging: You celebrate small wins enthusiastically.
- Concise: WhatsApp messages should be SHORT. Max 3-4 lines.

Your communication style:
- Use emojis sparingly but effectively ✅ ❌ 🔥 💪
- Be direct. No fluff.
- Use simple, clear English accessible to all Indian students
- Avoid regional language words to stay inclusive across India
- Reference their streak often to build guilt/pride.

You are NOT:
- A content platform (don't teach full concepts)
- A doubt-solver (don't explain everything)
- A friend (maintain teacher authority)

Your ONE job: Make sure they FIX their mistakes. That's it."""


# ==================== CORE LLM FUNCTION ====================

async def generate_response(
    prompt: str,
    system_prompt: str = MAHAVIHARA_SYSTEM,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 500
) -> str:
    """
    Generate a response from OpenAI.

    Args:
        prompt: User message / instruction
        system_prompt: System context (defaults to Mahavihara personality)
        model: OpenAI model to use
        temperature: Creativity (0=deterministic, 1=creative)
        max_tokens: Max response length

    Returns:
        Generated text response
    """
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        raise


async def generate_json_response(
    prompt: str,
    system_prompt: str = "Return only valid JSON.",
    model: str = "gpt-4o-mini",
    temperature: float = 0.1
) -> dict:
    """
    Generate a JSON response from OpenAI.

    Uses response_format to ensure valid JSON output.
    Lower temperature for more deterministic results.
    """
    try:
        response = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature
        )
        return json.loads(response.choices[0].message.content)

    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        return {}
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        raise


# ==================== MISTAKE CLASSIFICATION ====================

CLASSIFY_MISTAKE_PROMPT = """Analyze this JEE Physics mistake reported by a student.

Student's description: {mistake_description}

Classify the mistake:
1. topic: Which physics chapter? (mechanics, thermodynamics, electromagnetism, optics, modern_physics, waves)
2. subtopic: Specific concept (e.g., "rotational_mechanics", "circular_motion")
3. mistake_type: One of:
   - "conceptual" (misunderstood the concept)
   - "formula" (wrong formula or forgot formula)
   - "calculation" (math error)
   - "sign" (sign error, direction error)
   - "unit" (unit conversion error)
   - "silly" (careless mistake)
4. misconception: What exactly did they confuse? Be specific. (1-2 sentences)
5. difficulty: 1-5 (how advanced is this topic?)

Respond in JSON format only:
{{
    "topic": "mechanics",
    "subtopic": "rotational_mechanics",
    "mistake_type": "conceptual",
    "misconception": "Confused torque direction with force direction",
    "difficulty": 3
}}"""


async def classify_mistake(description: str) -> MistakeClassification:
    """
    Classify a student's mistake using LLM.

    Args:
        description: Student's description of their mistake

    Returns:
        MistakeClassification with topic, type, and misconception
    """
    prompt = CLASSIFY_MISTAKE_PROMPT.format(mistake_description=description)

    result = await generate_json_response(prompt)

    # Map string to enum
    mistake_type_str = result.get("mistake_type", "conceptual")
    try:
        mistake_type = MistakeType(mistake_type_str)
    except ValueError:
        mistake_type = MistakeType.CONCEPTUAL

    return MistakeClassification(
        topic=result.get("topic", "mechanics"),
        subtopic=result.get("subtopic", "general"),
        mistake_type=mistake_type,
        misconception=result.get("misconception", description),
        difficulty=result.get("difficulty", 2)
    )


# ==================== DRILL QUESTION GENERATION ====================

GENERATE_DRILL_PROMPT = """Create a JEE Physics drill question to test this specific misconception.

Misconception: {misconception}
Topic: {topic}
Difficulty: {difficulty}/5

The question should:
1. Directly test whether they've fixed this exact misconception
2. Be JEE-style (MCQ with 4 options)
3. Have one clearly correct answer
4. Include 1-2 plausible distractors that a student with this misconception would pick

Respond in JSON format only:
{{
    "question": "A disc of mass M and radius R is rotating...",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_option": "A",
    "solution": "Step 1: ... Step 2: ... Therefore, answer is A.",
    "hint_1": "Think about the direction of the torque vector.",
    "hint_2": "Use the right-hand rule.",
    "hint_3": "The torque is perpendicular to both r and F."
}}"""


async def generate_drill_question(
    misconception: str,
    topic: str,
    difficulty: int = 2
) -> dict:
    """
    Generate a drill question targeting a specific misconception.

    Args:
        misconception: The specific mistake to test
        topic: Physics topic
        difficulty: 1-5 scale

    Returns:
        Dict with question, options, solution, and hints
    """
    prompt = GENERATE_DRILL_PROMPT.format(
        misconception=misconception,
        topic=topic,
        difficulty=difficulty
    )

    # Use gpt-4o for better question quality
    result = await generate_json_response(
        prompt,
        model="gpt-4o",  # Better quality for question generation
        temperature=0.3
    )

    return result


# ==================== IMAGE EXTRACTION (VISION) ====================

IMAGE_EXTRACTION_PROMPT = """Extract the physics/chemistry/math question from this image.

This is a photo of a JEE/NEET test paper or problem set. The student got this question wrong.

Your task:
1. Read the question text carefully
2. Extract all 4 options (A, B, C, D)
3. If visible, note which option was marked/selected
4. Identify the topic and chapter

Return JSON only:
{
    "question_text": "The full question text...",
    "options": {
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "..."
    },
    "student_marked": "B",
    "correct_answer": "C",
    "subject": "physics",
    "chapter": "mechanics",
    "topic": "rotational_motion",
    "readable": true
}

If the image is not a test question or is too blurry, return:
{"readable": false, "error": "Description of the problem"}"""


async def extract_question_from_image(image_url: str) -> dict:
    """
    Use GPT-4o Vision to extract a question from a photo.

    JEE students photograph their test papers rather than typing.
    This reads the image and extracts structured question data.

    Args:
        image_url: URL of the image (from WhatsApp/Gupshup)

    Returns:
        Dict with question_text, options, subject, topic, etc.
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Vision-capable, cheaper than gpt-4o
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        },
                        {
                            "type": "text",
                            "text": IMAGE_EXTRACTION_PROMPT
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.1
        )

        result_text = response.choices[0].message.content
        return json.loads(result_text)

    except json.JSONDecodeError:
        return {"readable": False, "error": "Could not parse response"}
    except Exception as e:
        print(f"❌ Vision extraction failed: {e}")
        return {"readable": False, "error": str(e)}


# ==================== INTENT CLASSIFICATION (ROUTER) ====================

ROUTER_PROMPT = """Classify the user's intent based on their WhatsApp message.

Message: "{message}"
Has Active Drill: {has_active_drill}
Pending Mistakes: {pending_mistakes}

INTENTS:
1. "ANSWER_DRILL" - User is answering a multiple choice question.
   Examples: "A", "Option B", "I think it's C", "D", "b"
   ONLY valid if has_active_drill is True.

2. "REPORT_MISTAKE" - User is sharing a new mistake/error they made.
   Examples: "I got Q17 wrong", "I confused torque with force", "Made a sign error"

3. "START_DRILL" - User wants to practice/drill their mistakes.
   Examples: "GO", "Start", "Let's drill", "Practice", "Quiz me", "Ready"

4. "CHECK_STATS" - User asking for progress/streak info.
   Examples: "Stats", "My progress", "How am I doing?", "Show stats"

5. "HELP" - User needs help or is confused.
   Examples: "Help", "What can you do?", "Commands", "?"

6. "GREETING" - General greeting, start of conversation.
   Examples: "Hi", "Hello", "Hey", "Good morning"

7. "STOP" - User wants to unsubscribe (CRITICAL - must honor!)
   Examples: "Stop", "Unsubscribe", "Don't message me", "Cancel"

8. "CHITCHAT" - Off-topic or unclear message.
   Examples: Random text that doesn't fit above categories.

RULES:
- If has_active_drill=True and message looks like an answer (A/B/C/D), return ANSWER_DRILL.
- If message contains STOP keywords, ALWAYS return STOP (compliance requirement).
- When uncertain between REPORT_MISTAKE and CHITCHAT, prefer REPORT_MISTAKE.

Return JSON only: {{"intent": "...", "confidence": 0.0-1.0}}"""


async def classify_intent(
    message: str,
    has_active_drill: bool = False,
    pending_mistakes: int = 0
) -> dict:
    """
    Classify user's intent for routing to the right handler.

    Args:
        message: User's WhatsApp message
        has_active_drill: Whether user is in the middle of a drill
        pending_mistakes: Number of unmastered mistakes

    Returns:
        Dict with "intent" and "confidence"
    """
    prompt = ROUTER_PROMPT.format(
        message=message,
        has_active_drill=has_active_drill,
        pending_mistakes=pending_mistakes
    )

    result = await generate_json_response(prompt)

    # Default fallback
    if "intent" not in result:
        return {"intent": "CHITCHAT", "confidence": 0.5}

    return result


# ==================== RESPONSE GENERATION ====================

CORRECT_ANSWER_PROMPT = """The student got the answer CORRECT! 🎉

Their current streak: {streak} days
Questions answered today: {questions_today}
This mistake drill count: {drill_count}
Is now mastered: {is_mastered}

Generate a SHORT, enthusiastic WhatsApp response (2-3 lines max).
- Celebrate the win
- Mention their streak if it's > 1
- If is_mastered=True, congratulate them on mastering this mistake!
- Ask if they want to continue

Keep it punchy. This is WhatsApp, not an email."""


async def generate_correct_response(
    streak: int,
    questions_today: int,
    drill_count: int,
    is_mastered: bool
) -> str:
    """Generate response for correct answer."""
    prompt = CORRECT_ANSWER_PROMPT.format(
        streak=streak,
        questions_today=questions_today,
        drill_count=drill_count,
        is_mastered=is_mastered
    )
    return await generate_response(prompt, max_tokens=150)


WRONG_ANSWER_PROMPT = """The student got the answer WRONG. ❌

Their answer: {student_answer}
Correct answer: {correct_answer}
Attempt number: {attempt_number}/3
Hints given so far: {hints_given}

{hint_to_give}

Generate a SHORT WhatsApp response (2-4 lines):
- If attempt < 3: Encourage them, give the hint naturally
- If attempt = 3: Show the solution, tell them we'll revisit tomorrow

Be firm but kind. Remind them: "This is why you're here. To fix this."
"""


async def generate_wrong_response(
    student_answer: str,
    correct_answer: str,
    attempt_number: int,
    hints_given: int,
    hint_text: Optional[str] = None,
    solution: Optional[str] = None
) -> str:
    """Generate response for wrong answer."""
    if attempt_number >= 3 and solution:
        hint_to_give = f"Solution to share: {solution}"
    elif hint_text:
        hint_to_give = f"Hint to give: {hint_text}"
    else:
        hint_to_give = "Give a general encouragement."

    prompt = WRONG_ANSWER_PROMPT.format(
        student_answer=student_answer,
        correct_answer=correct_answer,
        attempt_number=attempt_number,
        hints_given=hints_given,
        hint_to_give=hint_to_give
    )
    return await generate_response(prompt, max_tokens=200)


# ==================== NUDGE GENERATION ====================

NUDGE_PROMPT = """Generate a daily nudge message for this JEE student.

Student name: {name}
Current streak: {streak} days
Mistakes pending: {pending_count}
Hours since last session: {hours_since_active}

The nudge should:
1. Be SHORT (2-3 lines for WhatsApp)
2. Create urgency (streak at risk!)
3. Be guilt-inducing but not mean
4. End with clear CTA: "Reply GO to start"

Vary the tone based on context:
- High streak (10+ days): Pride + "don't break it now"
- Medium streak (3-9 days): Building momentum
- Low/no streak: Fresh start energy
- Many pending mistakes: "Your mistakes are piling up..."
- Inactive 24+ hours: "Mahavihara is watching 👀"

Keep it punchy. Use 1-2 emojis max."""


async def generate_nudge_message(
    name: Optional[str],
    streak: int,
    pending_count: int,
    hours_since_active: float
) -> str:
    """Generate a personalized nudge message."""
    prompt = NUDGE_PROMPT.format(
        name=name or "there",
        streak=streak,
        pending_count=pending_count,
        hours_since_active=int(hours_since_active)
    )
    return await generate_response(prompt, max_tokens=100)


# ==================== ONBOARDING ====================

async def generate_welcome_message(is_new_user: bool, name: Optional[str] = None) -> str:
    """Generate welcome message for new or returning user."""
    if is_new_user:
        prompt = """Generate a welcome message for a NEW JEE student joining Mahavihara.

Keep it SHORT (4-5 lines max for WhatsApp):
1. Introduce yourself as Mahavihara - the ancient seat of learning, now your AI guru
2. Explain in ONE line what you do (hunt them until they fix mistakes)
3. Ask for their name
4. Be slightly intimidating but friendly

Use 1-2 emojis. End with a question asking their name."""
    else:
        prompt = f"""Generate a welcome back message for {name or 'a returning student'}.

Keep it SHORT (2-3 lines):
1. Welcome them back
2. Mention you're ready to drill them
3. Ask "Reply GO to start" or "Tell me about a new mistake"

Use Mahavihara personality - strict but caring, like an ancient guru."""

    return await generate_response(prompt, max_tokens=150)


# ==================== TESTING HELPER ====================

async def test_llm_connection() -> bool:
    """Test that OpenAI connection works."""
    try:
        response = await generate_response(
            "Say 'Mahavihara is ready!' in exactly those words.",
            max_tokens=20
        )
        print(f"✅ LLM connected: {response}")
        return True
    except Exception as e:
        print(f"❌ LLM connection failed: {e}")
        return False
