<script>
  import { onMount } from 'svelte';
  
  export let user = { username: 'User', avatar: 'F' };
  
  let currentTime = '';
  
  function updateTime() {
    const now = new Date();
    currentTime = now.toLocaleTimeString('it-IT', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
  }
  
  onMount(() => {
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  });
  
  function handleUserClick() {
    // Handle user menu/profile click
    console.log('User clicked');
  }
</script>

<header class="bg-white border-b border-gray-200 px-6 py-4">
  <div class="flex items-center justify-between">
    <!-- Left side - could add breadcrumbs or page title here -->
    <div class="flex-1">
    </div>
    
    <!-- Center - App Name -->
    <div class="flex-1 text-center">
      <h1 class="text-2xl font-bold text-gray-900">GateKeeper</h1>
    </div>
    
    <!-- Right side - Time and User -->
    <div class="flex-1 flex items-center justify-end space-x-4">
      <!-- Time Display -->
      <div class="text-sm text-gray-600 hidden sm:block">
        <span class="font-medium">time</span>
      </div>
      
      <!-- User Avatar -->
      <button
        class="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-lg hover:bg-blue-700 transition-colors duration-200"
        on:click={handleUserClick}
        title={user.username}
      >
        {user.avatar}
      </button>
    </div>
  </div>
</header>