let deferredPrompt = null;
let installButton = null;

// Listen for install prompt
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  showInstallButton();
});

function showInstallButton() {
  installButton = document.createElement('button');
  installButton.className = 'install-button';
  installButton.setAttribute('aria-label', 'Install Dialtone app');
  installButton.innerHTML = `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M12 2L12 14M12 14L17 9M12 14L7 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M5 19H19C20.1046 19 21 18.1046 21 17V17C21 15.8954 20.1046 15 19 15H5C3.89543 15 3 15.8954 3 17V17C3 18.1046 3.89543 19 5 19Z" stroke="currentColor" stroke-width="2"/>
    </svg>
    <span>Install App</span>
  `;
  installButton.addEventListener('click', installApp);
  
  const header = document.querySelector('.app-header');
  if (header) {
    header.appendChild(installButton);
  }
}

async function installApp() {
  if (!deferredPrompt) return;
  
  installButton.disabled = true;
  deferredPrompt.prompt();
  
  try {
    const { outcome } = await deferredPrompt.userChoice;
    console.log(`Install prompt outcome: ${outcome}`);
    
    // Track install metrics
    if (typeof gtag !== 'undefined') {
      gtag('event', 'pwa_install_prompt', {
        'event_category': 'engagement',
        'event_label': outcome
      });
    }
  } catch (error) {
    console.error('Error during app installation:', error);
  } finally {
    // Clean up
    deferredPrompt = null;
    if (installButton) {
      installButton.remove();
      installButton = null;
    }
  }
}

// Track app installation
window.addEventListener('appinstalled', () => {
  console.log('PWA installed successfully');
  
  // Track successful installation
  if (typeof gtag !== 'undefined') {
    gtag('event', 'pwa_installed', {
      'event_category': 'engagement'
    });
  }
});

// Handle URL parameters for shortcuts
function handleShortcutAction() {
  const urlParams = new URLSearchParams(window.location.search);
  const action = urlParams.get('action');
  
  if (action === 'record') {
    // Auto-start recording if opened from shortcut
    window.addEventListener('load', () => {
      const recordButton = document.getElementById('recordButton');
      if (recordButton && !recordButton.disabled) {
        // Small delay to ensure everything is initialized
        setTimeout(() => {
          console.log('Auto-starting recording from PWA shortcut');
          recordButton.click();
        }, 500);
      }
    });
  }
}

// Initialize PWA features
handleShortcutAction();

// Service worker registration (for future implementation)
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    // Service worker will be registered in issue #20
    console.log('Service worker support detected, registration pending implementation');
  });
}

// Standalone mode detection
if (window.matchMedia('(display-mode: standalone)').matches) {
  console.log('App running in standalone mode');
  document.body.classList.add('pwa-standalone');
}