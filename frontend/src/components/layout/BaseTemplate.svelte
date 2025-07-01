<script>
  import Sidebar from './Sidebar.svelte';
  import HeaderBar from './HeaderBar.svelte';
  import MainContent from './MainContent.svelte';
  
  export let currentRoute = 'dashboard';
  export let user = { username: 'User', avatar: 'F' };
</script>

<div class="h-screen flex bg-gray-50">
  <!-- Sidebar -->
  <Sidebar {currentRoute} />
  
  <!-- Main Content Area -->
  <div class="flex-1 flex flex-col">
    <!-- Header -->
    <HeaderBar {user} />
    
    <!-- Main Content -->
    <MainContent>
      <slot></slot>
    </MainContent>
  </div>
</div>