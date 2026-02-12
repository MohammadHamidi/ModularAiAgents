# Safiran Website API Analysis - Opportunities for AI Platform Enhancement

**Date:** 2026-02-12  
**API Version:** v1  
**Analysis Purpose:** Identify endpoints and features that could improve the AI platform system

---

## 🎯 Key Findings Summary

The Safiran API provides extensive endpoints that could significantly enhance the AI platform's capabilities, particularly in:
1. **Action Discovery & Filtering** - Better action recommendations
2. **User Context** - Richer user profile data
3. **Content Integration** - Access to content library
4. **Verse/Ayah Integration** - Quranic verse data
5. **User Activity Tracking** - Better personalization

---

## 📋 Currently Used Endpoints

### ✅ Already Integrated
- `/api/AI/AILogin` - Authentication (currently having issues with 405 errors)
- `/api/AI/GetAIUserData` - User data retrieval
- `/api/AI/GetEncryptedParam` - Encrypted parameter generation

---

## 🚀 High-Value Endpoints for AI Enhancement

### 1. **Action Discovery & Recommendations**

#### `/api/Action/GetActionList` (GET)
**Why Important:**
- Advanced filtering by: Title, IsSpecial, Platforms, Levels, Audiences, Activists, Campaigns, Hashtags
- Pagination support
- **Use Case:** AI agents can recommend actions based on user context, preferences, and filters

**Potential Integration:**
```python
# In action_expert agent
- When user asks "چه کنشی مناسب من است؟"
- Query GetActionList with user's profile data (city, level, etc.)
- Return personalized action recommendations
```

#### `/api/Action/GetOneAction` (GET via Home)
**Why Important:**
- Get detailed action information by ID
- **Use Case:** When user mentions action ID (e.g., from `/actions/40`), fetch full details

**Current Gap:**
- We detect action ID from path but don't fetch action details
- Could enhance context-aware welcome messages with actual action title/description

#### `/api/Action/GetRelatedActions` (GET)
**Why Important:**
- Get related actions for a specific action
- **Use Case:** "کنش‌های مشابه" suggestions in conversation

#### `/api/Action/GetReservedActions` (GET)
**Why Important:**
- Get user's reserved/saved actions
- **Use Case:** "کنش‌های ذخیره‌شده شما" - show user's saved actions

#### `/api/Action/GetUserScoreReport` (GET)
**Why Important:**
- User's score and progress report
- **Use Case:** Show achievements, progress in conversation

---

### 2. **Action Metadata & Filters**

#### `/api/Action/GetActionLevel` (GET)
**Why Important:**
- Get available action levels
- **Use Case:** Filter actions by difficulty/level

#### `/api/Action/GetActionPlatform` (GET)
**Why Important:**
- Get available platforms (خانه، مدرسه، مسجد، etc.)
- **Use Case:** Filter actions by platform

#### `/api/Action/GetAudiences` (GET)
**Why Important:**
- Get target audiences
- **Use Case:** Filter actions by audience type

#### `/api/Action/GetCampaigns` (GET)
**Why Important:**
- Get available campaigns
- **Use Case:** Filter actions by campaign

#### `/api/Action/GetHashtags` (GET)
**Why Important:**
- Search hashtags by term
- **Use Case:** Content generation with relevant hashtags

#### `/api/Action/GetActivists` (GET)
**Why Important:**
- Get activist types
- **Use Case:** Filter actions by activist role

#### `/api/Action/GetReasons` (GET)
**Why Important:**
- Get cancellation reasons
- **Use Case:** When user cancels an action

---

### 3. **Content Library Integration**

#### `/api/Contents/GetContentList` (GET)
**Why Important:**
- Filterable content library (TypeIds, CategoryIds, ActionIds, VerseIds, etc.)
- Pagination support
- **Use Case:** 
  - Content generation expert can reference existing content
  - Suggest related content for actions
  - "محتواهای مرتبط با این کنش"

#### `/api/Contents/GetActionsFilter` (GET)
**Why Important:**
- Search actions for content filtering
- **Use Case:** Link content to actions

#### `/api/Contents/GetVersesFilter` (GET)
**Why Important:**
- Get verses for content filtering
- **Use Case:** Content generation with specific verses

#### `/api/Contents/GetHashtagsFilter` (GET)
**Why Important:**
- Search hashtags for content
- **Use Case:** Add relevant hashtags to generated content

