import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.messages import ModelMessage as PydanticChatMessage

from shared.base_agent import BaseAgent, AgentConfig, AgentRequest, AgentResponse
from agents.litellm_compat import create_litellm_compatible_client


class ChatAgent(BaseAgent):
    """Chat agent implementation with hybrid session memory support."""

    async def initialize(self, http_client: httpx.AsyncClient | None = None):
        # Use provided http_client or create a new one
        client = http_client or create_litellm_compatible_client()

        openai_client = AsyncOpenAI(
            api_key=self.config.extra.get("api_key"),
            base_url=self.config.extra.get("base_url"),
            http_client=client,
        )
        provider = OpenAIProvider(openai_client=openai_client)
        model = OpenAIChatModel(self.config.model, provider=provider)

        # Don't set static system_prompt here - we'll create dynamic system messages
        # in process() that combine the static prompt with session context
        self.agent = Agent(model)
        # Only store http_client if we created it ourselves
        if http_client is None:
            self.http_client = client
        else:
            self.http_client = None

    def _convert_history(
        self, history: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Convert stored history dicts into simple role/content dicts.

        Stored messages are simple dicts: {\"role\": ..., \"content\": ..., \"timestamp\": ...}.
        """
        if not history:
            return []

        converted: List[Dict[str, Any]] = []
        for msg in history:
            role = msg.get("role") or "user"
            content = msg.get("content") or ""
            if not content:
                continue

            # pydantic_ai Agent accepts message_history as list of role/content-like items;
            # we keep this as plain dicts to avoid tight coupling to internal message classes.
            converted.append({"role": role, "content": content})
        return converted

    def _extract_user_signals(
        self, message: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Extract simple structured signals (name, language, age, location, interests, etc.) from user message.

        Returns (context_updates, user_prefs_updates) dictionaries.
        This is intentionally simple/regex-based for now.
        """
        context_updates: Dict[str, Any] = {}
        prefs_updates: Dict[str, Any] = {}

        text = message.strip()
        lowered = text.lower()

        # ==================== NAME EXTRACTION ====================
        # Very simple Persian and English patterns for name
        if "من " in text and ("هستم" in text or "ام" in text):
            # e.g. "من محمد هستم" / "من محمدم"
            try:
                after_man = text.split("من", 1)[1].strip()
                # remove trailing punctuation
                after_man = (
                    after_man.replace("هستم", "")
                    .replace("ام", "")
                    .replace(".", "")
                    .strip()
                )
                if after_man:
                    context_updates["user_name"] = {"value": after_man}
            except Exception:
                pass

        if "اسم من" in text or "نام من" in text:
            # e.g. "اسم من محمد است" or "نام من محمد است"
            # BUT NOT "اسم من چیه" (which is a question, not a statement)
            try:
                separator = "اسم من" if "اسم من" in text else "نام من"
                after_esme = text.split(separator, 1)[1].strip()
                after_esme = (
                    after_esme.replace("است", "")
                    .replace("هست", "")
                    .replace(".", "")
                    .replace("هستش", "")
                    .strip()
                )
                # Exclude question words - these indicate the user is ASKING for their name, not stating it
                question_words = ["چیه", "چیست", "چیه؟", "چیست؟", "چیه", "چی", "چی؟"]
                if after_esme and after_esme not in question_words:
                    context_updates["user_name"] = {"value": after_esme}
            except Exception:
                pass

        if "my name is" in lowered:
            try:
                after = lowered.split("my name is", 1)[1].strip()
                # take first token as simple name
                name = after.split()[0].strip(".,!?")
                if name:
                    context_updates["user_name"] = {"value": name}
            except Exception:
                pass

        if lowered.startswith("i am ") or lowered.startswith("i'm "):
            try:
                separator = "i'm " if lowered.startswith("i'm ") else "i am "
                name = lowered.split(separator, 1)[1].strip().split()[0].strip(".,!?")
                if name and name not in ["a", "an", "the", "from"]:
                    context_updates["user_name"] = {"value": name}
            except Exception:
                pass

        # ==================== AGE EXTRACTION ====================
        # Persian: "من ۲۵ سالمه" / "سنم ۲۵ است" / "۲۵ سال دارم"
        if "سالمه" in text or "سال دارم" in text or "سنم" in text:
            try:
                import re
                # Look for Persian and English digits
                age_match = re.search(r'(\d+|[۰-۹]+)', text)
                if age_match:
                    age_str = age_match.group(1)
                    # Convert Persian digits to English
                    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
                    age_str = age_str.translate(persian_to_english)
                    age = int(age_str)
                    if 1 <= age <= 120:  # Sanity check
                        context_updates["user_age"] = {"value": age}
            except Exception:
                pass

        # English: "I am 25 years old" / "I'm 25" / "my age is 25"
        if "years old" in lowered or "year old" in lowered or "my age is" in lowered:
            try:
                import re
                age_match = re.search(r'\b(\d+)\b', lowered)
                if age_match:
                    age = int(age_match.group(1))
                    if 1 <= age <= 120:
                        context_updates["user_age"] = {"value": age}
            except Exception:
                pass

        # ==================== LOCATION/CITY EXTRACTION ====================
        # Persian: "من از تهران هستم" / "اهل تهرانم" / "در تهران زندگی می‌کنم"
        city_patterns_fa = ["من از", "اهل", "در", "زندگی می‌کنم", "ساکن"]
        location_keywords = ["هستم", "ام", "زندگی می‌کنم", "زندگی میکنم"]

        for pattern in city_patterns_fa:
            if pattern in text:
                try:
                    parts = text.split(pattern, 1)
                    if len(parts) > 1:
                        after_pattern = parts[1].strip()
                        # Extract first word/phrase before location keywords
                        for keyword in location_keywords:
                            if keyword in after_pattern:
                                city = after_pattern.split(keyword)[0].strip()
                                if city:
                                    context_updates["user_location"] = {"value": city}
                                    break
                except Exception:
                    pass

        # English: "I am from Tehran" / "I live in Tehran"
        if "i am from" in lowered or "i'm from" in lowered or "i live in" in lowered:
            try:
                separator = None
                if "i'm from" in lowered:
                    separator = "i'm from"
                elif "i am from" in lowered:
                    separator = "i am from"
                elif "i live in" in lowered:
                    separator = "i live in"

                if separator:
                    after = lowered.split(separator, 1)[1].strip()
                    city = after.split()[0].strip(".,!?") if after else None
                    if city:
                        context_updates["user_location"] = {"value": city}
            except Exception:
                pass

        # ==================== OCCUPATION/JOB EXTRACTION ====================
        # Persian: "من برنامه‌نویسم" / "شغلم معلمی است" / "من یک پزشک هستم"
        if "شغلم" in text or "کارم" in text:
            try:
                separator = "شغلم" if "شغلم" in text else "کارم"
                after = text.split(separator, 1)[1].strip()
                job = after.replace("است", "").replace("هست", "").replace(".", "").strip()
                if job:
                    context_updates["user_occupation"] = {"value": job}
            except Exception:
                pass

        # English: "I am a teacher" / "I work as a developer" / "my job is"
        if "i work as" in lowered or "my job is" in lowered or "i am a" in lowered:
            try:
                separator = None
                if "i work as" in lowered:
                    separator = "i work as"
                elif "my job is" in lowered:
                    separator = "my job is"
                elif "i am a" in lowered:
                    separator = "i am a"

                if separator:
                    after = lowered.split(separator, 1)[1].strip()
                    job = after.split()[0].strip(".,!?") if after else None
                    if job and job not in ["a", "an", "the"]:
                        context_updates["user_occupation"] = {"value": job}
            except Exception:
                pass

        # ==================== INTERESTS/HOBBIES EXTRACTION ====================
        # Persian: "من به فوتبال علاقه دارم" / "دوست دارم کتاب بخونم"
        if "علاقه دارم" in text or "دوست دارم" in text:
            try:
                separator = "علاقه دارم" if "علاقه دارم" in text else "دوست دارم"
                # Get the part before the separator (what they like)
                before = text.split(separator, 0)[0] if "به" in text else None
                if before and "به" in before:
                    interest = before.split("به", 1)[1].strip()
                    if interest:
                        # Get existing interests or create new list
                        existing = context_updates.get("user_interests", {"value": []})
                        interests_list = existing.get("value", []) if isinstance(existing, dict) else []
                        if interest not in interests_list:
                            interests_list.append(interest)
                        context_updates["user_interests"] = {"value": interests_list}
            except Exception:
                pass

        # English: "I like football" / "I love reading" / "I enjoy"
        if "i like" in lowered or "i love" in lowered or "i enjoy" in lowered:
            try:
                separator = None
                if "i like" in lowered:
                    separator = "i like"
                elif "i love" in lowered:
                    separator = "i love"
                elif "i enjoy" in lowered:
                    separator = "i enjoy"

                if separator:
                    after = lowered.split(separator, 1)[1].strip()
                    interest = after.split()[0].strip(".,!?") if after else None
                    if interest and interest not in ["a", "an", "the", "to"]:
                        existing = context_updates.get("user_interests", {"value": []})
                        interests_list = existing.get("value", []) if isinstance(existing, dict) else []
                        if interest not in interests_list:
                            interests_list.append(interest)
                        context_updates["user_interests"] = {"value": interests_list}
            except Exception:
                pass

        # ==================== LANGUAGE PREFERENCE ====================
        # Preferred language (very simple signals)
        if "با من فارسی حرف بزن" in text or "فارسی صحبت کن" in text:
            context_updates["preferred_language"] = {"value": "fa"}

        if "speak english" in lowered or "talk to me in english" in lowered:
            context_updates["preferred_language"] = {"value": "en"}
        
        # Arabic language preference
        if "عربی" in text or "عربي" in text or "arabic" in lowered:
            # Check if it's a request to speak Arabic (not just mentioning the word)
            if any(phrase in text for phrase in [
                "به عربی", "به عربي", "عربی جواب", "عربي جواب",
                "از این به بعد به عربی", "از این به بعد به عربي",
                "speak arabic", "answer in arabic", "reply in arabic"
            ]):
                context_updates["preferred_language"] = {"value": "ar"}

        if context_updates:
            prefs_updates["user_prefs"] = context_updates

        return context_updates, prefs_updates

    async def process(
        self,
        request: AgentRequest,
        history: Optional[List[Dict[str, Any]]] = None,
        shared_context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        # Convert persisted history into pydantic_ai format
        message_history = self._convert_history(history)

        # Extract structured signals from latest user message
        context_updates, prefs_updates = self._extract_user_signals(request.message)

        # Build context-aware view by merging existing context
        merged_context: Dict[str, Any] = {}
        if shared_context:
            merged_context.update(shared_context)
        merged_context.update(context_updates)
        merged_context.update(prefs_updates)

        # Helper: extract plain user_name from merged context (if any)
        def _extract_name_from_context(ctx: Dict[str, Any]) -> Optional[str]:
            if "user_name" not in ctx:
                return None
            raw = ctx["user_name"]
            if isinstance(raw, dict):
                return (raw.get("value") or "").strip() or None
            return str(raw).strip() or None

        user_name_value = _extract_name_from_context(merged_context)

        # Build a combined system message that includes:
        # 1. The static system prompt from config
        # 2. Dynamic session context (user name, age, location, occupation, interests, language, etc.)
        # 3. Summary of the last 1-2 conversation turns
        # Trust the LLM to use this context appropriately - it has a large context window!

        # Start with the static system prompt
        static_prompt = self.config.extra.get("system_prompt", "")

        # Build dynamic context information from all available user data
        context_info: List[str] = []

        # Extract all user context fields
        if user_name_value:
            context_info.append(f"نام کاربر: {user_name_value}")

        # Age
        user_age = merged_context.get("user_age")
        if user_age:
            age_value = user_age.get("value") if isinstance(user_age, dict) else user_age
            if age_value:
                context_info.append(f"سن: {age_value}")

        # Location
        user_location = merged_context.get("user_location")
        if user_location:
            location_value = user_location.get("value") if isinstance(user_location, dict) else user_location
            if location_value:
                context_info.append(f"موقعیت: {location_value}")

        # Occupation
        user_occupation = merged_context.get("user_occupation")
        if user_occupation:
            occupation_value = user_occupation.get("value") if isinstance(user_occupation, dict) else user_occupation
            if occupation_value:
                context_info.append(f"شغل: {occupation_value}")

        # Interests
        user_interests = merged_context.get("user_interests")
        if user_interests:
            interests_value = user_interests.get("value") if isinstance(user_interests, dict) else user_interests
            if interests_value:
                if isinstance(interests_value, list):
                    interests_str = "، ".join(str(i) for i in interests_value)
                    context_info.append(f"علایق: {interests_str}")
                else:
                    context_info.append(f"علایق: {interests_value}")

        # Preferred Language
        preferred_lang = merged_context.get("preferred_language")
        if preferred_lang:
            if isinstance(preferred_lang, dict):
                lang_value = (preferred_lang.get("value") or "").strip()
            else:
                lang_value = str(preferred_lang).strip()
            if lang_value:
                context_info.append(f"زبان ترجیحی: {lang_value}")

        # Add summary of last 1-2 conversation turns
        recent_conversation: List[str] = []
        if history and len(history) > 0:
            # Get the last 2-4 messages (1-2 complete turns: user + assistant pairs)
            last_messages = history[-4:] if len(history) >= 4 else history[-2:] if len(history) >= 2 else history

            for msg in last_messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    role_label = "کاربر" if role == "user" else "دستیار" if role == "assistant" else role
                    # Truncate long messages
                    truncated_content = content[:100] + "..." if len(content) > 100 else content
                    recent_conversation.append(f"{role_label}: {truncated_content}")

        # Combine static prompt with dynamic context
        system_parts = []
        if static_prompt:
            system_parts.append(static_prompt)

        if context_info:
            system_parts.append("📋 اطلاعات کاربر:\n" + "\n".join(context_info))

        if recent_conversation:
            system_parts.append("💬 خلاصه گفتگوی اخیر:\n" + "\n".join(recent_conversation))

        # Create the combined system message
        if system_parts:
            combined_system_message = "\n\n".join(system_parts)
            # Insert or update system message at the beginning of history
            if not message_history or message_history[0].get("role") != "system":
                message_history.insert(
                    0, {"role": "system", "content": combined_system_message}
                )
            else:
                # Update existing system message
                message_history[0]["content"] = combined_system_message

        # Always use the LLM - trust it to use the context properly!
        result = await self.agent.run(
            request.message,
            message_history=message_history,
        )
        assistant_output = result.output

        # Append latest turn to history so caller can persist it
        updated_history: List[Dict[str, Any]] = history.copy() if history else []
        now_iso = datetime.datetime.utcnow().isoformat()
        updated_history.append(
            {
                "role": "user",
                "content": request.message,
                "timestamp": now_iso,
            }
        )
        updated_history.append(
            {
                "role": "assistant",
                "content": assistant_output,
                "timestamp": now_iso,
            }
        )

        # Merge all metadata/context updates so caller can persist them
        metadata: Dict[str, Any] = {
            "model": self.config.model,
            "history": updated_history,
        }

        context_updates_combined: Dict[str, Any] = {}
        if shared_context:
            context_updates_combined.update(shared_context)
        # context_updates are fine-grained keys like user_name, preferred_language
        context_updates_combined.update(context_updates)
        # prefs_updates can be a higher-level aggregation under user_prefs
        context_updates_combined.update(prefs_updates)

        return AgentResponse(
            session_id=request.session_id,
            output=assistant_output,
            metadata=metadata,
            context_updates=context_updates_combined,
        )

    def get_capabilities(self) -> list[str]:
        return ["chat", "conversation", "qa"]
