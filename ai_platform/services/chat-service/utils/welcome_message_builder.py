"""
Build context-aware welcome messages and conversation starters based on agent and path.
"""
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def _first_name_from_user_data(user_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract first name from user data (fullName or full_name). Returns None if not available."""
    if not user_data or not isinstance(user_data, dict):
        return None
    full = user_data.get("fullName") or user_data.get("full_name") or user_data.get("user_full_name")
    if isinstance(full, dict) and "value" in full:
        full = full.get("value")
    if not full or not isinstance(full, str) or not full.strip():
        return None
    parts = full.strip().split()
    return parts[0] if parts else None


def _greeting_prefix(first_name: Optional[str]) -> str:
    """Return personalized greeting prefix: 'سلام محمد!' or 'سلام!'"""
    if first_name:
        return f"سلام {first_name}!"
    return "سلام!"


def get_welcome_message_and_starters(
    agent_key: str,
    entry_path: Optional[str] = None,
    user_data: Optional[Dict[str, Any]] = None,
    action_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate welcome message and conversation starters based on agent and path context.
    
    Args:
        agent_key: Agent identifier (guest_faq, action_expert, journey_register, etc.)
        entry_path: Path where user came from (e.g., "/actions/40", "/register", "/action-list")
        user_data: Optional user data (to check if user is logged in, etc.)
        action_details: Optional action payload from /api/Home/GetOneAction
    
    Returns:
        Dict with:
            - welcome_message: Main welcome text
            - conversation_starters: List of suggested conversation starters
            - subtitle: Optional subtitle for UI
    """
    # Normalize entry_path
    if entry_path:
        entry_path = entry_path.strip()
        if not entry_path.startswith("/"):
            entry_path = "/" + entry_path
    
    # Check if user is logged in (has user_id in user_data)
    is_logged_in = False
    if user_data:
        is_logged_in = bool(user_data.get("userId") or user_data.get("user_id"))
    
    # Extract action ID if path contains /actions/{id}
    action_id = None
    if entry_path and "/actions/" in entry_path:
        import re
        match = re.search(r'/actions/(\d+)', entry_path)
        if match:
            action_id = match.group(1)

    # Action title/description (if we fetched real details from Safiran API)
    action_title = None
    action_description = None
    if isinstance(action_details, dict):
        data_obj = action_details.get("data") if isinstance(action_details.get("data"), dict) else {}
        action_title = (
            action_details.get("title")
            or action_details.get("name")
            or action_details.get("actionTitle")
            or data_obj.get("title")
        )
        action_description = (
            action_details.get("description")
            or action_details.get("desc")
            or data_obj.get("description")
        )
    action_label = action_title or (f"کنش شماره {action_id}" if action_id else "این کنش")
    first_name = _first_name_from_user_data(user_data)
    greeting = _greeting_prefix(first_name)

    result = {
        "welcome_message": "",
        "conversation_starters": [],
        "subtitle": None,
    }
    
    # ========================================================================
    # GUEST_FAQ Agent
    # ========================================================================
    if agent_key == "guest_faq":
        # Before registration paths
        if entry_path in ("/register", "/login"):
            result["welcome_message"] = f"{greeting} خوش اومدی به سفیران آیه‌ها 🌟\n\nمی‌بینم که می‌خوای ثبت‌نام کنی. خیلی خوشحالم که می‌خوای سفیر بشی! بذار ببینم چطور می‌تونم کمکت کنم."
            result["conversation_starters"] = [
                "سفیر آیه‌ها یعنی چی و چه نقشی داره؟",
                "چطور می‌تونم ثبت‌نام کنم؟",
                "چه کنش‌هایی می‌تونم انجام بدم؟",
            ]
            result["subtitle"] = "راهنمای ثبت‌نام و شروع"
        
        # Homepage or main entry
        elif entry_path in ("/", "/home"):
            result["welcome_message"] = f"{greeting} خوش اومدی به سفیران آیه‌ها 🌟\n\nاینجا اتاق فرمان و پشت‌صحنه نهضت «زندگی با آیه‌ها»ست. من اینجام تا بهت کمک کنم نقش سفیر رو بفهمی، کنش‌های مناسب رو انتخاب کنی و برات محتوا تولید کنم."
            result["conversation_starters"] = [
                "سفیر آیه‌ها یعنی چی؟ چطور باید شروع کنم؟",
                "کنش‌های ویژه چیه و کدوم رو انتخاب کنم؟",
                "من وقت کم دارم، چه فعالیت سریعی می‌تونم انجام بدم؟",
            ]
            result["subtitle"] = "راهنمای اولیه"
        
        # Action list page
        elif entry_path == "/action-list":
            result["welcome_message"] = f"{greeting} می‌بینم که در حال دیدن لیست کنش‌ها هستی 🌟\n\nچه کنشی مد نظرته؟ می‌تونم کمکت کنم انتخاب کنی یا محتوا براش تولید کنم."
            result["conversation_starters"] = [
                "کدوم کنش رو انتخاب کنم؟",
                "برای این کنش چه محتوایی نیاز دارم؟",
                "چطور می‌تونم یک کنش رو شروع کنم؟",
            ]
            result["subtitle"] = "راهنمای انتخاب کنش"
        
        # Specific action page
        elif action_id:
            if action_description:
                desc_snippet = action_description[:180] + ("..." if len(action_description) > 180 else "")
                result["welcome_message"] = (
                    f"{greeting} می‌بینم که در حال دیدن «{action_label}» هستی 🌟\n\n"
                    f"خلاصه این کنش: {desc_snippet}\n\n"
                    "می‌خوای درباره همین کنش بیشتر بدونی یا محتوا براش تولید کنم؟"
                )
            else:
                result["welcome_message"] = f"{greeting} می‌بینم که در حال دیدن «{action_label}» هستی 🌟\n\nمی‌خوای درباره این کنش بیشتر بدونی یا محتوا براش تولید کنم؟"
            result["conversation_starters"] = [
                f"برای {action_label} چه محتوایی نیاز دارم؟",
                "چطور این کنش رو انجام بدم؟",
                "این کنش برای چه کسانی مناسبه؟",
            ]
            result["subtitle"] = f"راهنمای کنش #{action_id}"
        
        # Default FAQ
        else:
            result["welcome_message"] = f"{greeting} خوش اومدی به سفیران آیه‌ها 🌟\n\nچطور می‌تونم کمکت کنم؟ می‌تونی از من درباره سفیران، کنش‌ها، محتوا یا هر چیز دیگه‌ای بپرسی."
            result["conversation_starters"] = [
                "سفیر آیه‌ها یعنی چی؟",
                "کنش‌های قرآنی چیه؟",
                "چطور می‌تونم شروع کنم؟",
            ]
            result["subtitle"] = "راهنمای اولیه"
    
    # ========================================================================
    # ACTION_EXPERT Agent
    # ========================================================================
    elif agent_key == "action_expert":
        # Specific action page
        if action_id:
            result["welcome_message"] = f"{greeting} برای تولید محتوای «{action_label}» آماده‌ام 🎯\n\nچه نوع محتوایی نیاز داری؟ می‌تونم برات اسکریپت، متن، یا راهنمای عملیاتی تولید کنم."
            result["conversation_starters"] = [
                f"برای {action_label} چه محتوایی تولید کنم؟",
                "اسکریپت کامل برای این کنش",
                "راهنمای عملیاتی اجرای این کنش",
            ]
            result["subtitle"] = f"تولید محتوا برای کنش #{action_id}"
        
        # Action list
        elif entry_path == "/action-list":
            result["welcome_message"] = f"{greeting} برای تولید محتوای کنش‌ها آماده‌ام 🎯\n\nچه کنشی مد نظرته؟ می‌تونم برات محتوا، اسکریپت یا راهنمای عملیاتی تولید کنم."
            result["conversation_starters"] = [
                "برای یک محفل خانگی محتوا تولید کن",
                "اسکریپت برای آیه صبحگاه",
                "راهنمای فضاسازی قرآنی خانه",
            ]
            result["subtitle"] = "تولید محتوای کنش‌ها"
        
        # Report form
        elif entry_path == "/actions/report-form":
            result["welcome_message"] = f"{greeting} می‌بینم که می‌خوای گزارش کنش ثبت کنی 📝\n\nمی‌تونم کمکت کنم گزارش رو بنویسی یا اگر سوالی داری جواب بدم."
            result["conversation_starters"] = [
                "چطور گزارش کنش رو بنویسم؟",
                "چه اطلاعاتی باید در گزارش باشه؟",
                "نمونه گزارش برای یک کنش",
            ]
            result["subtitle"] = "راهنمای ثبت گزارش"
        
        # Default
        else:
            result["welcome_message"] = f"{greeting} برای تولید محتوای کنش‌ها آماده‌ام 🎯\n\nچه کنشی مد نظرته؟ می‌تونم برات محتوا، اسکریپت یا راهنمای عملیاتی تولید کنم."
            result["conversation_starters"] = [
                "برای یک محفل خانگی محتوا تولید کن",
                "اسکریپت برای آیه صبحگاه",
                "چه کنشی رو انتخاب کنم؟",
            ]
            result["subtitle"] = "تولید محتوای کنش‌ها"
    
    # ========================================================================
    # CONTENT_GENERATION_EXPERT Agent
    # ========================================================================
    elif agent_key == "content_generation_expert":
        if action_id:
            result["welcome_message"] = f"{greeting} من متخصص پیشرفته تولید محتوا هستم 🎨\n\nمی‌بینم که در حال دیدن «{action_label}» هستی. می‌تونم برات محتوای کامل، حرفه‌ای و آماده اجرا تولید کنم."
            result["conversation_starters"] = [
                f"محتوای کامل و حرفه‌ای برای {action_label}",
                "اسکریپت طولانی و جزئی برای این کنش",
                "راهنمای عملیاتی دقیق برای اجرا",
            ]
            result["subtitle"] = f"تولید محتوای پیشرفته - کنش #{action_id}"
        else:
            result["welcome_message"] = f"{greeting} من متخصص پیشرفته تولید محتوا هستم 🎨\n\nبرای کدام کنش می‌خواهی محتوا تولید کنی؟ می‌تونم برات محتوای کامل، حرفه‌ای و آماده اجرا تولید کنم."
            result["conversation_starters"] = [
                "برای کدام کنش می‌خواهی محتوا تولید کنی؟",
                "محتوای کامل برای یک محفل خانگی",
                "اسکریپت حرفه‌ای برای سخنرانی",
            ]
            result["subtitle"] = "تولید محتوای پیشرفته"
    
    # ========================================================================
    # KONESH_EXPERT Agent (konesh already known from path/action_details)
    # ========================================================================
    elif agent_key == "konesh_expert":
        if action_id:
            result["welcome_message"] = f"{greeting} می‌بینم که در حال دیدن «{action_label}» هستی 🌟\n\nمی‌خوای درباره همین کنش بیشتر بدونی یا محتوا براش تولید کنم؟"
            result["conversation_starters"] = [
                f"برای {action_label} چه محتوایی نیاز دارم؟",
                "چطور این کنش رو انجام بدم؟",
                "این کنش برای چه کسانی مناسبه؟",
            ]
            result["subtitle"] = f"راهنمای کنش #{action_id}"
        elif entry_path == "/action-list":
            result["welcome_message"] = f"{greeting} می‌بینم که در حال دیدن لیست کنش‌ها هستی 🌟\n\nچه کنشی مد نظرته؟ می‌تونم کمکت کنم انتخاب کنی یا محتوا براش تولید کنم."
            result["conversation_starters"] = [
                "کدوم کنش رو انتخاب کنم؟",
                "برای این کنش چه محتوایی نیاز دارم؟",
                "چطور می‌تونم یک کنش رو شروع کنم؟",
            ]
            result["subtitle"] = "راهنمای انتخاب کنش"
        else:
            result["welcome_message"] = f"{greeting} متخصص کنش‌های قرآنی اینجام 🌟\n\nمی‌تونم کمکت کنم کنش مناسب انتخاب کنی، نحوه اجرا رو توضیح بدم یا محتوا برات تولید کنم."
            result["conversation_starters"] = [
                "کدوم کنش رو انتخاب کنم؟",
                "برای محفل خانگی چه محتوایی نیاز دارم؟",
                "چطور کنش رو اجرا کنم؟",
            ]
            result["subtitle"] = "راهنمای کنش‌های قرآنی"
    
    # ========================================================================
    # JOURNEY_REGISTER Agent
    # ========================================================================
    elif agent_key == "journey_register":
        # Profile pages
        if entry_path and "/my-profile" in entry_path:
            if entry_path == "/my-profile/info":
                result["welcome_message"] = f"{greeting} می‌بینم که می‌خوای اطلاعات پروفایلت رو تکمیل کنی 📋\n\nبیا با هم اطلاعاتت رو کامل کنیم تا بتونی بهتر از پلتفرم استفاده کنی."
                result["conversation_starters"] = [
                    "چطور اطلاعات پروفایلم رو تکمیل کنم؟",
                    "چه اطلاعاتی لازمه؟",
                    "چرا باید اطلاعاتم رو کامل کنم؟",
                ]
                result["subtitle"] = "تکمیل پروفایل"
            elif entry_path == "/my-profile/actions":
                result["welcome_message"] = f"{greeting} می‌بینم که می‌خوای کنش‌هایت رو ببینی 📋\n\nمی‌تونم کمکت کنم کنش ثبت کنی یا گزارش بدهی."
                result["conversation_starters"] = [
                    "چطور یک کنش رو ثبت کنم؟",
                    "گزارش کنش رو چطور بدم؟",
                    "کنش‌های من کجا هستند؟",
                ]
                result["subtitle"] = "مدیریت کنش‌ها"
            else:
                result["welcome_message"] = f"{greeting} بیا مسیر سفیران رو با هم طی کنیم 🌟\n\nمی‌تونم کمکت کنم کنش ثبت کنی، گزارش بدهی یا پروفایلت رو تکمیل کنی."
                result["conversation_starters"] = [
                    "چطور یک کنش رو ثبت کنم؟",
                    "گزارش کنش رو چطور بدم؟",
                    "چطور پروفایلم رو تکمیل کنم؟",
                ]
                result["subtitle"] = "راهنمای ثبت کنش"
        else:
            result["welcome_message"] = f"{greeting} بیا مسیر سفیران رو با هم طی کنیم 🌟\n\nمی‌تونم کمکت کنم کنش ثبت کنی، گزارش بدهی یا پروفایلت رو تکمیل کنی."
            result["conversation_starters"] = [
                "چطور یک کنش رو ثبت کنم؟",
                "گزارش کنش رو چطور بدم؟",
                "چطور پروفایلم رو تکمیل کنم؟",
            ]
            result["subtitle"] = "راهنمای ثبت کنش"
    
    # ========================================================================
    # REWARDS_INVITE Agent
    # ========================================================================
    elif agent_key == "rewards_invite":
        if entry_path == "/my-profile/invite-friends":
            result["welcome_message"] = f"{greeting} می‌بینم که می‌خوای دوستات رو دعوت کنی 🎁\n\nمی‌تونم درباره سیستم امتیازات، جوایز و کد معرف بهت توضیح بدم."
            result["conversation_starters"] = [
                "چطور دوستام رو دعوت کنم؟",
                "کد معرف من چیه؟",
                "چه جوایزی می‌تونم بگیرم؟",
            ]
            result["subtitle"] = "دعوت دوستان و جوایز"
        elif entry_path == "/my-profile/achievements":
            result["welcome_message"] = f"{greeting} می‌بینم که می‌خوای دستاوردهات رو ببینی 🏆\n\nمی‌تونم درباره امتیازات، سطوح و جوایز بهت توضیح بدم."
            result["conversation_starters"] = [
                "چطور امتیاز بگیرم؟",
                "چه سطوحی وجود داره؟",
                "چه جوایزی می‌تونم بگیرم؟",
            ]
            result["subtitle"] = "دستاوردها و جوایز"
        else:
            result["welcome_message"] = f"{greeting} برای اطلاعات امتیازات و دعوت‌ها اینجام 🎁\n\nچه چیزی می‌خوای بدونی؟"
            result["conversation_starters"] = [
                "چطور امتیاز بگیرم؟",
                "کد معرف من چیه؟",
                "چه جوایزی می‌تونم بگیرم؟",
            ]
            result["subtitle"] = "جوایز و دعوت"
    
    # ========================================================================
    # Default (fallback)
    # ========================================================================
    else:
        result["welcome_message"] = f"{greeting} چطور می‌تونم کمکت کنم؟"
        result["conversation_starters"] = [
            "چطور می‌تونم شروع کنم؟",
            "سفیران آیه‌ها چیه؟",
            "چه کنش‌هایی وجود داره؟",
        ]
        result["subtitle"] = "دستیار هوشمند"
    
    return result
