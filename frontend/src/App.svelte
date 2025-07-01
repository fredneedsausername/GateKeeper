<script>
  import BaseTemplate from './components/layout/BaseTemplate.svelte';
  
  // Sample user data
  const user = {
    username: 'Federico',
    avatar: 'F'
  };
  
  // Current route - this would normally come from a router
  let currentRoute = 'entry';
</script>

<BaseTemplate {currentRoute} {user}>
  <div class="p-6">
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
      <h2 class="text-2xl font-bold text-gray-900 mb-4">Welcome to GateKeeper</h2>
      <p class="text-gray-600">Base template is working! You can now add your content here.</p>
    </div>
  </div>
</BaseTemplate>