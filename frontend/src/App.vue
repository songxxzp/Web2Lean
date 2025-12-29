<template>
  <div id="app">
    <header class="header">
      <h1>Web2Lean</h1>
      <nav class="nav">
        <router-link to="/">Dashboard</router-link>
        <router-link to="/crawlers">Crawlers</router-link>
        <router-link to="/processing">Processing</router-link>
        <router-link to="/database">Database</router-link>
        <router-link to="/scheduler">Scheduler</router-link>
        <router-link to="/config">Configuration</router-link>
      </nav>
    </header>

    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
// App root component
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  min-height: 100vh;
  background: #f5f7fa;
}

.header {
  background: #2c3e50;
  color: white;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h1 {
  font-size: 1.5rem;
}

.nav {
  display: flex;
  gap: 1.5rem;
}

.nav a {
  color: #ecf0f1;
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  transition: background 0.2s;
}

.nav a:hover,
.nav a.router-link-active {
  background: #34495e;
}

.main {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}
</style>
