<script>
  export let currentRoute = 'dashboard';
  
  const menuItems = [
    { id: 'menu', label: 'Menu', icon: 'menu' },
    { id: 'log', label: 'Log', icon: 'log' },
    { id: 'entry', label: 'Entry', icon: 'entry' },
    { id: 'tag', label: 'Tag', icon: 'tag' },
    { id: 'crew', label: 'Crew', icon: 'crew' },
    { id: 'navi', label: 'Navi', icon: 'ship' }
  ];
  
  function handleMenuClick(itemId) {
    // Handle navigation - this would typically dispatch an event or use a router
    console.log('Navigate to:', itemId);
  }
  
  function getIcon(iconType) {
    const icons = {
      menu: `<svg viewBox="0 0 24 24" class="w-6 h-6" fill="currentColor">
        <path d="M3 12h18M3 6h18M3 18h18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>`,
      log: `<svg viewBox="0 0 24 24" class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="4" y="2" width="16" height="20" rx="2"/>
        <line x1="7" y1="6" x2="17" y2="6"/>
        <line x1="7" y1="10" x2="14" y2="10"/>
        <line x1="7" y1="14" x2="16" y2="14"/>
        <line x1="7" y1="18" x2="13" y2="18"/>
      </svg>`,
      entry: `<svg viewBox="0 0 24 24" class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M7 6V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2v16c0 1.1-.9 2-2 2H9c-1.1 0-2-.9-2-2v-2"/>
        <path d="M3 12h12m0 0l-4-4m4 4l-4 4"/>
      </svg>`,
      tag: `<svg viewBox="0 0 24 24" class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <circle cx="12" cy="12" r="4"/>
      </svg>`,
      crew: `<svg viewBox="0 0 24 24" class="w-6 h-6" fill="currentColor">
        <circle cx="12" cy="7" r="4"/>
        <path d="M12 12c-5 0-9 3-9 7v2c0 .5.5 1 1 1h16c.5 0 1-.5 1-1v-2c0-4-4-7-9-7"/>
      </svg>`,
      ship: `<svg viewBox="0 0 24 24" class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="1" width="6" height="6"/>
        <rect x="6" y="7" width="12" height="5"/>
        <path d="M3 12L6 21L12 23L18 21L21 12Z"/>
      </svg>`
    };
    return icons[iconType] || '';
  }
</script>

<aside class="w-64 bg-blue-900 text-white flex flex-col">
  <nav class="flex-1 py-4">
    {#each menuItems as item}
      <button
        class="w-full flex items-center px-6 py-3 text-left hover:bg-blue-800 transition-colors duration-200 {currentRoute === item.id ? 'bg-blue-800 border-r-4 border-white' : ''}"
        on:click={() => handleMenuClick(item.id)}
      >
        <span class="mr-3">
          {@html getIcon(item.icon)}
        </span>
        <span class="text-lg font-medium">{item.label}</span>
      </button>
    {/each}
  </nav>
</aside>