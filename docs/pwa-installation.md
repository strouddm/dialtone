# PWA Installation Guide

Dialtone can be installed as a Progressive Web App (PWA) on your device for quick access and an app-like experience.

## Benefits of Installing as PWA

- **Quick Access**: Launch from your home screen with one tap
- **App-like Experience**: Runs in standalone mode without browser UI
- **Offline Ready**: Works even without network connectivity (with service worker)
- **Automatic Updates**: Always get the latest version automatically

## Installation Instructions

### Android (Chrome)

1. Open Dialtone in Chrome browser
2. Look for the "Install App" button in the header, or:
   - Tap the menu (three dots) in Chrome
   - Select "Install app" or "Add to Home screen"
3. Follow the prompts to install
4. Find Dialtone on your home screen

### iOS (Safari)

1. Open Dialtone in Safari
2. Tap the Share button (square with arrow)
3. Scroll down and tap "Add to Home Screen"
4. Give it a name (default: "Dialtone")
5. Tap "Add"
6. Find Dialtone on your home screen

### Desktop (Chrome/Edge)

1. Open Dialtone in Chrome or Edge
2. Look for the install icon in the address bar (⊕)
3. Click "Install" when prompted
4. Dialtone will open as a standalone app

## Using PWA Shortcuts

Once installed, you can long-press (mobile) or right-click (desktop) the Dialtone icon to access shortcuts:

- **New Recording**: Start recording immediately

## Troubleshooting

### Install Button Not Appearing

- Ensure you're using HTTPS (required for PWA)
- Clear browser cache and reload
- Check that JavaScript is enabled
- Try a different browser (Chrome recommended)

### App Not Working Offline

- Service worker implementation is coming in a future update
- Currently requires network connection for AI processing

### Icons Not Displaying Correctly

- Clear app cache and reinstall
- Check for browser updates
- Report issue with device/browser details

## Platform Limitations

### iOS
- No install prompt (must use Share menu)
- Limited to Safari browser engine
- No automatic updates (manually update via Share menu)

### Desktop
- Shortcuts may not work on all platforms
- Some features require browser permissions

## Updating the PWA

### Android/Desktop
- Updates happen automatically in the background
- Force update by closing and reopening the app

### iOS
- Remove from home screen
- Re-add using Safari Share menu

## Privacy & Security

- All data stays local on your device
- No tracking or analytics in the PWA
- HTTPS required for installation
- Permissions requested only when needed

## Need Help?

If you're having trouble installing or using the PWA:

1. Check browser compatibility
2. Ensure HTTPS is enabled
3. Clear cache and try again
4. Report issues on GitHub