---

### 4. **Verse/Ayah Integration**

#### `/api/Home/GetActionEducations` (GET)
**Why Important:**
- Get educational materials for an action
- **Use Case:** Provide educational resources when discussing actions

**Note:** There's also `/api/AdminVerses/GetList` but it's admin-only. Need to find public verse endpoint.

---

### 5. **User Profile & Context**

#### `/api/Profile/GetUserProfile` (GET)
**Why Important:**
- Comprehensive user profile data
- **Use Case:** Better personalization, context-aware responses

#### `/api/Profile/GetMyActions` (GET)
**Why Important:**
- User's completed/pending actions
- **Use Case:** 
  - "کنش‌های من" - show user's actions
  - Track progress in conversation

#### `/api/Profile/GetSaveActions` (GET)
**Why Important:**
- User's saved actions
- **Use Case:** Reference saved actions in conversation

#### `/api/Profile/GetSaveContents` (GET)
**Why Important:**
- User's saved content
- **Use Case:** Reference saved content

#### `/api/Profile/GetUserAchievement` (GET)
**Why Important:**
- User achievements and progress
- **Use Case:** Show achievements, motivate user

#### `/api/Profile/GetInvites` (GET)
**Why Important:**
- User's invite code and referrals
- **Use Case:** Rewards/invite agent can show invite stats

#### `/api/Profile/GetProfile` (GET)
**Why Important:**
- Full profile information
- **Use Case:** Complete user context

---

### 6. **Action Form & Reporting**

#### `/api/Home/GetActionForm` (GET)
**Why Important:**
- Get report form structure for an action
- **Use Case:** 
  - Help user fill out action report
  - Guide through form fields
  - "چطور گزارش این کنش را ثبت کنم؟"

#### `/api/Home/SubmitActionForm` (POST)
**Why Important:**
- Submit action report
- **Use Case:** AI can help user complete and submit reports

---

### 7. **Common Questions (FAQ)**

#### `/api/Commons/GetCommonQuestions` (GET)
**Why Important:**
- Get FAQ by category (1=Action, 2=Content, 3=Club)
- **Use Case:** 
  - FAQ agent can use real FAQ data
  - Better answers to common questions
  - Currently we might be generating generic answers

---

### 8. **Home Dashboard Data**

#### `/api/Home/GetUserInfo` (GET)
**Why Important:**
- User info displayed on home page
- **Use Case:** Quick user context (level, score, etc.)

#### `/api/Home/GetActions` (GET)
**Why Important:**
- Personalized action recommendations for home
- **Use Case:** Show recommended actions in conversation

#### `/api/Home/GetActionContents` (GET)
**Why Important:**
- Content related to actions
- **Use Case:** Show content for actions

---

## 🔧 Implementation Recommendations

### Priority 1: High Impact, Easy Integration

1. **Action Details Integration**
   - Use `/api/Home/GetOneAction` when user comes from `/actions/{id}`
   - Enhance welcome messages with actual action title/description
   - Store action details in conversation context

2. **Action Recommendations**
   - Use `/api/Action/GetActionList` with user filters
   - Provide personalized action suggestions
   - Filter by user's city, level, platform preferences

3. **User Activity Context**
   - Use `/api/Profile/GetMyActions` to show user's actions
   - Use `/api/Action/GetReservedActions` for saved actions
   - Reference user's progress in conversations

### Priority 2: Medium Impact, Moderate Effort

4. **Content Library Integration**
   - Use `/api/Contents/GetContentList` to suggest related content
   - Link content to actions in recommendations
   - Content generation expert can reference existing content

5. **FAQ Integration**
   - Use `/api/Commons/GetCommonQuestions` for FAQ agent
   - Provide real FAQ answers instead of generated ones
   - Category-based FAQ (Action, Content, Club)

6. **Action Form Assistance**
   - Use `/api/Home/GetActionForm` to help users fill reports
   - Guide through form fields
   - Validate form data before submission

### Priority 3: Nice to Have

7. **Verse Integration**
   - Find public verse endpoint
   - Link verses to actions/content
   - Use verses in content generation

8. **Hashtag Suggestions**
   - Use `/api/Action/GetHashtags` for content generation
   - Suggest relevant hashtags

