#!/bin/bash

# Quick diagnostic script for 422 errors

echo "🔍 AI Platform Diagnostics"
echo "=========================="
echo ""

# Check if services are running
echo "1. Checking running services..."
echo "--------------------------------"
if lsof -i :8000 >/dev/null 2>&1; then
    echo "✅ Port 8000: Service running"
    curl -s http://localhost:8000/health | jq . || echo "❌ Health check failed"
else
    echo "❌ Port 8000: No service"
fi

if lsof -i :8001 >/dev/null 2>&1; then
    echo "✅ Port 8001: Service running"
    curl -s http://localhost:8001/health | jq . || echo "❌ Health check failed"
else
    echo "❌ Port 8001: No service"
fi

if lsof -i :8003 >/dev/null 2>&1; then
    echo "✅ Port 8003: Service running"
    curl -s http://localhost:8003/health | jq . || echo "❌ Health check failed"
else
    echo "❌ Port 8003: No service"
fi

echo ""
echo "2. Checking environment configuration..."
echo "----------------------------------------"
if [ -f .env ]; then
    echo "✅ .env file exists"
    if grep -q "^DATABASE_URL=" .env; then
        echo "✅ DATABASE_URL is set"
        DB_URL=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2-)
        if [[ $DB_URL == postgresql+asyncpg://* ]]; then
            echo "✅ DATABASE_URL format looks correct (asyncpg driver)"
        else
            echo "⚠️  DATABASE_URL might be wrong format. Should start with: postgresql+asyncpg://"
        fi
    else
        echo "❌ DATABASE_URL is NOT set in .env"
    fi

    if grep -q "^LITELLM_API_KEY=" .env; then
        echo "✅ LITELLM_API_KEY is set"
    else
        echo "⚠️  LITELLM_API_KEY is NOT set in .env"
    fi
else
    echo "❌ .env file does not exist!"
    echo ""
    echo "Create it with:"
    echo "  cp .env.example .env"
    echo "  nano .env"
fi

echo ""
echo "3. Checking Tailwind CSS compilation..."
echo "---------------------------------------"
if [ -f static/css/tailwind.css ]; then
    SIZE=$(stat -f%z static/css/tailwind.css 2>/dev/null || stat -c%s static/css/tailwind.css 2>/dev/null)
    if [ $SIZE -gt 1000 ]; then
        echo "✅ Tailwind CSS compiled ($SIZE bytes)"
    else
        echo "⚠️  Tailwind CSS file seems too small ($SIZE bytes)"
        echo "   Run: npm run build:css"
    fi
else
    echo "❌ Tailwind CSS not compiled!"
    echo "   Run: npm run build:css"
fi

echo ""
echo "4. Checking Python dependencies..."
echo "----------------------------------"
if python3 -c "import fastapi, uvicorn, sqlalchemy, asyncpg, pydantic_ai" 2>/dev/null; then
    echo "✅ Core dependencies installed"
else
    echo "❌ Some dependencies missing"
    echo "   Install with: cd services/chat-service && pip install -r requirements.txt"
fi

echo ""
echo "5. Testing database connection..."
echo "---------------------------------"
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    if [ -n "$DATABASE_URL" ]; then
        python3 << 'PYEOF'
import asyncio
import asyncpg
import os
import sys

async def test_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not found")
        return False

    # Convert postgresql+asyncpg:// to postgresql:// for asyncpg
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(db_url),
            timeout=5.0
        )
        await conn.close()
        print("✅ Database connection successful!")
        return True
    except asyncio.TimeoutError:
        print("❌ Database connection timeout (5 seconds)")
        print("   Check if database host is reachable")
        return False
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("   Check DATABASE_URL in .env")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_db())
    sys.exit(0 if result else 1)
PYEOF
    else
        echo "⚠️  DATABASE_URL not set, skipping test"
    fi
else
    echo "⚠️  .env not found, skipping test"
fi

echo ""
echo "6. Recommendations..."
echo "--------------------"

HAS_ISSUES=0

if [ ! -f .env ]; then
    echo "❗ Create .env file:"
    echo "   cp .env.example .env"
    echo "   nano .env  # Add DATABASE_URL and LITELLM_API_KEY"
    HAS_ISSUES=1
fi

if [ ! -f static/css/tailwind.css ]; then
    echo "❗ Compile Tailwind CSS:"
    echo "   npm install"
    echo "   npm run build:css"
    HAS_ISSUES=1
fi

if ! lsof -i :8000 >/dev/null 2>&1 && ! lsof -i :8003 >/dev/null 2>&1; then
    echo "❗ Start services:"
    echo "   ./start_local.sh"
    echo "   # Or with custom port:"
    echo "   GATEWAY_PORT=8003 ./start_local.sh"
    HAS_ISSUES=1
fi

if [ $HAS_ISSUES -eq 0 ]; then
    echo "✅ Everything looks good!"
    echo ""
    echo "If you're still getting 422 errors:"
    echo "1. Check browser console for detailed error"
    echo "2. Check logs: tail -f logs/gateway.log logs/chat-service.log"
    echo "3. Test with curl:"
    echo "   curl -X POST http://localhost:8003/chat/guest_faq \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"message\": \"test\"}'"
fi

echo ""
echo "For more help, see: LOCAL_SETUP.md and TROUBLESHOOTING.md"
