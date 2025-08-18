# DiveDB Dash SASS Setup

This directory contains the SASS styling setup for the DiveDB Dash application.

## Files

- `assets/styles.scss` - Main SASS file containing all the custom styles
- `assets/styles.css` - Compiled CSS file (auto-generated)
- `package.json` - Node.js package configuration for SASS compilation

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Compile SASS to CSS:
   ```bash
   npm run build-css
   ```

3. Watch for changes during development:
   ```bash
   npm run watch-css
   ```

## Development Workflow

1. Edit `assets/styles.scss` with your changes
2. Run `npm run build-css` to compile (or use `npm run watch-css` for auto-compilation)
3. The compiled CSS will be automatically loaded by the Dash app