9. **Related Actions**
   - Use `/api/Action/GetRelatedActions` for suggestions
   - "کنش‌های مشابه" feature

---

## 🛠️ Technical Implementation Notes

### Authentication
- Current issue: `/api/AI/AILogin` returns 405 (Method Not Allowed)
- **Fix Needed:** Check if it should be PATCH instead of POST/GET
- Swagger shows: `"patch"` method for AILogin

### Error Handling
- All endpoints return 200 OK (need to check response body for errors)
- Implement proper error handling for API failures
- Add retry logic for transient failures

### Caching Strategy
- Cache metadata endpoints (Levels, Platforms, Audiences) - rarely change
- Cache user profile data with TTL
- Cache action details with action ID as key

### Rate Limiting
- Implement rate limiting for API calls
- Batch requests where possible
- Use async/await for parallel requests

---

## 📝 Code Structure Suggestions

### New Tool: `SafiranActionTool`
```python
class SafiranActionTool:
    - get_action_details(action_id)
    - get_action_list(filters)
    - get_related_actions(action_id)
    - get_user_actions()
    - get_reserved_actions()
```

### New Tool: `SafiranContentTool`
```python
class SafiranContentTool:
    - get_content_list(filters)
    - get_content_for_action(action_id)
    - search_content(query)
```

### New Tool: `SafiranProfileTool`
```python
class SafiranProfileTool:
    - get_user_profile()
    - get_user_achievements()
    - get_saved_actions()
    - get_saved_contents()
```

### Enhanced Context Manager
- Store action details in context
- Store user activity in context
- Cache frequently accessed data

---

## 🎯 Expected Benefits

1. **Better Personalization**
   - Actions tailored to user's profile, location, level
   - Content suggestions based on user's interests

2. **Richer Context**
   - Actual action details instead of just IDs
   - User's activity history
   - Progress tracking

3. **More Accurate Responses**
   - Real FAQ data instead of generated answers
   - Actual action metadata
   - User-specific data

4. **Better User Experience**
   - Show user's saved actions
   - Reference user's progress
   - Provide actionable recommendations

5. **Content Generation Enhancement**
   - Reference existing content
   - Use real hashtags
   - Link to verses

---

## ⚠️ Important Notes

1. **Authentication Fix Required**
   - `/api/AI/AILogin` method should be PATCH, not POST/GET
   - Current implementation tries multiple methods (GET, POST) but Swagger shows PATCH

2. **API Response Structure**
   - Need to inspect actual response structures
   - Some endpoints may return different formats than expected

3. **Error Handling**
   - Implement comprehensive error handling
   - Handle 401/403 for unauthorized access
   - Handle rate limiting (429)

4. **Testing**
   - Test all endpoints with real data
   - Verify response structures
   - Test error scenarios

---

## 📊 Endpoint Summary Table

| Endpoint | Method | Priority | Use Case |
|----------|--------|----------|----------|
| `/api/Action/GetActionList` | GET | High | Action recommendations |
| `/api/Home/GetOneAction` | GET | High | Action details |
| `/api/Action/GetReservedActions` | GET | High | User's saved actions |
| `/api/Profile/GetMyActions` | GET | High | User's actions |
| `/api/Profile/GetUserProfile` | GET | High | User context |
| `/api/Contents/GetContentList` | GET | Medium | Content suggestions |
| `/api/Commons/GetCommonQuestions` | GET | Medium | FAQ answers |
| `/api/Home/GetActionForm` | GET | Medium | Report form help |
| `/api/Action/GetRelatedActions` | GET | Low | Related actions |
| `/api/Action/GetHashtags` | GET | Low | Hashtag suggestions |

---

## 🔄 Next Steps

1. **Fix Authentication**
   - Update `AILogin` to use PATCH method
   - Test authentication flow

2. **Implement Priority 1 Features**
   - Action details integration
   - Action recommendations
   - User activity context

3. **Create New Tools**
   - SafiranActionTool
   - SafiranContentTool
   - SafiranProfileTool

4. **Update Agents**
   - Enhance action_expert with action details
   - Enhance guest_faq with real FAQ data
   - Enhance content_generation_expert with content library

5. **Testing & Validation**
   - Test all new integrations
   - Validate response structures
   - Test error scenarios

---

**Generated:** 2026-02-12  
**Status:** Ready for Implementation Review
