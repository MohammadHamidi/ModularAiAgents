# Tailwind CSS Setup for AI Platform

This document explains the proper Tailwind CSS setup for production use.

## Why Not Use the CDN?

The Tailwind CSS CDN (`https://cdn.tailwindcss.com`) is convenient for prototyping but **should NOT be used in production** because:
- It's significantly larger (includes all utility classes)
- Slower performance and load times
- No optimization or purging of unused styles
- Tailwind explicitly warns against this usage

## Production Setup

We use Tailwind CLI to compile CSS at build time, which:
- Generates optimized, minified CSS
- Includes only the classes actually used in your HTML
- Results in much smaller file sizes
- Provides better performance

## Directory Structure

```
ai_platform/
├── src/
│   └── input.css              # Input CSS with Tailwind directives
├── static/
│   └── css/
│       └── tailwind.css       # Compiled output (auto-generated)
├── package.json               # npm configuration
├── tailwind.config.js         # Tailwind configuration
├── Chat.html                  # Main chat UI
└── Chat_Iframe.html          # Iframe-compatible chat UI
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd ai_platform
npm install
```

This installs Tailwind CSS as a dev dependency.

### 2. Build CSS (One-time)

```bash
npm run build:css
```

This generates the optimized `static/css/tailwind.css` file.

### 3. Watch Mode (Development)

During development, use watch mode to automatically rebuild CSS when you change HTML or CSS files:

```bash
npm run watch:css
```

Or simply:

```bash
npm run dev
```

## Adding New Tailwind Classes

1. Add your HTML with Tailwind utility classes to any HTML file
2. Run `npm run build:css` to regenerate the CSS
3. The new classes will be automatically included in the output

## Docker Build

The gateway Dockerfile already includes the compiled CSS:

```dockerfile
COPY static /app/static
```

Make sure to run `npm run build:css` before building Docker images.

## Customization

Edit `tailwind.config.js` to customize:
- Content paths (which files to scan for classes)
- Theme extensions (colors, fonts, spacing)
- Plugins

Edit `src/input.css` to add:
- Custom CSS rules
- Font imports
- Global styles

## Troubleshooting

### CSS not loading in browser?

1. Verify the file exists: `ls -la static/css/tailwind.css`
2. Check browser Network tab for 404 errors
3. Ensure the gateway is serving `/static/*` files correctly

### Styles not applying?

1. Rebuild CSS: `npm run build:css`
2. Check `tailwind.config.js` content paths include your HTML files
3. Hard refresh browser (Ctrl+F5 / Cmd+Shift+R)

### Build fails?

1. Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`
2. Update Tailwind: `npm update tailwindcss`
3. Check Node.js version: `node --version` (should be 14+)

## SES Lockdown Warning

If you see this warning in browser console:

```
lockdown-install.js:1 SES Removing unpermitted intrinsics
```

This is **NOT from our code**. It's caused by:
- Browser extensions (MetaMask, other crypto wallets)
- Secure EcmaScript (SES) sandboxing in extensions
- Not a problem with the application

To verify: Open browser in incognito mode (extensions disabled) - the warning should disappear.

## Related Files

- `package.json` - npm scripts and dependencies
- `tailwind.config.js` - Tailwind configuration
- `src/input.css` - Source CSS with Tailwind directives
- `static/css/tailwind.css` - Compiled output (don't edit directly)
- `Chat.html` - Loads `/static/css/tailwind.css`
- `Chat_Iframe.html` - Loads `/static/css/tailwind.css`
- `services/gateway/main.py` - Serves static files at `/static/*`
- `services/gateway/Dockerfile` - Copies static files to container
