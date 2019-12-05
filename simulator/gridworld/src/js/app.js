import $$ from 'dom7'
import Framework7 from 'framework7/framework7.esm.bundle.js'
import 'framework7/css/framework7.bundle.css'
// Icons and App Custom Styles
import '../css/icons.css'
import '../css/app.css'
// Import Routes
import routes from './routes.js'
// Game of Life
import Arena from './Arena'

const app = new Framework7({ // eslint-disable-line no-unused-vars
  root: '#app', // App root element

  name: 'JS-son: Game of Life', // App name
  theme: 'auto', // Automatic theme detection
  // App root data
  data: () => {
    $$(document).on('page:init', e => {
      let arena = Arena()
      let shouldRestart = false
      document.getElementById('log-button').onclick = () => {
        const uriContent = `data:text/plain;charset=utf-8,${encodeURIComponent(JSON.stringify(window.simulationLog))}`
        window.open(uriContent, 'simulation-log.json')
      }
      $$('.restart-button').on('click', () => {
        shouldRestart = true
      })
      window.setInterval(() => {
        if (shouldRestart) {
          shouldRestart = false
          arena = Arena()
        } else {
          arena.run(1)
          console.log(arena)
          $$('#arena-grid').html(arena.render(arena.state))
        }
      }, 2000)
    })
  },
  // App routes
  routes: routes
})
